const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Merchant {
  id: string;
  name: string;
  slug: string;
}

export interface RootCauseBreakdown {
  at_risk: number;
  recovered: number;
  recovery_rate: number;
}

export interface BatchSummary {
  batch_id: string;
  total_cases: number;
  total_at_risk: number;
  total_recovered: number;
  recovery_rate: number;
  by_root_cause: Record<string, RootCauseBreakdown>;
  status_counts: Record<string, number>;
  stopping_rule_triggers: number;
  compliance_substitutions: number;
}

export interface RunBatchResponse {
  batch_id: string;
  n_customers: number;
  n_cases: number;
  summary: BatchSummary;
}

export interface CaseSummary {
  id: string;
  type: string;
  customer_id: string;
  amount: number;
  currency: string;
  created_at: string;
  due_at: string | null;
  status: string;
  raw_failure_reason: string | null;
  root_cause: string | null;
  outcome: string;
  recovered_amount: number;
  disputed: boolean;
  batch_id: string | null;
  merchant_id: string | null;
  next_action_at: string | null;
}

export interface AuditEvent {
  id: string;
  attempt_id: string | null;
  timestamp: string;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
}

export interface Attempt {
  id: string;
  timestamp: string;
  channel: string;
  action: string;
  compliance_check: Record<string, unknown>;
  outcome: string;
  promise_to_pay_date: string | null;
  transcript: string | null;
}

export interface CaseTimeline {
  case: CaseSummary;
  events: AuditEvent[];
  attempts: Attempt[];
}

export interface Ticket {
  id: string;
  case_id: string;
  merchant_id: string | null;
  created_at: string;
  subject: string;
  priority: string;
  status: string;
  assignee: string;
  reason: string;
}

export interface RunDueJobsResponse {
  processed: number;
  reached_terminal: number;
  rescheduled: number;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export function listMerchants(): Promise<Merchant[]> {
  return apiFetch<Merchant[]>("/merchants");
}

export function runBatch(params: {
  merchantId: string;
  nCases: number;
  seed: number | null;
  instant?: boolean;
}): Promise<RunBatchResponse> {
  return apiFetch<RunBatchResponse>("/batches/run", {
    method: "POST",
    body: JSON.stringify({
      merchant_id: params.merchantId,
      n_cases: params.nCases,
      seed: params.seed,
      instant: params.instant ?? true,
    }),
  });
}

export function getBatchSummary(batchId: string): Promise<BatchSummary> {
  return apiFetch<BatchSummary>(`/batches/${batchId}/summary`);
}

export function listCases(params: {
  batchId?: string;
  merchantId?: string;
  status?: string;
  type?: string;
}): Promise<CaseSummary[]> {
  const q = new URLSearchParams();
  if (params.batchId) q.set("batch_id", params.batchId);
  if (params.merchantId) q.set("merchant_id", params.merchantId);
  if (params.status) q.set("status", params.status);
  if (params.type) q.set("type", params.type);
  const qs = q.toString();
  return apiFetch<CaseSummary[]>(`/cases${qs ? `?${qs}` : ""}`);
}

export function listScheduledCases(merchantId: string): Promise<CaseSummary[]> {
  return apiFetch<CaseSummary[]>(`/cases/scheduled?merchant_id=${merchantId}`);
}

export function getCaseTimeline(caseId: string): Promise<CaseTimeline> {
  return apiFetch<CaseTimeline>(`/cases/${caseId}`);
}

export function listTickets(params: { merchantId?: string; status?: string }): Promise<Ticket[]> {
  const q = new URLSearchParams();
  if (params.merchantId) q.set("merchant_id", params.merchantId);
  if (params.status) q.set("status", params.status);
  const qs = q.toString();
  return apiFetch<Ticket[]>(`/tickets${qs ? `?${qs}` : ""}`);
}

export function runDueJobs(merchantId: string): Promise<RunDueJobsResponse> {
  return apiFetch<RunDueJobsResponse>(`/jobs/run-due?merchant_id=${merchantId}`, { method: "POST" });
}
