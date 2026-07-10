# -*- coding: utf-8 -*-
"""
SAP HCM 스타일 합성 HR 데이터 생성기
====================================
SAP HR(HCM)의 대표 인포타입 구조를 따르는 CSV 5종을 생성한다.

  employees.csv        PA0000(인사조치) + PA0001(조직배치) 성격의 사원 마스터
  salary_history.csv   PA0008(기본급) 성격의 급여 변경 이력 (기간 유효 레코드)
  overtime.csv         PT(근무시간관리) 성격의 월별 초과근무 집계
  absences.csv         PA2001(결근) 성격의 근태 이벤트
  appraisals.csv       평가 결과 (연 1회)

핵심 설계: 퇴사는 무작위가 아니라 아래 잠재 요인의 함수로 발생시킨다.
  - 초과근무가 많을수록          → 퇴사 확률 ↑
  - 마지막 인상 후 오래됐을수록   → 퇴사 확률 ↑
  - 부서 중위 급여보다 낮을수록   → 퇴사 확률 ↑
  - 평가 점수가 낮거나 하락할수록 → 퇴사 확률 ↑
  - 근속 2년 미만               → 퇴사 확률 ↑ (조기 퇴사 U자 곡선)

이렇게 인과 구조를 명시적으로 주입해 두면, 이후 ML 모델이
이 패턴들을 데이터에서 스스로 복원해 내는지를 검증할 수 있다.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

OUT_DIR = Path(__file__).parent.parent / "data"
CUTOFF = date(2026, 6, 30)          # 데이터 스냅샷 기준일
N_EMPLOYEES = 1200

# ── SAP 조직/직급 코드 체계 ──────────────────────────────────────
DEPARTMENTS = [
    # (ORGEH, 부서명, 인원비중, 기본잔업(h/월), 급여계수)
    ("10001000", "경영지원팀", 0.06, 8,  1.00),
    ("10002000", "인사팀",     0.05, 10, 1.00),
    ("10003000", "재무팀",     0.06, 14, 1.02),
    ("20001000", "영업1팀",    0.13, 22, 1.05),
    ("20002000", "영업2팀",    0.12, 24, 1.05),
    ("30001000", "생산관리팀", 0.18, 28, 0.95),
    ("40001000", "연구개발팀", 0.22, 26, 1.10),
    ("40002000", "IT운영팀",   0.10, 20, 1.08),
    ("20003000", "마케팅팀",   0.08, 16, 1.02),
]

POSITIONS = [
    # (PLANS, 직급명, 최소근속(년), 기본연봉(만원))
    ("50000100", "사원", 0,  3600),
    ("50000200", "대리", 3,  4600),
    ("50000300", "과장", 7,  5800),
    ("50000400", "차장", 12, 7000),
    ("50000500", "부장", 17, 8400),
]

FAMILY_NAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진지엄채원천방공현함변염여추도소석선설마길연위표명기반라왕금옥육인맹제모탁국여어은편용"
GIVEN_SYL = "민서준우지현영수진성호연아윤재원태경은주혜정상미랑도하람빛찬슬기누리결솔한별샘가온"


def rand_name():
    return random.choice(FAMILY_NAMES) + "".join(random.sample(GIVEN_SYL, 2))


def month_range(start: date, end: date):
    """start~end 사이의 매월 1일 목록"""
    cur = date(start.year, start.month, 1)
    while cur <= end:
        yield cur
        cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)


def sigmoid(x):
    import math
    return 1 / (1 + math.exp(-x))


def pick_department():
    r, acc = random.random(), 0.0
    for dept in DEPARTMENTS:
        acc += dept[2]
        if r <= acc:
            return dept
    return DEPARTMENTS[-1]


def position_for_tenure(tenure_years: float):
    eligible = [p for p in POSITIONS if p[2] <= tenure_years]
    # 근속이 되어도 승진 못 한 경우도 섞는다
    idx = min(len(eligible) - 1, max(0, len(eligible) - 1 - (0 if random.random() < 0.7 else 1)))
    return eligible[idx]


def main():
    OUT_DIR.mkdir(exist_ok=True)
    employees, salaries, overtimes, absences, appraisals = [], [], [], [], []

    for i in range(N_EMPLOYEES):
        pernr = f"{10000001 + i}"
        orgeh, dept_name, _, dept_ot, dept_pay = pick_department()
        gender = random.choice(["1", "2"])  # SAP GESCH: 1=남, 2=여

        # 입사일: 2013 ~ 2026-03 사이
        hire = date(2013, 1, 1) + timedelta(days=random.randint(0, (date(2026, 3, 31) - date(2013, 1, 1)).days))
        hire_age = random.randint(24, 34)
        birth = date(hire.year - hire_age, random.randint(1, 12), random.randint(1, 28))
        tenure_at_cutoff = (CUTOFF - hire).days / 365.25
        plans, pos_name, _, base_pay = position_for_tenure(tenure_at_cutoff)

        # ── 개인 성향 파라미터 ──
        ot_factor = max(0.2, random.gauss(1.0, 0.35))          # 잔업 성향
        raise_luck = random.random()                            # 인상 운 (낮으면 급여 정체)
        perf_base = min(5, max(1, random.gauss(3.2, 0.8)))      # 기본 역량

        # ── 급여 이력: 입사 시점 급여에서 매년 인상(또는 동결) ──
        monthly_pay = base_pay * dept_pay / 12 * random.uniform(0.9, 1.1)
        # 입사 시점 급여로 역산 (근속 1년당 약 3% 낮게)
        monthly_pay /= (1.03 ** min(tenure_at_cutoff, 13))
        last_raise_date = hire
        seg_start = hire
        for y in range(hire.year + 1, CUTOFF.year + 1):
            raise_day = date(y, 3, 1)
            if raise_day <= hire or raise_day > CUTOFF:
                continue
            raise_pct = 0.0 if raise_luck < 0.25 and random.random() < 0.6 \
                else random.uniform(0.01, 0.08) * (0.6 + perf_base / 5)
            if raise_pct > 0.005:
                salaries.append([pernr, seg_start.isoformat(), (raise_day - timedelta(days=1)).isoformat(),
                                 round(monthly_pay, 1)])
                monthly_pay *= (1 + raise_pct)
                seg_start, last_raise_date = raise_day, raise_day
        salaries.append([pernr, seg_start.isoformat(), "9999-12-31", round(monthly_pay, 1)])

        years_since_raise = (CUTOFF - last_raise_date).days / 365.25

        # ── 평가 이력 (최근 3년, 하락 추세 개인 존재) ──
        perf_trend = random.choice([0, 0, 0, -0.4, -0.7, +0.3])
        last_scores = []
        for j, y in enumerate([2023, 2024, 2025]):
            if date(y, 12, 31) < hire:
                continue
            score = min(5, max(1, round(perf_base + perf_trend * j + random.gauss(0, 0.4))))
            appraisals.append([pernr, str(y), str(score)])
            last_scores.append(score)

        # ── 퇴사 확률 (잠재 요인 → 시그모이드) ──
        avg_ot = dept_ot * ot_factor
        dept_base_monthly = base_pay * dept_pay / 12
        pay_gap = (monthly_pay - dept_base_monthly) / dept_base_monthly   # 음수면 동급 대비 저임금
        last_score = last_scores[-1] if last_scores else 3
        declining = 1 if (len(last_scores) >= 2 and last_scores[-1] < last_scores[0]) else 0
        early_tenure = 1 if tenure_at_cutoff < 2 else 0

        z = (-2.4
             + 0.045 * (avg_ot - 18)          # 잔업
             + 0.55 * min(years_since_raise, 4)  # 급여 정체
             - 1.8 * pay_gap                   # 동급 대비 급여 격차
             - 0.35 * (last_score - 3)         # 평가
             + 0.5 * declining                 # 평가 하락 추세
             + 0.7 * early_tenure              # 조기 퇴사
             + random.gauss(0, 0.6))           # 노이즈
        p_attrition = sigmoid(z) * 0.85        # 전체 비율 조정

        attrited = random.random() < p_attrition
        if attrited:
            # 퇴사일: 2024-07 ~ 2026-05 사이, 입사 후 최소 6개월
            earliest = max(hire + timedelta(days=180), date(2024, 7, 1))
            if earliest >= date(2026, 5, 31):
                attrited = False
        if attrited:
            span = (date(2026, 5, 31) - earliest).days
            term = earliest + timedelta(days=random.randint(0, max(span, 1)))
            stat2, massn, terdt = "0", "10", term.isoformat()   # STAT2=0 퇴직, MASSN=10 퇴사조치
            active_end = term
        else:
            stat2, massn, terdt = "3", "01", ""                 # STAT2=3 재직
            active_end = CUTOFF

        employees.append([pernr, rand_name(), gender, birth.isoformat(), hire.isoformat(),
                          orgeh, dept_name, plans, pos_name, stat2, massn, terdt])

        # ── 월별 초과근무: 퇴사자는 퇴사 전 6개월간 잔업 증가 패턴 ──
        for m in month_range(max(hire, date(2023, 1, 1)), active_end):
            ot = max(0, random.gauss(avg_ot, 5))
            if attrited:
                months_to_term = (active_end.year - m.year) * 12 + (active_end.month - m.month)
                if 0 <= months_to_term <= 6:
                    ot *= random.uniform(1.15, 1.5)   # 번아웃 구간
            overtimes.append([pernr, m.strftime("%Y-%m"), round(ot, 1)])

        # ── 근태: 연차(AWART=0100)는 정상, 병가(0200)는 이탈 징후와 상관 ──
        for y in range(max(hire.year, 2023), active_end.year + 1):
            n_leave = random.randint(6, 15)
            n_sick = 0
            if attrited and y >= active_end.year - 1:
                n_sick = random.randint(2, 8)          # 퇴사 전 병가 증가
            elif random.random() < 0.25:
                n_sick = random.randint(1, 4)
            for awart, n in [("0100", n_leave), ("0200", n_sick)]:
                if n == 0:
                    continue
                d0 = date(y, random.randint(1, 12), random.randint(1, 25))
                if hire <= d0 <= active_end:
                    days = min(n, 5)
                    absences.append([pernr, awart, d0.isoformat(),
                                     (d0 + timedelta(days=days - 1)).isoformat(), str(days)])

    # ── CSV 저장 ──
    def save(name, header, rows):
        with open(OUT_DIR / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"  {name:<22} {len(rows):>7,} rows")

    print(f"출력 폴더: {OUT_DIR}")
    save("employees.csv", ["Pernr", "Ename", "Gesch", "Gbdat", "Hidat", "Orgeh", "OrgehTxt",
                           "Plans", "PlansTxt", "Stat2", "Massn", "Terdt"], employees)
    save("salary_history.csv", ["Pernr", "Begda", "Endda", "Bet01"], salaries)
    save("overtime.csv", ["Pernr", "Zmonth", "Othrs"], overtimes)
    save("absences.csv", ["Pernr", "Awart", "Begda", "Endda", "Abwtg"], absences)
    save("appraisals.csv", ["Pernr", "Zyear", "Score"], appraisals)

    n_att = sum(1 for e in employees if e[9] == "0")
    print(f"\n총 {len(employees)}명 중 퇴사 {n_att}명 ({n_att/len(employees):.1%})")


if __name__ == "__main__":
    main()
