export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

export function showNotice(message, type = "error", target = document.querySelector("#page-notice")) {
  if (!target) return;
  target.hidden = false;
  target.className = `notice ${type}`;
  target.textContent = message;
}

export function setLoading(element, message = "Loading…") {
  if (element) {
    element.setAttribute("aria-busy", "true");
    element.innerHTML = `<div class="loading-state"><span class="spinner" aria-hidden="true"></span>${escapeHtml(message)}</div>`;
  }
}

export function clearLoading(element) { element?.removeAttribute("aria-busy"); }
export function emptyState(message) { return `<div class="empty-state">${escapeHtml(message)}</div>`; }
export function formValues(form) { return Object.fromEntries(new FormData(form).entries()); }
export function list(items, renderItem, emptyMessage) {
  return items?.length ? items.map(renderItem).join("") : emptyState(emptyMessage);
}