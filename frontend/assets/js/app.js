import { apiRequest, authenticate, getToken } from "./api.js";
import { logout, requireAuth } from "./auth.js";
import { clearLoading, emptyState, escapeHtml, formValues, list, setLoading, showNotice } from "./dom.js";

const page = document.body.dataset.page;
const THEME_KEY = "northstar_theme";
const savedTheme = localStorage.getItem(THEME_KEY);
document.body.dataset.theme = ["dark", "light", "glass"].includes(savedTheme) ? savedTheme : "dark";
document.querySelectorAll("[data-theme-control]").forEach((control) => {
  control.value = document.body.dataset.theme;
  control.addEventListener("change", () => {
    const theme = ["dark", "light", "glass"].includes(control.value) ? control.value : "dark";
    document.body.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
    document.querySelectorAll("[data-theme-control]").forEach((other) => { other.value = theme; });
  });
});
document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", logout));

function skills(values = []) { return values.map((item) => `<span class="skill-chip">${escapeHtml(item)}</span>`).join(""); }

function renderAnalysis(analysis) {
  const value = analysis.result;
  const personal = value.personal_information?.full_name ? `<p class="muted">${escapeHtml(value.personal_information.full_name)}</p>` : "";
  return `<div class="analysis-summary">${personal}<p>${escapeHtml(value.summary || "No professional summary was found in the resume.")}</p></div>
    <div class="analysis-grid"><section><h3>Technical skills</h3><div class="chip-row">${skills(value.technical_skills)}</div></section><section><h3>Soft skills</h3><div class="chip-row">${skills(value.soft_skills)}</div></section>
    <section><h3>Experience</h3>${list(value.experience, (item) => `<div class="detail-line"><strong>${escapeHtml(item.position || "Position not specified")}</strong><span>${escapeHtml(item.company || "")}</span><p>${escapeHtml((item.responsibilities || []).join(" · "))}</p></div>`, "No work experience section found.")}</section>
    <section><h3>Education</h3>${list(value.education, (item) => `<div class="detail-line"><strong>${escapeHtml(item.degree || item.field_of_study || "Education")}</strong><span>${escapeHtml(item.institution || "")}</span></div>`, "No education section found.")}</section>
    <section><h3>Projects</h3>${list(value.projects, (item) => `<div class="detail-line"><strong>${escapeHtml(item.name || "Project")}</strong><p>${escapeHtml(item.description || "")}</p><div class="chip-row">${skills(item.technologies)}</div></div>`, "No projects found.")}</section>
    <section><h3>Certifications and languages</h3><p>${escapeHtml(value.certifications.map((item) => item.name).filter(Boolean).join(" · ") || "No certifications found.")}</p><p>${escapeHtml(value.languages.map((item) => item.name).filter(Boolean).join(" · ") || "No languages found.")}</p></section></div>`;
}

function renderRecommendations(items) {
  return list(items, (item) => `<article class="record-item recommendation-item"><div class="match-score">${item.match_score}<small>FIT</small></div><div class="record-copy"><strong>${escapeHtml(item.job_title)} · ${escapeHtml(item.company)}</strong><p>${escapeHtml(item.explanation)}</p><div class="chip-row">${skills(item.matched_skills)}</div>${item.missing_skills.length ? `<p class="gap-text">Gaps: ${escapeHtml(item.missing_skills.join(", "))}</p>` : ""}</div></article>`, "No recommendations yet. Analyze a resume, then compare it with one of your jobs.");
}

function renderBulletGroup(title, values = []) {
  return `<section class="suggestion-group"><h4>${escapeHtml(title)}</h4>${list(values, (value) => `<p>${escapeHtml(value)}</p>`, "No items available.")}</section>`;
}

function renderSources(sources = []) {
  return `<section class="suggestion-group"><h4>Sources</h4>${list(sources, (item) => `<p><strong>${escapeHtml(item.title)}</strong> · ${escapeHtml(item.category)} · ${escapeHtml(item.source)}</p>`, "No knowledge-base sources were used.")}</section>`;
}

