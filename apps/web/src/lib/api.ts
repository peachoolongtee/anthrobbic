import { API_URL } from "@/lib/env";
import type {
  Cause,
  DecisionResult,
  Evaluation,
  Run,
  RunLog,
  RunMode,
  RunOverrides,
  ScenarioSummary,
  SignoffRequest,
  SignoffResult,
  StateChange,
  VerifyResult,
} from "@/lib/api-types";
import { mockBackend } from "@/lib/mock/backend";

/**
 * "mock" serves fixtures from the browser. Anything else talks to the API at
 * NEXT_PUBLIC_API_URL. The value is inlined at build time.
 */
export const IS_MOCK = process.env.NEXT_PUBLIC_API_MODE === "mock";

export class ApiError extends Error {
  /** "unreachable" means no HTTP response arrived at all. */
  readonly kind: "unreachable" | "http";
  readonly status: number | null;

  constructor(kind: "unreachable" | "http", message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("unreachable", "No response from the planning service.", null);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the status text
    }
    throw new ApiError("http", detail || `Request failed (${res.status})`, res.status);
  }
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return http<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export const api = {
  listScenarios(params: { cause?: Cause; limit?: number } = {}): Promise<ScenarioSummary[]> {
    if (IS_MOCK) return mockBackend.listScenarios(params);
    const q = new URLSearchParams();
    if (params.cause) q.set("cause", params.cause);
    if (params.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return http<ScenarioSummary[]>(`/scenarios${qs ? `?${qs}` : ""}`);
  },

  createRun(body: {
    scenario_id: string;
    mode: RunMode;
    overrides?: RunOverrides;
  }): Promise<Run> {
    if (IS_MOCK) return mockBackend.createRun(body);
    return post<Run>("/runs", body);
  },

  /** (addition) Change the airport state of an existing run, after it was shown. */
  changeState(runId: string, change: StateChange): Promise<{ state_version: string }> {
    if (IS_MOCK) return mockBackend.changeState(runId, change);
    return post(`/runs/${encodeURIComponent(runId)}/state`, change);
  },

  signoff(runId: string, body: SignoffRequest): Promise<SignoffResult> {
    if (IS_MOCK) return mockBackend.signoff(runId, body);
    return post<SignoffResult>(`/runs/${encodeURIComponent(runId)}/signoff`, body);
  },

  /** Records a rejection. Issues nothing. The reason is stored as unverified. */
  reject(runId: string, body: { decided_by: string; reason?: string }): Promise<DecisionResult> {
    if (IS_MOCK) return mockBackend.reject(runId, body);
    return post<DecisionResult>(`/runs/${encodeURIComponent(runId)}/reject`, body);
  },

  /** Records that the duty manager has a no-deal case. The note is stored as unverified. */
  takeOver(runId: string, body: { decided_by: string; note?: string }): Promise<DecisionResult> {
    if (IS_MOCK) return mockBackend.takeOver(runId, body);
    return post<DecisionResult>(`/runs/${encodeURIComponent(runId)}/take-over`, body);
  },

  getLog(runId: string): Promise<RunLog> {
    if (IS_MOCK) return mockBackend.getLog(runId);
    return http<RunLog>(`/runs/${encodeURIComponent(runId)}/log`);
  },

  verifyLog(runId: string, body: { tamper?: boolean } = {}): Promise<VerifyResult> {
    if (IS_MOCK) return mockBackend.verifyLog(runId, body);
    return post<VerifyResult>(`/runs/${encodeURIComponent(runId)}/log/verify`, body);
  },

  getEvaluation(): Promise<Evaluation> {
    if (IS_MOCK) return mockBackend.getEvaluation();
    return http<Evaluation>("/evaluation");
  },
};

export function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return err instanceof Error ? err.message : "Something went wrong";
}

export function isUnreachable(err: unknown): boolean {
  return err instanceof ApiError && err.kind === "unreachable";
}
