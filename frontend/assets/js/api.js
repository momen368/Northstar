import { API_BASE_URL } from "./deployment-config.js";

const TOKEN_KEY = "northstar_access_token";

export function getToken() { return sessionStorage.getItem(TOKEN_KEY); }
export function setToken(token) { sessionStorage.setItem(TOKEN_KEY, token); }
export function clearToken() { sessionStorage.removeItem(TOKEN_KEY); }

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }
  let response;
  try { response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, body, credentials: "same-origin" }); }
  catch { throw new Error("Could not reach the server. Check your connection and try again."); }
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    clearToken();
    if (!new Set(["login", "register"]).has(document.body.dataset.page)) window.location.assign("/login.html?expired=1");
  }
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
  }
  return payload;
}

export async function authenticate(endpoint, credentials) {
  let result;
  if (endpoint === "register") {
    await apiRequest("/api/auth/register", { method: "POST", body: credentials });
    result = await apiRequest("/api/auth/login", {
      method: "POST",
      body: { email: credentials.email, password: credentials.password },
    });
  } else {
    result = await apiRequest(`/api/auth/${endpoint}`, { method: "POST", body: credentials });
  }
  setToken(result.access_token);
  return result.user;
}
