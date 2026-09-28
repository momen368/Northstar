from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Job, JobSkill, Skill


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, owner_id: int, values: dict[str, object]) -> Job:
        skill_names = values.pop("skills", [])
        skills = [self._get_or_create_skill(name) for name in skill_names]
        job = Job(owner_id=owner_id, **values)
        job.job_skills = [JobSkill(skill=skill) for skill in skills]
        self.db.add(job)
        self.db.commit()
        return self.get_owned(owner_id, job.id)

    def get_owned(self, owner_id: int, job_id: int) -> Job | None:
        statement = (
            select(Job)
            .where(Job.id == job_id, Job.owner_id == owner_id)
            .options(selectinload(Job.job_skills).selectinload(JobSkill.skill))
        )
        return self.db.scalar(statement)

    def list_owned(self, owner_id: int, limit: int, offset: int) -> tuple[list[Job], int]:
        base = select(Job).where(Job.owner_id == owner_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        statement = (
            base.options(selectinload(Job.job_skills).selectinload(JobSkill.skill))
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement)), total

    def search(
        self,
        owner_id: int,
        keyword: str | None,
        location: str | None,
        experience_level: str | None,
        skill: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Job], int]:
        statement = select(Job).where(Job.owner_id == owner_id)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            statement = statement.where(
                or_(Job.title.ilike(pattern), Job.company.ilike(pattern), Job.description.ilike(pattern))
            )
        if location:
            statement = statement.where(Job.location.ilike(f"%{location.strip()}%"))
        if experience_level:
            statement = statement.where(Job.experience_level.ilike(experience_level.strip()))
        if skill:
            statement = statement.join(Job.job_skills).join(JobSkill.skill).where(
                Skill.name.ilike(skill.strip())
            )
        matching_jobs = statement.with_only_columns(Job.id).distinct().order_by(None).subquery()
        count_statement = select(func.count()).select_from(matching_jobs)
        total = self.db.scalar(count_statement) or 0
        statement = (
            statement.distinct()
            .options(selectinload(Job.job_skills).selectinload(JobSkill.skill))
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement)), total

    def update(self, job: Job, values: dict[str, object]) -> Job:
        skill_names = values.pop("skills", [])
        skills = [self._get_or_create_skill(name) for name in skill_names]
        for field, value in values.items():
            setattr(job, field, value)
        job.job_skills = [JobSkill(skill=skill) for skill in skills]
        self.db.commit()
        return self.get_owned(job.owner_id, job.id)

    def delete(self, job: Job) -> None:
        self.db.delete(job)
        self.db.commit()

    def _get_or_create_skill(self, name: str) -> Skill:
        skill = self.db.scalar(
            select(Skill).where(func.lower(Skill.name) == name.casefold(), Skill.category == "general")
        )
        if skill is None:
            skill = Skill(name=name, category="general")
            self.db.add(skill)
            self.db.flush()
        return skill