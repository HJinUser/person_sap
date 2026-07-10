# -*- coding: utf-8 -*-
"""
피처 엔지니어링 — 시점 기준(point-in-time) 방식
================================================
퇴사 예측에서 가장 흔한 실수는 데이터 누수(leakage):
퇴사자의 피처를 "지금" 기준으로 계산하면, 퇴사 후에 생긴 정보
(예: 퇴사해서 잔업이 0이 된 것)가 학습에 섞여 성능이 부풀려진다.

그래서 기준일(ref_date)을 사람마다 다르게 잡는다:
  - 퇴사자: 퇴사일(Terdt) 직전까지의 데이터만 사용
  - 재직자: 스냅샷 기준일(CUTOFF_DATE)까지의 데이터 사용

이렇게 하면 모델은 "퇴사 직전 N개월의 모습"과 "재직자의 현재 모습"을
같은 조건으로 비교하게 된다.
"""
import logging

import pandas as pd

from .config import CUTOFF_DATE

logger = logging.getLogger(__name__)

# 학습에 사용할 피처 정의 (범주형 / 수치형)
CATEGORICAL_FEATURES = ["dept", "position", "gender"]
NUMERIC_FEATURES = [
    "age", "tenure_years", "salary_now", "salary_growth_1y", "years_since_raise",
    "pay_vs_peer", "ot_avg_6m", "ot_trend", "sick_days_12m", "leave_days_12m",
    "last_score", "score_trend",
]
LABEL = "attrited"

# 대시보드/리포트 표시용 한글 피처명
FEATURE_LABELS = {
    "age": "나이", "tenure_years": "근속연수", "salary_now": "현재 급여",
    "salary_growth_1y": "최근 1년 급여 인상률", "years_since_raise": "마지막 인상 후 경과년수",
    "pay_vs_peer": "동일 직급 대비 급여 수준", "ot_avg_6m": "최근 6개월 평균 잔업",
    "ot_trend": "잔업 증감 추세", "sick_days_12m": "최근 1년 병가일수",
    "leave_days_12m": "최근 1년 연차일수", "last_score": "최근 평가점수",
    "score_trend": "평가점수 추세", "dept": "부서", "position": "직급", "gender": "성별",
}


