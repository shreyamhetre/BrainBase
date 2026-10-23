// Calls to the GitMore backend. Requests go to /api/..., which next.config.ts forwards
// to FastAPI. The login token travels in an httpOnly cookie that scripts can't read.

export type User = {
  id: string;
  email: string;
  name: string;
  roles: string[];
  is_admin: boolean;
  team: string | null;
  title: string | null;
};

export type AdminUser = User & { is_active: boolean; last_login_at: string | null };

export type Source = {
  number: number;
  source: string;
  title: string;
  heading_path: string;
  link: string;
  cited: boolean;
  updated_at: string | null;
  status: string | null;
};

export type AskResponse = {
  answer: string;
  sources: Source[];
  prompt_tokens: number;
  completion_tokens: number;
  seconds: number;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
    credentials: "same-origin",
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ user: User }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  signup: (name: string, email: string, password: string) =>
    request<{ user: User }>("/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
  ask: (question: string) =>
    request<AskResponse>("/ask", { method: "POST", body: JSON.stringify({ question }) }),
  users: () => request<AdminUser[]>("/admin/users"),
  roles: () => request<string[]>("/admin/roles"),
  updateUser: (id: string, changes: Partial<Pick<AdminUser, "roles" | "is_admin" | "is_active">>) =>
    request<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
};
