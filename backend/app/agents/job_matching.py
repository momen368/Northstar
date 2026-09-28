import json
import re

from pydantic import BaseModel

from backend.app.agents.structured_llm import StructuredLLM
from backend.app.models import Job, ResumeAnalysisRecord
from backend.app.schemas.job_matching import JobMatchResult, MatchNarrative, ScoreBreakdown
from backend.app.schemas.resume_analysis import ResumeAnalysis


EDUCATION_CUES = ("degree", "bachelor", "master", "phd", "education", "university", "college")
STOP_WORDS = {
    "about", "after", "also", "and", "are", "build", "building", "candidate", "company", "experience",
    "for", "from", "have", "into", "including", "looking", "more", "must", "need", "our", "role", "skills",
    "team", "that", "the", "their", "this", "with", "work", "years", "your",
}


class JobMatchingAgent:
    def __init__(self, llm: StructuredLLM | None = None) -> None:
        self.llm = llm or StructuredLLM()

    async def match(self, analysis: ResumeAnalysis, job: Job) -> JobMatchResult:
        job_skills = [(association.skill.name, association.importance) for association in job.job_skills]
        resume_skills = self._resume_skills(analysis)
        normalized_resume_skills = {self._normalize(item) for item in resume_skills}
        matched = [name for name, _weight in job_skills if self._normalize(name) in normalized_resume_skills]
        missing = [name for name, _weight in job_skills if self._normalize(name) not in normalized_resume_skills]
        total_weight = sum(max(weight, 0.0) for _name, weight in job_skills)
        skill_coverage = (sum(max(weight, 0.0) for name, weight in job_skills
                              if self._normalize(name) in normalized_resume_skills) / total_weight
                          if total_weight else 1.0)

        experience_text = " ".join(
            [analysis.summary or ""]
            + [f"{item.position or ''} {item.company or ''} {' '.join(item.responsibilities)}"
               for item in analysis.experience]
        )
        job_text = f"{job.title} {job.description}"
        experience_relevance = self._token_overlap(experience_text, job_text)
        education_required = any(cue in job_text.casefold() for cue in EDUCATION_CUES)
        education_text = " ".join(
            f"{item.degree or ''} {item.field_of_study or ''} {item.institution or ''} {' '.join(item.details)}"
            for item in analysis.education
        )
        education_relevance = self._token_overlap(education_text, job_text) if education_required else None

        if job_skills:
            weighted_score = 0.70 * skill_coverage + 0.25 * experience_relevance
            weight_total = 0.95
        else:
            weighted_score = experience_relevance
            weight_total = 1.0
        if education_required:
            weighted_score += 0.05 * (education_relevance or 0.0)
            weight_total += 0.05
        score = round(100 * weighted_score / weight_total)

        evidence = {
            "score": score,
            "breakdown": {
                "technical_skill_coverage": round(skill_coverage, 3),
                "experience_relevance": round(experience_relevance, 3),
                "education_relevance": round(education_relevance, 3) if education_relevance is not None else None,
            },
            "matched_skills": matched,
            "missing_skills": missing,
            "resume_summary": analysis.summary,
            "resume_experience": [item.model_dump() for item in analysis.experience],
            "resume_education": [item.model_dump() for item in analysis.education] if education_required else [],
            "job_title": job.title,
            "job_description": job.description[:12000],
            "job_skills": [{"name": name, "importance": weight} for name, weight in job_skills],
        }
        narrative = await self.llm.complete(
            "Explain the supplied deterministic resume-job score using only the supplied evidence. Do not infer "
            "experience, qualifications, or skills. Mention matched and missing skills and the scoring breakdown. "
            "Make one practical recommendation grounded in the evidence. Return explanation and recommendation.",
            json.dumps(evidence, ensure_ascii=False),
            MatchNarrative,
        )
        return JobMatchResult(
            match_score=score,
            matched_skills=matched,
            missing_skills=missing,
            explanation=narrative.explanation,
            recommendation=narrative.recommendation,
            score_breakdown=ScoreBreakdown(
                technical_skill_coverage=skill_coverage,
                experience_relevance=experience_relevance,
                education_relevance=education_relevance,
            ),
        )

    @staticmethod
    def _resume_skills(analysis: ResumeAnalysis) -> list[str]:
        skills = list(analysis.technical_skills)
        for project in analysis.projects:
            skills.extend(project.technologies)
        return list(dict.fromkeys(skills))

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().casefold())

    @staticmethod
    def _token_overlap(source: str, target: str) -> float:
        source_terms = {term for term in re.findall(r"[a-z0-9+#.]{4,}", source.casefold()) if term not in STOP_WORDS}
        target_terms = {term for term in re.findall(r"[a-z0-9+#.]{4,}", target.casefold()) if term not in STOP_WORDS}
        if not target_terms:
            return 0.0
        return len(source_terms & target_terms) / len(target_terms)