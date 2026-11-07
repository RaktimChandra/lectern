import type { FixPreview, Health, Lesson, LessonRequest, LessonSummary, StepName } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Lectern's server is not reachable. Check that it is running.", 0);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/health"),
  lessons: () => request<LessonSummary[]>("/lessons"),
  lesson: (id: string) => request<Lesson>(`/lessons/${id}`),
  create: (body: LessonRequest) => post<Lesson>("/lessons", body),
  remove: (id: string) => request<void>(`/lessons/${id}`, { method: "DELETE" }),
  run: (id: string, from_step?: StepName) => post<Lesson>(`/lessons/${id}/run`, { from_step: from_step ?? null }),
  recheck: (id: string, layer: "facts" | "instruction" | "both") => post<Lesson>(`/lessons/${id}/qc/${layer}`),
  source: (id: string, sid: string) =>
    request<{ passages: { id: string; text: string }[] } & Record<string, unknown>>(`/lessons/${id}/sources/${sid}`),
  editSection: (id: string, sid: string, body: { base_version: number; body_md: string; title?: string; minutes?: number; instructor_notes?: string }) =>
    put<Lesson>(`/lessons/${id}/sections/${sid}`, body),
  editCheck: (id: string, kid: string, body: { base_version: number; question: string; options: string[]; answer_index: number; explanation: string }) =>
    put<Lesson>(`/lessons/${id}/checks/${kid}`, body),
  preview: (id: string, iid: string) => post<FixPreview>(`/lessons/${id}/issues/${iid}/preview`),
  apply: (id: string, iid: string, body: { base_version: number; after?: string | null; check?: unknown }) =>
    post<Lesson>(`/lessons/${id}/issues/${iid}/apply`, body),
  dismiss: (id: string, iid: string, reason?: string) => post<Lesson>(`/lessons/${id}/issues/${iid}/dismiss`, { reason }),
  reopen: (id: string, iid: string) => post<Lesson>(`/lessons/${id}/issues/${iid}/reopen`),
  applyExact: (id: string, base_version: number) => post<Lesson & { applied: string[] }>(`/lessons/${id}/apply-exact`, { base_version }),
  version: (id: string, n: number) => request<{ number: number; reason: string; created_at: string; content: import("./types").LessonContent }>(`/lessons/${id}/versions/${n}`),
  restore: (id: string, n: number, base_version: number) => post<Lesson>(`/lessons/${id}/versions/${n}/restore`, { base_version }),
  exportUrl: (id: string, format: "md" | "html" | "json" | "zip") => `/api/lessons/${id}/export?format=${format}`,
};
