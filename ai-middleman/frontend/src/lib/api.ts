const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Bypasses ngrok's free-tier browser-warning interstitial page, which
// otherwise replaces every API response with an HTML page when the request
// carries a normal browser User-Agent (harmless no-op against non-ngrok hosts).
const NGROK_BYPASS_HEADERS = { "ngrok-skip-browser-warning": "true" };

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: NGROK_BYPASS_HEADERS });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...NGROK_BYPASS_HEADERS },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export type AnalyticsSummary = {
  total_contacts: number;
  vip_contacts: number;
  avg_relationship_strength: number;
  sectors_covered: number;
};

export type SectorStat = { name: string; value: number };
export type LocationStat = { name: string; value: number };
export type ScatterPoint = { x: number; y: number; sector: string };
export type SkillStat = { name: string; count: number };
export type SeniorityStat = { name: string; value: number };
export type StrengthBucket = { level: number; value: number };
export type VipSlice = { name: string; value: number };

export type ContactRow = {
  id: number;
  full_name: string;
  title: string | null;
  company: string | null;
  sector: string | null;
  location: string | null;
  seniority: string | null;
  relationship_strength: number | null;
  is_vip: boolean;
  intros_made: number | null;
};

export type ContactsPage = {
  items: ContactRow[];
  total: number;
  page: number;
  page_size: number;
};

export type ContactDetail = {
  contact: Record<string, unknown>;
  recent_matches: { confidence: number; reasoning: string; created_at: string; message_text: string }[];
};

export type FilterOptions = { sectors: string[]; locations: string[]; seniorities: string[] };

export type ActivityEvent = {
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
  sender_number: string;
};

export type MatchResult = {
  analysis: string;
  matches: { contact_id: number; name: string; role: string; confidence: number; reasoning: string }[];
  match_quality: "good" | "weak" | "none";
  clarification_question?: string;
};

export type ThreadEvent = {
  id: number;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
};

export type PipelineEvent = {
  id: number;
  ts: number;
  stage: string;
  message: string;
  meta: Record<string, unknown>;
};

export const api = {
  analyticsSummary: () => request<AnalyticsSummary>("/api/analytics/summary"),
  analyticsSectors: () => request<SectorStat[]>("/api/analytics/sectors"),
  analyticsLocations: (limit = 10) => request<LocationStat[]>(`/api/analytics/locations?limit=${limit}`),
  analyticsScatter: (limit = 500) => request<ScatterPoint[]>(`/api/analytics/scatter?limit=${limit}`),
  analyticsDealsBySector: () => request<SectorStat[]>("/api/analytics/deals-by-sector"),
  analyticsTopSkills: (limit = 8) => request<SkillStat[]>(`/api/analytics/top-skills?limit=${limit}`),
  analyticsSeniority: () => request<SeniorityStat[]>("/api/analytics/seniority"),
  analyticsStrengthDistribution: () => request<StrengthBucket[]>("/api/analytics/strength-distribution"),
  analyticsVipBreakdown: () => request<VipSlice[]>("/api/analytics/vip-breakdown"),
  filterOptions: () => request<FilterOptions>("/api/filters/options"),
  activity: (limit = 10) => request<ActivityEvent[]>(`/api/activity?limit=${limit}`),
  contacts: (params: {
    search?: string; sector?: string; location?: string; seniority?: string;
    vip?: boolean; page?: number; pageSize?: number;
  }) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.sector) q.set("sector", params.sector);
    if (params.location) q.set("location", params.location);
    if (params.seniority) q.set("seniority", params.seniority);
    if (params.vip) q.set("vip", "true");
    q.set("page", String(params.page ?? 1));
    q.set("page_size", String(params.pageSize ?? 50));
    return request<ContactsPage>(`/api/contacts?${q.toString()}`);
  },
  contact: (id: number) => request<ContactDetail>(`/api/contacts/${id}`),
  match: (query: string) => post<MatchResult>("/match", { query }),
  friendThread: () => request<{ thread_id: number; events: ThreadEvent[] }>("/friend/thread"),
  friendSend: (text: string) => post<{ status: string } | { error: string }>("/friend/send", { text }),
  friendSendMedia: async (file: File | Blob, filename: string): Promise<{ status: string } | { error: string }> => {
    const form = new FormData();
    form.append("file", file, filename);
    const res = await fetch(`${API_BASE}/friend/send-media`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`/friend/send-media -> ${res.status}`);
    return res.json();
  },
  pipelineEvents: (since = 0) => request<{ events: PipelineEvent[]; since: number }>(`/pipeline/events?since=${since}`),
  health: () => request<{ status: string }>("/health"),
};
