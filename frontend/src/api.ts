// Thin API client for the FastAPI backend. Same-origin paths in dev are proxied
// by Vite (see vite.config.ts); set VITE_API_BASE for a different host.

const BASE = import.meta.env.VITE_API_BASE ?? "";
const TOKEN_KEY = "ainl_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent("ainl:unauthorized"));
    throw new ApiError(401, "Unauthorized");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  put: <T>(p: string, b?: unknown) => request<T>("PUT", p, b ?? {}),
};

// ---- Types ----
export type StageState = "pending" | "active" | "done" | "failed";
export interface Stage {
  key: string;
  label: string;
  state: StageState;
}
export type RunState = "running" | "awaiting_review" | "completed" | "rejected" | "failed" | "pending";

export interface WorkflowStatus {
  workflow_run_id: string;
  newsletter_id: string | null;
  current_step: string | null;
  approval_status: string | null;
  publish_status: string | null;
  review_session_id: string | null;
  errors: string[];
  next: string[];
  paused: boolean;
  run_state: RunState;
  progress_percent: number;
  current_stage: string | null;
  stages: Stage[];
}

export interface StartResponse {
  workflow_run_id: string;
  newsletter_id: string;
  issue_number: number;
  run_state: RunState;
  paused: boolean;
}

export interface RunListItem {
  workflow_run_id: string;
  newsletter_id: string | null;
  issue_number: number | null;
  title: string | null;
  newsletter_status: string | null;
  run_state: RunState | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ConfigField {
  key: string;
  label: string;
  type: "string" | "secret" | "bool" | "number" | "select";
  group: string;
  help: string;
  options: string[];
}
export interface ConfigPayload {
  fields: ConfigField[];
  values: Record<string, unknown>;
  secret_set: Record<string, boolean>;
}

export interface NewsletterDraft {
  id: string;
  newsletter_id: string;
  content: Record<string, unknown> | null;
}

// ---- Calls ----
export const Auth = {
  config: () => api.get<{ auth_required: boolean }>("/api/auth/config"),
  login: (token: string) => api.post<{ ok: boolean; auth_required: boolean }>("/api/auth/login", { token }),
  verify: () => api.get<{ ok: boolean }>("/api/auth/verify"),
};

export const Workflows = {
  list: () => api.get<RunListItem[]>("/api/workflows"),
  start: () => api.post<StartResponse>("/api/workflows/newsletter/start"),
  status: (id: string) => api.get<WorkflowStatus>(`/api/workflows/${id}/status`),
  state: (id: string) => api.get<{ state: Record<string, unknown> }>(`/api/workflows/${id}/state`),
  review: (id: string, approval_status: string, feedback_text?: string) =>
    api.post<WorkflowStatus>(`/api/workflows/${id}/review`, {
      approval_status,
      feedback_items: feedback_text ? [{ feedback_type: "general", feedback_text }] : [],
    }),
};

export const Settings = {
  get: () => api.get<ConfigPayload>("/api/settings"),
  update: (updates: Record<string, unknown>) => api.put<ConfigPayload & { changed: string[] }>("/api/settings", updates),
};

export const Newsletters = {
  get: (id: string) => api.get<NewsletterDraft>(`/api/newsletters/${id}`),
};

export const Sources = {
  seed: () => api.post<{ created: number; message: string }>("/api/sources/seed"),
};
