// AI 서비스 API 클라이언트
const BASE = "http://127.0.0.1:8000/api";

export interface Summary {
  active_headcount: number;
  high_risk_count: number;
  avg_risk: number;
  model: string;
  test_roc_auc: number;
  trained_at: string;
}

export interface DeptRow {
  dept: string;
  headcount: number;
  avg_risk: number;
  high_risk: number;
  avg_ot: number;
}

export interface EmployeeRisk {
  pernr: string;
  name: string;
  dept: string;
  position: string;
  tenure_years: number;
  ot_avg_6m: number;
  years_since_raise: number;
  last_score: number;
  risk: number;
  risk_band: "high" | "mid" | "low";
}

export interface FeatureImportance {
  feature: string;
  label: string;
  importance: number;
}

export interface Report {
  generated_at: string;
  engine: "claude" | "rule-based";
  markdown: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  summary: () => get<Summary>("/summary"),
  departments: () => get<DeptRow[]>("/departments"),
  employeesRisk: (limit = 20) => get<EmployeeRisk[]>(`/employees/risk?limit=${limit}`),
  features: () => get<FeatureImportance[]>("/model/features"),
  latestReport: () => get<Report>("/report/latest"),
  syncTrain: () => post<{ message: string }>("/sync-train"),
  generateReport: () => post<Report>("/report/generate"),
};
