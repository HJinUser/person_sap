# -*- coding: utf-8 -*-
"""
AI 인사 분석 리포트 생성기
==========================
예측 결과를 '스스로 분석'해서 경영진용 리포트를 만든다. 2단계 구조:

  1단계 (규칙 기반 인사이트 엔진): 예측 결과·피처 분포에서 통계적으로
     의미 있는 사실들을 추출한다 — 부서별 위험 순위, 개인별 위험 요인 태그,
     전사 지표. 이 단계는 외부 의존성이 전혀 없어 항상 동작한다.

  2단계 (LLM 내러티브, 선택): ANTHROPIC_API_KEY가 설정돼 있으면 1단계의
     구조화된 사실을 Claude에게 전달해 자연어 경영 리포트로 변환한다.
     API 키가 없거나 호출이 실패하면 1단계 결과로 만든 규칙 기반
     리포트를 그대로 제공한다 (graceful degradation).
"""
import json
import logging
import os
from datetime import datetime

import pandas as pd

from .config import ARTIFACTS_DIR, CLAUDE_MODEL

logger = logging.getLogger(__name__)


def _reason_tags(row: pd.Series, q: dict) -> list[str]:
    """개인별 위험 요인 태그 (전사 분포 기준 상대 비교)"""
    tags = []
    if row["ot_avg_6m"] >= q["ot_q75"]:
        tags.append(f"잔업 과다 (월 {row['ot_avg_6m']:.0f}h, 상위 25%)")
    if row["ot_trend"] > 3:
        tags.append(f"최근 잔업 급증 (+{row['ot_trend']:.0f}h)")
    if row["years_since_raise"] >= 2:
        tags.append(f"급여 정체 {row['years_since_raise']:.1f}년")
    if row["pay_vs_peer"] < 0.9:
        tags.append(f"동일 직급 대비 급여 {row['pay_vs_peer'] * 100:.0f}% 수준")
    if row["score_trend"] < 0:
        tags.append("평가점수 하락 추세")
    if row["last_score"] <= 2:
        tags.append(f"최근 평가 저조 ({row['last_score']:.0f}점)")
    if row["sick_days_12m"] >= 3:
        tags.append(f"병가 증가 (연 {row['sick_days_12m']}일)")
    if row["tenure_years"] < 2:
        tags.append("입사 2년 미만 (조기 이탈 구간)")
    return tags


def build_insights() -> dict:
    """1단계: 예측 산출물에서 구조화된 인사이트 추출"""
    pred = pd.read_csv(ARTIFACTS_DIR / "predictions.csv", dtype={"pernr": str})
    metrics = json.loads((ARTIFACTS_DIR / "metrics.json").read_text(encoding="utf-8"))
    importance = json.loads(
        (ARTIFACTS_DIR / "feature_importance.json").read_text(encoding="utf-8"))

    q = {"ot_q75": pred["ot_avg_6m"].quantile(0.75)}

    # 부서별 요약 (평균 위험도 내림차순)
    dept = (
        pred.groupby("dept")
        .agg(headcount=("pernr", "count"), avg_risk=("risk", "mean"),
             high_risk=("risk_band", lambda s: int((s == "high").sum())),
             avg_ot=("ot_avg_6m", "mean"))
        .round(3)
        .sort_values("avg_risk", ascending=False)
        .reset_index()
    )

    # 고위험 개인 상위 10명 + 위험 요인 태그
    top = pred.sort_values("risk", ascending=False).head(10)
    top_individuals = [
        {
            "pernr": r["pernr"], "name": r["name"], "dept": r["dept"],
            "position": r["position"], "risk": round(float(r["risk"]), 3),
            "reasons": _reason_tags(r, q),
        }
        for _, r in top.iterrows()
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "company": {
            "active_headcount": len(pred),
            "avg_risk": round(float(pred["risk"].mean()), 3),
            "high_risk_count": int((pred["risk_band"] == "high").sum()),
            "high_risk_ratio": round(
                float((pred["risk_band"] == "high").mean()), 3),
        },
        "model": {
            "name": metrics["best_model"],
            "test_roc_auc": metrics["test_roc_auc"],
            "test_recall": metrics["test_recall"],
            "trained_at": metrics["trained_at"],
        },
        "top_risk_factors": importance[:5],
        "departments": dept.to_dict(orient="records"),
        "top_individuals": top_individuals,
    }


