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

export type AdminUser = User & { is_active: boolean; last_login_at: string | null; created_at: string };

export type Overview = {
  users: number;
  active: number;
  inactive: number;
  pending_requests: number;
  active_last_7_days: number;
  role_counts: Record<string, number>;
};

export type RequestStatus = "pending" | "approved" | "denied" | "cancelled";

export type AccessRequest = {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  user_team: string | null;
  user_roles: string[];
  role: string;
  reason: string;
  status: RequestStatus;
  note: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
};

export type MyRequest = Pick<AccessRequest, "id" | "role" | "reason" | "status" | "note" | "decided_at" | "created_at">;

export type Activity = {
  id: number;
  actor: string | null;
  action: string;
  target: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type Role = { name: string; description: string };
export type AdminRole = Role & { users: number; sources: number; created_at: string };

export type Connector = {
  id: string;
  kind: "slack" | "gitlab";
  name: string;
  enabled: boolean;
  status: "connected" | "error";
  last_error: string | null;
  last_checked_at: string | null;
  last_sync_at: string | null;
  sync_interval_minutes: number;
  sources: number;
  unmapped: number;
  you_can_read: string[];
  config: Record<string, string | null> | null; // admins only
  token_hint: string | null; // admins only
  documents: number;
  syncing: boolean;
  last_run: {
    status: "running" | "ok" | "error";
    trigger: string;
    started_at: string;
    finished_at: string | null;
    seen: number;
    changed: number;
    deleted: number;
    chunks: number;
    error: string | null;
  } | null; // admins only
};

export type NewConnector = { kind: "slack" | "gitlab"; name: string; token: string; url?: string; group?: string };

export type SourceAccess = {
  id: string;
  container_id: string;
  container_name: string;
  container_kind: "public_channel" | "private_channel" | "project";
  allowed_roles: string[];
  discovered_at: string;
};

export type McpServer = {
  id: string;
  kind: string;
  name: string;
  enabled: boolean;
  status: string;
  tools: { id: string; name: string; description: string; enabled: boolean; allowed_roles: string[]; you_can_use: boolean }[];
};

export type UsageTotals = { questions: number; tokens: number; cost_usd: number; avg_seconds: number; not_found: number };

export type Usage = {
  today: UsageTotals;
  last_7_days: UsageTotals;
  all_time: UsageTotals;
  top_users: { name: string; questions: number; tokens: number; cost_usd: number }[];
  recent: {
    id: number;
    user: string | null;
    question: string;
    found: boolean;
    sources: number;
    tokens: number;
    cost_usd: number;
    seconds: number;
    trace_url: string | null;
    created_at: string;
  }[];
};

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
      message = typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg ?? JSON.stringify(body.detail);
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const api = {
  login: (email: string, password: string) => request<{ user: User }>("/auth/login", json("POST", { email, password })),
  signup: (name: string, email: string, password: string) =>
    request<{ user: User }>("/auth/signup", json("POST", { name, email, password })),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
  ask: (question: string) => request<AskResponse>("/ask", json("POST", { question })),

  updateProfile: (changes: { name: string; title: string | null; team: string | null }) =>
    request<User>("/account/profile", json("PATCH", changes)),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/account/password", json("POST", { current_password, new_password })),
  myRequests: () => request<MyRequest[]>("/account/requests"),
  requestRole: (role: string, reason: string) => request<MyRequest>("/account/requests", json("POST", { role, reason })),
  cancelRequest: (id: string) => request<void>(`/account/requests/${id}`, { method: "DELETE" }),

  overview: () => request<Overview>("/admin/overview"),
  users: () => request<AdminUser[]>("/admin/users"),
  roles: () => request<Role[]>("/roles"),
  adminRoles: () => request<AdminRole[]>("/admin/roles"),
  addRole: (name: string, description: string) => request<AdminRole>("/admin/roles", json("POST", { name, description })),
  editRole: (name: string, description: string) => request<AdminRole>(`/admin/roles/${name}`, json("PATCH", { description })),
  deleteRole: (name: string) => request<void>(`/admin/roles/${name}`, { method: "DELETE" }),

  connectors: () => request<Connector[]>("/connectors"),
  addConnector: (body: NewConnector) => request<Connector>("/admin/connectors", json("POST", body)),
  editConnector: (id: string, changes: Partial<{ name: string; enabled: boolean; sync_interval_minutes: number; token: string }>) =>
    request<Connector>(`/admin/connectors/${id}`, json("PATCH", changes)),
  removeConnector: (id: string) => request<void>(`/admin/connectors/${id}`, { method: "DELETE" }),
  checkConnector: (id: string) => request<Connector>(`/admin/connectors/${id}/check`, { method: "POST" }),
  syncConnector: (id: string) => request<{ started: boolean }>(`/admin/connectors/${id}/sync`, { method: "POST" }),
  access: (connectorId: string) => request<SourceAccess[]>(`/admin/connectors/${connectorId}/access`),
  editAccess: (id: string, allowed_roles: string[]) => request<SourceAccess>(`/admin/access/${id}`, json("PATCH", { allowed_roles })),
  mcp: () => request<McpServer[]>("/mcp"),
  updateUser: (id: string, changes: Partial<Pick<AdminUser, "roles" | "is_active">>) =>
    request<AdminUser>(`/admin/users/${id}`, json("PATCH", changes)),
  requests: (status: "pending" | "decided") => request<AccessRequest[]>(`/admin/requests?status=${status}`),
  decide: (id: string, approve: boolean, note: string | null) =>
    request<AccessRequest>(`/admin/requests/${id}/decision`, json("POST", { approve, note })),
  usage: () => request<Usage>("/admin/usage"),
  activity: (limit = 100) => request<Activity[]>(`/admin/activity?limit=${limit}`),
};