async function initAuthForm() {
  if (getToken() && page === "home") return window.location.replace("/dashboard.html");
  const form = document.querySelector(page === "login" ? "#login-form" : "#register-form");
  if (!form) return;
  const notice = document.querySelector("#notice");
  if (new URLSearchParams(location.search).has("expired")) showNotice("Your session expired. Sign in again.", "info", notice);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    button.disabled = true; button.textContent = "Working…";
    try { await authenticate(page === "login" ? "login" : "register", formValues(form)); location.assign("/dashboard.html"); }
    catch (error) { showNotice(error.message, "error", notice); }
    finally { button.disabled = false; button.textContent = page === "login" ? "Sign in ↗" : "Create account ↗"; }
  });
}

async function initDashboard() {
  if (!await requireAuth()) return;
  const resumesElement = document.querySelector("#dashboard-resumes");
  const jobsElement = document.querySelector("#dashboard-jobs");
  const matchesElement = document.querySelector("#dashboard-matches");
  [resumesElement, jobsElement, matchesElement].forEach((element) => setLoading(element));
  try {
    const [resumes, jobs] = await Promise.all([apiRequest("/api/resumes"), apiRequest("/api/jobs?limit=4&offset=0")]);
    clearLoading(resumesElement); clearLoading(jobsElement); clearLoading(matchesElement);
    const insights = await Promise.all(resumes.slice(0, 4).map(async (resume) => {
      try { return [resume, await apiRequest(`/api/resumes/${resume.id}/analysis`)]; }
      catch { return [resume, null]; }
    }));
    resumesElement.innerHTML = list(insights, ([resume, analysis]) => `<article class="record-item dashboard-resume"><div class="record-copy"><a class="record-title" href="/resume.html?id=${resume.id}">${escapeHtml(resume.original_filename)}</a><p>${escapeHtml(resume.file_type.toUpperCase())} · Uploaded ${new Date(resume.created_at).toLocaleDateString()} · ${analysis ? "Analyzed" : "Analysis pending"}</p>${analysis ? `<p>${escapeHtml(analysis.result.summary || "No summary extracted.")}</p><div class="chip-row">${skills(analysis.result.technical_skills)}</div>` : ""}</div></article>`, "No resumes yet. Upload one to start an analysis.");
    jobsElement.innerHTML = list(jobs.items, (job) => `<a class="record-item record-link" href="/job-details.html?id=${job.id}"><div class="record-copy"><strong>${escapeHtml(job.title)}</strong><p>${escapeHtml(job.company)} · ${escapeHtml(job.location)}</p></div><span aria-hidden="true">↗</span></a>`, "No job listings yet.");
    const recommendations = [];
    for (const resume of resumes.slice(0, 5)) recommendations.push(...await apiRequest(`/api/recommendations/${resume.id}`));
    matchesElement.innerHTML = renderRecommendations(recommendations.sort((a, b) => b.match_score - a.match_score).slice(0, 4));
    const advisorSelect = document.querySelector("#dashboard-advisor-resume");
    advisorSelect.innerHTML = resumes.length ? resumes.map((resume) => `<option value="${resume.id}">${escapeHtml(resume.original_filename)}</option>`).join("") : '<option value="">Upload a resume first</option>';
  } catch (error) { showNotice(error.message); }
  document.querySelector("#dashboard-advisor-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const values = formValues(event.currentTarget);
    const target = document.querySelector("#dashboard-advisor-result"); setLoading(target, "Retrieving relevant guidance…");
    try {
      const answer = await apiRequest("/api/career-advisor", { method: "POST", body: { resume_id: Number(values.resume_id), question: values.question } });
      target.innerHTML = `<p class="dashboard-answer">${escapeHtml(answer.answer)}</p>${renderSources(answer.sources)}<a class="text-link" href="/advisor.html">Open full advisor →</a>`;
    } catch (error) { target.innerHTML = emptyState(error.message); }
  });
}