def build_features(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """OData로 수집한 5개 테이블을 조인해 사원별 피처 테이블을 만든다."""
    emp = data["employees"].copy()
    cutoff = pd.Timestamp(CUTOFF_DATE)

    # 날짜형 변환
    emp["Gbdat"] = pd.to_datetime(emp["Gbdat"])
    emp["Hidat"] = pd.to_datetime(emp["Hidat"])
    emp["Terdt"] = pd.to_datetime(emp["Terdt"].replace("", pd.NA))

    sal = data["salaries"].copy()
    sal["Begda"] = pd.to_datetime(sal["Begda"])
    sal["Endda"] = pd.to_datetime(sal["Endda"].replace("9999-12-31", "2262-01-01"))
    sal["Bet01"] = sal["Bet01"].astype(float)

    ot = data["overtime"].copy()
    ot["month"] = pd.to_datetime(ot["Zmonth"] + "-01")
    ot["Othrs"] = ot["Othrs"].astype(float)

    ab = data["absences"].copy()
    ab["Begda"] = pd.to_datetime(ab["Begda"])
    ab["Abwtg"] = ab["Abwtg"].astype(int)

    ap = data["appraisals"].copy()
    ap["Zyear"] = ap["Zyear"].astype(int)
    ap["Score"] = ap["Score"].astype(int)

    # 사번별로 미리 그룹화 (조회 성능)
    sal_by_emp = dict(tuple(sal.groupby("Pernr")))
    ot_by_emp = dict(tuple(ot.groupby("Pernr")))
    ab_by_emp = dict(tuple(ab.groupby("Pernr")))
    ap_by_emp = dict(tuple(ap.groupby("Pernr")))

    rows = []
    for e in emp.itertuples(index=False):
        attrited = e.Stat2 == "0"
        if attrited:
            ref = e.Terdt  # 퇴사자: 퇴사일 기준
        else:
            # 재직자: 최근 1년 내 무작위 시점 기준 (사번 기반 결정적 샘플링).
            # 전원을 스냅샷 기준일로 고정하면 "3월 일괄 인상 직후"라는 시점
            # 특성이 재직자에게만 공통으로 생겨, 모델이 인과 요인이 아니라
            # 관측 시점의 차이를 학습하는 편향(class-conditional artifact)이 생긴다.
            offset_days = (int(e.Pernr) * 2654435761) % 365
            ref = cutoff - pd.Timedelta(days=offset_days)
            ref = max(ref, e.Hidat)  # 입사 전 시점이 되지 않도록 보정

        row: dict = {
            "pernr": e.Pernr,
            "name": e.Ename,
            "dept": e.OrgehTxt,
            "position": e.PlansTxt,
            "gender": "남" if e.Gesch == "1" else "여",
            "age": (ref - e.Gbdat).days / 365.25,
            "tenure_years": (ref - e.Hidat).days / 365.25,
            LABEL: int(attrited),
        }

        # ── 급여: 기준일에 유효한 레코드 / 1년 전 레코드 / 마지막 인상 시점 ──
        s = sal_by_emp.get(e.Pernr)
        salary_now, salary_1y_ago, years_since_raise = 0.0, None, row["tenure_years"]
        if s is not None:
            cur = s[(s["Begda"] <= ref) & (s["Endda"] >= ref)]
            if not cur.empty:
                cur_row = cur.iloc[0]
                salary_now = cur_row["Bet01"]
                # 현재 급여 레코드의 시작일 = 마지막 인상일 (입사일과 같으면 인상 이력 없음)
                years_since_raise = (ref - cur_row["Begda"]).days / 365.25
            ago = ref - pd.Timedelta(days=365)
            past = s[(s["Begda"] <= ago) & (s["Endda"] >= ago)]
            if not past.empty:
                salary_1y_ago = past.iloc[0]["Bet01"]
        row["salary_now"] = salary_now
        row["salary_growth_1y"] = (
            (salary_now - salary_1y_ago) / salary_1y_ago if salary_1y_ago else 0.0
        )
        row["years_since_raise"] = years_since_raise

        # ── 잔업: 기준일 직전 6개월 평균 + 최근 3개월 vs 그 이전 3개월 추세 ──
        o = ot_by_emp.get(e.Pernr)
        ot_avg_6m, ot_trend = 0.0, 0.0
        if o is not None:
            w6 = o[(o["month"] >= ref - pd.DateOffset(months=6)) & (o["month"] < ref)]
            if not w6.empty:
                ot_avg_6m = w6["Othrs"].mean()
                recent = w6[w6["month"] >= ref - pd.DateOffset(months=3)]["Othrs"].mean()
                earlier = w6[w6["month"] < ref - pd.DateOffset(months=3)]["Othrs"].mean()
                if pd.notna(recent) and pd.notna(earlier):
                    ot_trend = recent - earlier
        row["ot_avg_6m"] = ot_avg_6m
        row["ot_trend"] = ot_trend

        # ── 근태: 최근 12개월 병가/연차 일수 ──
        a = ab_by_emp.get(e.Pernr)
        sick, leave = 0, 0
        if a is not None:
            w12 = a[(a["Begda"] >= ref - pd.DateOffset(months=12)) & (a["Begda"] < ref)]
            sick = int(w12[w12["Awart"] == "0200"]["Abwtg"].sum())
            leave = int(w12[w12["Awart"] == "0100"]["Abwtg"].sum())
        row["sick_days_12m"] = sick
        row["leave_days_12m"] = leave

        # ── 평가: 기준일 이전의 최근 점수 + 추세 (최근 - 최초) ──
        p = ap_by_emp.get(e.Pernr)
        last_score, score_trend = 3.0, 0.0
        if p is not None:
            valid = p[p["Zyear"] < ref.year + 1].sort_values("Zyear")
            if not valid.empty:
                last_score = float(valid.iloc[-1]["Score"])
                if len(valid) >= 2:
                    score_trend = float(valid.iloc[-1]["Score"] - valid.iloc[0]["Score"])
        row["last_score"] = last_score
        row["score_trend"] = score_trend

        rows.append(row)

    df = pd.DataFrame(rows)

    # ── 동일 (부서, 직급) 그룹 중위 급여 대비 수준 ──
    peer_median = df.groupby(["dept", "position"])["salary_now"].transform("median")
    df["pay_vs_peer"] = (df["salary_now"] / peer_median).fillna(1.0)

    logger.info("피처 테이블 생성: %d명 × %d개 피처 (퇴사율 %.1f%%)",
                len(df), len(CATEGORICAL_FEATURES) + len(NUMERIC_FEATURES),
                df[LABEL].mean() * 100)
    return df
