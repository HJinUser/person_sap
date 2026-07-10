import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import "./App.css";
import { api } from "./api";
import type { DeptRow, EmployeeRisk, FeatureImportance, Report, Summary } from "./api";

const BAND_LABEL: Record<EmployeeRisk["risk_band"], string> = {
  high: "고위험",
  mid: "중위험",
  low: "저위험",
};

function KpiTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  );
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [departments, setDepartments] = useState<DeptRow[]>([]);
  const [employees, setEmployees] = useState<EmployeeRisk[]>([]);
  const [features, setFeatures] = useState<FeatureImportance[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setError(null);
    try {
      const [s, d, e, f] = await Promise.all([
        api.summary(), api.departments(), api.employeesRisk(20), api.features(),
      ]);
      setSummary(s);
      setDepartments(d);
      setEmployees(e);
      setFeatures(f.filter((x) => x.importance > 0).slice(0, 8));
      setReport(await api.latestReport().catch(() => null));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const handleTrain = async () => {
    setBusy("SAP 데이터 수집 및 모델 학습 중… (약 1분)");
    try {
      await api.syncTrain();
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const handleReport = async () => {
    setBusy("AI 리포트 생성 중…");
    try {
      setReport(await api.generateReport());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="layout">
      <header className="header">
        <div>
          <h1>SAP HR Insight</h1>
          <p className="subtitle">SAP HCM 연동 퇴사 위험 예측 · AI 인사 분석</p>
        </div>
        <div className="actions">
          <button onClick={handleTrain} disabled={!!busy}>데이터 동기화 + 재학습</button>
          <button onClick={handleReport} disabled={!!busy || !summary}>AI 리포트 생성</button>
        </div>
      </header>

      {busy && <div className="banner">{busy}</div>}
      {error && (
        <div className="banner banner-error">
          {error} — SAP Mock(8081)과 AI 서비스(8000)가 떠 있는지 확인하세요.
        </div>
      )}

      {summary && (
        <>
          <section className="tiles">
            <KpiTile label="재직 인원" value={summary.active_headcount.toLocaleString()} sub="명" />
            <KpiTile
              label="퇴사 고위험군"
              value={summary.high_risk_count.toLocaleString()}
              sub="명 (위험도 상위 5%)"
            />
            <KpiTile label="평균 위험도" value={(summary.avg_risk * 100).toFixed(1)} sub="%" />
            <KpiTile
              label="모델 성능 (ROC-AUC)"
              value={summary.test_roc_auc.toFixed(3)}
              sub={`${summary.model} · ${summary.trained_at.slice(0, 10)} 학습`}
            />
          </section>

          <section className="charts">
            <div className="card">
              <h2>부서별 평균 퇴사 위험도</h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={departments} margin={{ top: 20, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis
                    dataKey="dept" tickLine={false} axisLine={{ stroke: "var(--baseline)" }}
                    tick={{ fill: "var(--text-muted)", fontSize: 11 }} interval={0} angle={-28}
                    textAnchor="end" height={54}
                  />
                  <YAxis
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} tickLine={false}
                    axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--grid)", opacity: 0.4 }}
                    formatter={(v) => [`${(Number(v) * 100).toFixed(1)}%`, "평균 위험도"]}
                    contentStyle={{
                      background: "var(--surface)", border: "1px solid var(--border)",
                      borderRadius: 8, color: "var(--text-primary)",
                    }}
                  />
                  <Bar dataKey="avg_risk" fill="var(--chart-blue)" barSize={20} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h2>퇴사 위험 요인 (모델 기여도)</h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={features} layout="vertical"
                  margin={{ top: 4, right: 48, left: 24, bottom: 0 }}
                >
                  <CartesianGrid horizontal={false} stroke="var(--grid)" />
                  <XAxis type="number" hide />
                  <YAxis
                    type="category" dataKey="label" width={140} tickLine={false} axisLine={false}
                    tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--grid)", opacity: 0.4 }}
                    formatter={(v) => [Number(v).toFixed(4), "기여도 (ROC-AUC 감소량)"]}
                    contentStyle={{
                      background: "var(--surface)", border: "1px solid var(--border)",
                      borderRadius: 8, color: "var(--text-primary)",
                    }}
                  />
                  <Bar dataKey="importance" fill="var(--chart-aqua)" barSize={16} radius={[0, 4, 4, 0]}>
                    <LabelList
                      dataKey="importance" position="right"
                      formatter={(v: React.ReactNode) => Number(v).toFixed(3)}
                      style={{ fill: "var(--text-muted)", fontSize: 11 }}
                    />
                    {features.map((f) => <Cell key={f.feature} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="card">
            <h2>퇴사 위험 상위 직원 (우선 면담 대상)</h2>
            <table>
              <thead>
                <tr>
                  <th>사번</th><th>이름</th><th>부서</th><th>직급</th>
                  <th className="num">근속(년)</th><th className="num">월평균 잔업(h)</th>
                  <th className="num">인상 후(년)</th><th className="num">최근 평가</th>
                  <th className="num">위험도</th><th>등급</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((e) => (
                  <tr key={e.pernr}>
                    <td className="mono">{e.pernr}</td>
                    <td>{e.name}</td>
                    <td>{e.dept}</td>
                    <td>{e.position}</td>
                    <td className="num">{e.tenure_years.toFixed(1)}</td>
                    <td className="num">{e.ot_avg_6m.toFixed(0)}</td>
                    <td className="num">{e.years_since_raise.toFixed(1)}</td>
                    <td className="num">{e.last_score.toFixed(0)}점</td>
                    <td className="num strong">{(e.risk * 100).toFixed(0)}%</td>
                    <td>
                      <span className={`band band-${e.risk_band}`}>
                        {BAND_LABEL[e.risk_band]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <div className="report-head">
              <h2>AI 인사 분석 리포트</h2>
              {report && (
                <span className="engine">
                  엔진: {report.engine === "claude" ? "Claude AI" : "규칙 기반 분석"} ·{" "}
                  {report.generated_at.slice(0, 16).replace("T", " ")}
                </span>
              )}
            </div>
            {report ? (
              <div className="report-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.markdown}</ReactMarkdown>
              </div>
            ) : (
              <p className="empty">아직 생성된 리포트가 없습니다. [AI 리포트 생성] 버튼을 눌러주세요.</p>
            )}
          </section>
        </>
      )}

      {!summary && !error && <div className="banner">데이터를 불러오는 중…</div>}

      <footer className="footer">
        데이터: SAP HCM 스타일 합성 데이터 (OData v2로 수집) · 예측은 참고용이며 실제 인사
        의사결정에는 정성 판단을 병행해야 합니다.
      </footer>
    </div>
  );
}