async function initResume() {
  if (!await requireAuth()) return;
  const listElement = document.querySelector("#resume-list");
  const analysisPanel = document.querySelector("#resume-analysis");
  let selectedResumeId = new URLSearchParams(location.search).get("id");
  const loadResumes = async () => {
    setLoading(listElement);
    const resumes = await apiRequest("/api/resumes"); clearLoading(listElement);
    listElement.innerHTML = list(resumes, (resume) => `<article class="record-item"><div class="record-copy"><button class="record-title link-button" data-select-resume="${resume.id}">${escapeHtml(resume.original_filename)}</button><p>${escapeHtml(resume.file_type.toUpperCase())} · ${new Date(resume.created_at).toLocaleDateString()}</p></div><button class="icon-button danger-text" aria-label="Delete ${escapeHtml(resume.original_filename)}" data-delete-resume="${resume.id}">Delete</button></article>`, "Your resume library is empty. Upload a PDF or DOCX to begin.");
    return resumes;
  };
  const showResume = async (resumeId) => {
    selectedResumeId = String(resumeId); analysisPanel.hidden = false;
    document.querySelector("#analysis-title").textContent = "Resume analysis";
    const content = document.querySelector("#analysis-content");
    setLoading(content, "Loading saved analysis…");
    try {
      const [resume, analysis] = await Promise.all([apiRequest(`/api/resumes/${resumeId}`), apiRequest(`/api/resumes/${resumeId}/analysis`)]);
      document.querySelector("#analysis-title").textContent = resume.original_filename;
      content.innerHTML = renderAnalysis(analysis);
    } catch (error) {
      content.innerHTML = emptyState(error.message.includes("analysis not found") ? "This resume has not been analyzed yet." : error.message);
    }
  };
  try { const resumes = await loadResumes(); if (selectedResumeId) await showResume(selectedResumeId); else if (resumes.length) await showResume(resumes[0].id); }
  catch (error) { showNotice(error.message); }

  document.querySelector("#upload-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const button = event.currentTarget.querySelector("button");
    button.disabled = true; button.textContent = "Uploading and extracting…";
    try {
      const result = await apiRequest("/api/resumes/upload", { method: "POST", body: new FormData(event.currentTarget) });
      showNotice(`Uploaded ${result.original_filename}; text extraction is complete.`, "success");
      await loadResumes(); await showResume(result.id);
    } catch (error) { showNotice(error.message); }
    finally { button.disabled = false; button.textContent = "Upload and extract"; }
  });
  listElement.addEventListener("click", async (event) => {
    const selection = event.target.closest("[data-select-resume]");
    const deletion = event.target.closest("[data-delete-resume]");
    try {
      if (selection) await showResume(selection.dataset.selectResume);
      if (deletion) {
        await apiRequest(`/api/resumes/${deletion.dataset.deleteResume}`, { method: "DELETE" });
        showNotice("Resume deleted.", "success"); analysisPanel.hidden = true; await loadResumes();
      }
    } catch (error) { showNotice(error.message); }
  });
  document.querySelector("#analyze-button").addEventListener("click", async (event) => {
    if (!selectedResumeId) return;
    const button = event.currentTarget; button.disabled = true; button.textContent = "Analyzing…";
    try { await apiRequest(`/api/resumes/${selectedResumeId}/analyze`, { method: "POST" }); await showResume(selectedResumeId); showNotice("Structured analysis saved.", "success"); }
    catch (error) { showNotice(error.message); }
    finally { button.disabled = false; button.textContent = "Analyze"; }
  });
  document.querySelector("#improve-button").addEventListener("click", async (event) => {
    if (!selectedResumeId) return;
    const button = event.currentTarget; button.disabled = true; button.textContent = "Reviewing…";
    const target = document.querySelector("#improvement-content"); setLoading(target, "Grounding suggestions in resume and reference material…");
    try {
      const result = await apiRequest(`/api/resumes/${selectedResumeId}/improve`, { method: "POST" }); clearLoading(target);
      target.innerHTML = `<h3>Improvement suggestions</h3>${renderBulletGroup("Strengths", result.strengths)}${renderBulletGroup("Weaknesses", result.weaknesses)}${renderBulletGroup("Missing skills", result.missing_skills)}${renderBulletGroup("Writing improvements", result.improvements)}${renderBulletGroup("Certifications", result.certifications)}${renderBulletGroup("Learning resources", result.learning_resources)}${renderSources(result.sources)}`;
    } catch (error) { target.innerHTML = emptyState(error.message); }
    finally { button.disabled = false; button.textContent = "Improve"; }
  });
}

