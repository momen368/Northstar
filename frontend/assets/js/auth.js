import { apiRequest, clearToken, getToken } from "./api.js";
import { showNotice } from "./dom.js";

export async function requireAuth() {
  if (!getToken()) { window.location.replace("/login.html"); return null; }
  try { return await apiRequest("/api/auth/me"); }
  catch (error) { if (getToken()) showNotice(error.message); return null; }
}

export async function logout() {
  try { await apiRequest("/api/auth/logout", { method: "POST" }); } catch { /* Clear local auth if offline. */ }
  clearToken();
  window.location.assign("/login.html");
}