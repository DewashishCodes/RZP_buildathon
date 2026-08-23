const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export function runBatch(nCases: number, seed: number | null): Promise<RunBatchResponse> {
  return apiFetch<RunBatchResponse>("/batches/run", {
    method: "POST",
    body: JSON.stringify({ n_cases: nCases, seed }),
  });
}

export function getBatchSummary(batchId: string): Promise<BatchSummary> {
  return apiFetch<BatchSummary>(`/batches/${batchId}/summary`);
}

export function listCases(params: { batchId?: string; status?: string; type?: string }): Promise<CaseSummary[]> {
  const q = new URLSearchParams();
  if (params.batchId) q.set("batch_id", params.batchId);
  if (params.status) q.set("status", params.status);
  if (params.type) q.set("type", params.type);
  const qs = q.toString();
  return apiFetch<CaseSummary[]>(`/cases${qs ? `?${qs}` : ""}`);
}

export function getCaseTimeline(caseId: string): Promise<CaseTimeline> {
  return apiFetch<CaseTimeline>(`/cases/${caseId}`);
}