async function initJobs() {
  if (!await requireAuth()) return;
  const listElement = document.querySelector("#job-list");
  async function loadJobs(filters = {}) {
    setLoading(listElement, "Searching your job listings…");
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    const result = await apiRequest(`/api/jobs/search?${params}`); clearLoading(listElement);
    document.querySelector("#job-count").textContent = `${result.total} listing${result.total === 1 ? "" : "s"}`;
    listElement.innerHTML = list(result.items, (job) => `<article class="job-row"><div class="record-copy"><a class="record-title" href="/job-details.html?id=${job.id}">${escapeHtml(job.title)}</a><p>${escapeHtml(job.company)} · ${escapeHtml(job.location || "Location not specified")} · ${escapeHtml(job.experience_level)}</p><p>${escapeHtml(job.description.slice(0, 180))}${job.description.length > 180 ? "…" : ""}</p><div class="chip-row">${skills(job.skills)}</div></div><a class="button secondary small-button" href="/job-details.html?id=${job.id}">Details →</a></article>`, "No jobs match those filters. Try widening your search.");
  }
  try { await loadJobs(); } catch (error) { showNotice(error.message); }
  document.querySelector("#job-search-form").addEventListener("submit", async (event) => {
    event.preventDefault(); try { await loadJobs(formValues(event.currentTarget)); } catch (error) { showNotice(error.message); }
  });
  document.querySelector("#job-create-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const form = event.currentTarget; const values = formValues(form);
    values.skills = values.skills.split(",").map((item) => item.trim()).filter(Boolean);
    const button = form.querySelector("button"); button.disabled = true; button.textContent = "Saving…";
    try { await apiRequest("/api/jobs", { method: "POST", body: values }); form.reset(); showNotice("Job listing saved.", "success"); await loadJobs(); }
    catch (error) { showNotice(error.message); }
    finally { button.disabled = false; button.textContent = "Save listing"; }
  });
}