def _rule_based_report(ins: dict) -> str:
    """2단계 대체 경로: 규칙 기반으로 마크다운 리포트 조립 (API 키 불필요)"""
    c, m = ins["company"], ins["model"]
    lines = [
        f"# 주간 인사 리스크 리포트 ({ins['generated_at'][:10]})",
        "",
        "## 요약",
        f"- 재직 인원 **{c['active_headcount']:,}명** 중 퇴사 고위험군은 "
        f"**{c['high_risk_count']}명({c['high_risk_ratio'] * 100:.1f}%)** 입니다.",
        f"- 예측 모델: {m['name']} (테스트 ROC-AUC {m['test_roc_auc']}, "
        f"재현율 {m['test_recall']})",
        "",
        "## 주요 퇴사 위험 요인 (모델 기여도 순)",
    ]
    for i, f in enumerate(ins["top_risk_factors"], 1):
        lines.append(f"{i}. **{f['label']}** (기여도 {f['importance']})")

    lines += ["", "## 부서별 현황 (위험도 순)", "",
              "| 부서 | 인원 | 평균 위험도 | 고위험 인원 | 평균 잔업(h/월) |",
              "|---|---|---|---|---|"]
    for d in ins["departments"]:
        lines.append(f"| {d['dept']} | {d['headcount']} | {d['avg_risk']:.3f} "
                     f"| {d['high_risk']} | {d['avg_ot']:.1f} |")

    lines += ["", "## 우선 면담 대상 (위험도 상위)"]
    for p in ins["top_individuals"][:5]:
        reasons = ", ".join(p["reasons"]) if p["reasons"] else "복합 요인"
        lines.append(f"- **{p['name']}** ({p['dept']}·{p['position']}, "
                     f"위험도 {p['risk']:.0%}) — {reasons}")

    worst = ins["departments"][0]
    lines += [
        "",
        "## 권고 조치",
        f"- **{worst['dept']}**: 평균 위험도가 가장 높습니다 "
        f"({worst['avg_risk']:.3f}). 잔업 부하와 보상 체계 점검을 권고합니다.",
        "- 고위험군 대상 1:1 면담을 이번 주 내 실시하고, 급여 정체 2년 이상 "
        "인원은 보상 검토 대상에 포함하십시오.",
        "- 본 리포트는 합성 데이터 기반 예측이며, 실제 의사결정에는 "
        "정성적 판단을 병행해야 합니다.",
    ]
    return "\n".join(lines)


def _llm_report(ins: dict) -> str | None:
    """2단계: Claude API로 내러티브 리포트 생성. 실패하면 None 반환."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.info("ANTHROPIC_API_KEY 미설정 — 규칙 기반 리포트로 대체")
        return None
    try:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=(
                "당신은 HR 데이터 분석가입니다. 주어진 퇴사 위험 예측 결과(JSON)를 "
                "바탕으로 경영진용 주간 인사 리스크 리포트를 한국어 마크다운으로 "
                "작성하세요. 구성: 핵심 요약(3줄 이내) → 부서별 진단 → 우선 면담 "
                "대상과 이유 → 구체적 권고 조치. 수치는 JSON에 있는 값만 사용하고 "
                "새로 지어내지 마세요."
            ),
            messages=[{
                "role": "user",
                "content": json.dumps(ins, ensure_ascii=False),
            }],
        )
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text:
            logger.info("Claude 리포트 생성 완료 (%s)", CLAUDE_MODEL)
        return text
    except anthropic.APIConnectionError:
        logger.warning("Claude API 연결 실패 — 규칙 기반 리포트로 대체")
        return None
    except anthropic.APIStatusError as e:
        logger.warning("Claude API 오류(%s) — 규칙 기반 리포트로 대체", e.status_code)
        return None


def generate_report() -> dict:
    """인사이트 추출 → LLM 리포트 시도 → 실패 시 규칙 기반 리포트"""
    ins = build_insights()
    llm_text = _llm_report(ins)
    report = {
        "generated_at": ins["generated_at"],
        "engine": "claude" if llm_text else "rule-based",
        "markdown": llm_text or _rule_based_report(ins),
        "insights": ins,
    }
    (ARTIFACTS_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