async function initJobDetails() {
  if (!await requireAuth()) return;
  const id = new URLSearchParams(location.search).get("id");
  const container = document.querySelector("#job-details");
  if (!id) { container.innerHTML = emptyState("No job was selected."); return; }
  const select = document.querySelector("#match-resume");
  try {
    const [job, resumes] = await Promise.all([apiRequest(`/api/jobs/${id}`), apiRequest("/api/resumes")]);
    container.innerHTML = `<p class="eyebrow">${escapeHtml(job.experience_level)} · ${escapeHtml(job.location || "Location not specified")}</p><h1>${escapeHtml(job.title)}</h1><p class="company-line">${escapeHtml(job.company)}</p><div class="chip-row">${skills(job.skills)}</div><div class="job-description">${escapeHtml(job.description)}</div><div class="button-row"><button class="button secondary" id="edit-job-toggle">Edit listing</button><button class="button text-danger" id="delete-job">Delete listing</button></div><form id="job-edit-form" class="edit-job-form" hidden><label>Title<input name="title" value="${escapeHtml(job.title)}" required></label><label>Company<input name="company" value="${escapeHtml(job.company)}" required></label><label>Location<input name="location" value="${escapeHtml(job.location)}"></label><label>Experience level<input name="experience_level" value="${escapeHtml(job.experience_level)}" required></label><label>Description<textarea name="description" required>${escapeHtml(job.description)}</textarea></label><label>Skills <small>Comma separated</small><input name="skills" value="${escapeHtml(job.skills.join(", "))}"></label><button class="button primary">Save changes</button></form>`;
    select.innerHTML = resumes.length ? resumes.map((resume) => `<option value="${resume.id}">${escapeHtml(resume.original_filename)}</option>`).join("") : '<option value="">Upload a resume first</option>';
    document.querySelector("#edit-job-toggle").addEventListener("click", () => { const form = document.querySelector("#job-edit-form"); form.hidden = !form.hidden; });
    document.querySelector("#delete-job").addEventListener("click", async () => {
      if (!confirm("Delete this job listing?")) return;
      try { await apiRequest(`/api/jobs/${id}`, { method: "DELETE" }); location.assign("/jobs.html"); }
      catch (error) { showNotice(error.message); }
    });
    document.querySelector("#job-edit-form").addEventListener("submit", async (event) => {
      event.preventDefault(); const values = formValues(event.currentTarget);
      values.skills = values.skills.split(",").map((item) => item.trim()).filter(Boolean);
      try { await apiRequest(`/api/jobs/${id}`, { method: "PUT", body: values }); showNotice("Job listing updated.", "success"); location.reload(); }
      catch (error) { showNotice(error.message); }
    });
  } catch (error) { container.innerHTML = emptyState(error.message); return; }
  document.querySelector("#match-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const result = document.querySelector("#match-result"); setLoading(result, "Comparing analyzed resume evidence with this job…");
    try {
      const match = await apiRequest("/api/recommendations/match", {
        method: "POST", body: { resume_id: Number(formValues(event.currentTarget).resume_id), job_id: Number(id) },
      });
      result.innerHTML = `<article class="match-result"><div class="match-score large-score">${match.match_score}<small>FIT</small></div><div><h3>Match explanation</h3><p>${escapeHtml(match.explanation)}</p><p><strong>Recommendation:</strong> ${escapeHtml(match.recommendation)}</p></div><section><h3>Matched skills</h3><div class="chip-row">${skills(match.matched_skills)}</div></section><section><h3>Missing skills</h3><div class="chip-row">${skills(match.missing_skills)}</div></section><details><summary>Scoring breakdown</summary><pre>${escapeHtml(JSON.stringify(match.score_breakdown, null, 2))}</pre></details></article>`;
    } catch (error) { result.innerHTML = emptyState(error.message); }
  });
}

async function initAdvisor() {
  if (!await requireAuth()) return;
  const select = document.querySelector("#advisor-resume");
  const result = document.querySelector("#advisor-result");
  try {
    const resumes = await apiRequest("/api/resumes");
    select.innerHTML = resumes.length ? resumes.map((resume) => `<option value="${resume.id}">${escapeHtml(resume.original_filename)}</option>`).join("") : '<option value="">Upload a resume first</option>';
  } catch (error) { showNotice(error.message); return; }
  document.querySelector("#advisor-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const values = formValues(event.currentTarget);
    result.hidden = false; setLoading(result, "Reviewing analysis and retrieving career sources…");
    try {
      const answer = await apiRequest("/api/career-advisor", { method: "POST", body: { resume_id: Number(values.resume_id), question: values.question } });
      result.innerHTML = `<p class="eyebrow">CAREER ADVISOR</p><h2>Guidance</h2><p class="answer-copy">${escapeHtml(answer.answer)}</p>${renderBulletGroup("Skill gaps", answer.skill_gaps)}${renderBulletGroup("Recommended courses", answer.recommended_courses)}${renderBulletGroup("Certifications", answer.certifications)}${renderBulletGroup("Learning resources", answer.learning_resources)}${renderBulletGroup("Roadmap", answer.roadmap)}${renderSources(answer.sources)}`;
    } catch (error) { result.innerHTML = emptyState(error.message); }
  });
}

const initializers = { home: initAuthForm, login: initAuthForm, register: initAuthForm,
  dashboard: initDashboard, resume: initResume, jobs: initJobs, "job-details": initJobDetails, advisor: initAdvisor };
initializers[page]?.();
