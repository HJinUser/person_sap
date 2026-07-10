# SAP HR Insight — SAP HCM 연동 퇴사 위험 예측 & AI 인사 분석

> SAP HR(HCM)의 데이터 모델을 공부해 **OData 규격의 모의 SAP 서버**로 재현하고,
> 그 데이터를 **머신러닝으로 분석해 퇴사 위험을 예측**하며,
> **AI가 경영진용 인사 리포트를 자동 작성**하는 풀스택 프로젝트입니다.

## 왜 이 프로젝트인가

SAP ERP는 개인이 접근할 수 없는 시스템입니다. 그래서 이 제약을
"SAP의 테이블 구조와 연동 프로토콜을 학습해서 직접 재현한다"는 기회로 바꿨습니다.
채용 관점에서 신입에게 필요한 것은 SAP 운영 경험이 아니라:

1. **ERP 비즈니스 데이터에 대한 이해** — 인사 인포타입(PA0001/PA0008/PA2001)의 구조와 의미
2. **SAP 표준 연동 방식에 대한 이해** — OData v2, `$filter`/`$top`/`$metadata`, X-CSRF-Token
3. **그 위에 가치를 만드는 능력** — ML 예측과 AI 분석

이 세 가지를 증명하는 것이 이 프로젝트의 목표입니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  sap-mock  ·  Spring Boot 3 (Java 17+) · 포트 8081               │
│  SAP HCM 인포타입 재현: PA0001(조직배치) PA0008(급여) PA2001(근태)  │
│  SAP NetWeaver Gateway OData v2 규격 API                         │
│  /sap/opu/odata/sap/ZHR_EMP_SRV/{EntitySet}                      │
│  $filter · $top · $skip · $inlinecount · $metadata · CSRF 토큰    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ OData v2 (표준 SAP 연동 프로토콜)
┌──────────────────────────▼──────────────────────────────────────┐
│  ai-service  ·  Python FastAPI · 포트 8000                       │
│  ① OData 수집 → 시점 기준(point-in-time) 피처 엔지니어링          │
│  ② scikit-learn 모델 3종 교차검증 비교 → 최적 모델 채택           │
│  ③ 규칙 기반 인사이트 엔진 + Claude API 내러티브(선택)            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST + CORS
┌──────────────────────────▼──────────────────────────────────────┐
│  frontend  ·  React 19 + TypeScript (Vite) · 포트 5173           │
│  KPI 타일 · 부서별 위험 차트 · 위험 요인 차트 · 면담 대상 테이블   │
│  AI 리포트 뷰 (라이트/다크 모드 지원)                             │
└─────────────────────────────────────────────────────────────────┘
```

ML 서비스를 SAP 애드온이 아니라 **사이드카(별도 서비스)** 로 분리한 것은
실제 SAP BTP의 확장(side-by-side extension) 패턴과 같은 구조입니다 —
ERP 코어를 건드리지 않고 표준 API로만 통신합니다.

## 데이터 설계 — 합성이지만 인과 구조를 주입

`data-gen/generate.py`가 사원 1,200명(퇴사율 약 14%)의 HR 데이터를 생성합니다.
단순 랜덤이 아니라 **퇴사 확률이 명시적인 요인의 함수**가 되도록 설계했습니다:

| 주입한 인과 요인 | 모델이 복원했는가 |
|---|---|
| 퇴사 전 6개월 잔업 증가(번아웃 램프) | ✅ 중요도 2위 |
| 퇴사 전 병가 증가 | ✅ 중요도 1위 |
| 급여 정체(마지막 인상 후 경과) | ✅ 상위권 |
| 평가점수 하락 추세 | ✅ 상위권 |
| 입사 2년 미만 조기 이탈 구간 | ✅ (근속연수) |

즉 이 프로젝트의 ML 파트는 "**심어둔 패턴을 모델이 데이터에서 스스로
복원하는지 검증하는 실험**"으로 설계되었습니다.

## ML 설계에서 신경 쓴 것들

- **데이터 누수(leakage) 방지 — 시점 기준 피처**: 퇴사자의 피처는 퇴사일 기준,
  재직자는 관측 시점 기준으로 계산합니다.
- **관측 시점 편향 제거**: 재직자 전원을 같은 스냅샷 날짜로 고정하면
  "3월 일괄 인상 직후"라는 시점 특성이 재직자에게만 생겨, 모델이 인과 요인이
  아니라 **관측 시점의 차이**를 학습합니다(실제로 초기 버전에서 AUC 0.98이
  나왔다가 이 편향을 제거하니 0.89로 내려왔습니다 — 부풀려진 성능이었던 것).
  재직자의 기준일을 최근 1년 내에서 무작위 샘플링해 해결했습니다.
- **불균형 데이터**: 퇴사율 ~14%이므로 정확도 대신 ROC-AUC로 평가하고,
  `class_weight='balanced'`와 F1 최적 임계값 튜닝(0.5 → 0.40)을 적용했습니다.
- **모델 비교**: 로지스틱 회귀(선형 기준선) / 랜덤 포레스트 / 그래디언트 부스팅을
  5겹 교차검증으로 비교해 채택합니다.
- **해석 가능성**: 순열 중요도(permutation importance)로 모델 종류와 무관하게
  피처 기여도를 측정하고, 개인별 위험 요인 태그를 함께 제공합니다.
- **위험 등급은 상대 분위**: 트리 모델의 확률값은 보정(calibration)되지 않으므로
  절대 임계값 대신 "위험도 상위 5% = 고위험"의 우선순위 방식을 씁니다.

## AI 분석 리포트 — 2단계 설계

1. **규칙 기반 인사이트 엔진** (항상 동작): 부서별 위험 순위, 개인별 위험 요인
   태그, 전사 지표를 구조화된 JSON으로 추출 → 마크다운 리포트 조립
2. **Claude API 내러티브** (선택): `ANTHROPIC_API_KEY`가 설정돼 있으면 1단계의
   구조화된 사실을 Claude에게 전달해 자연어 경영 리포트로 변환.
   키가 없거나 호출 실패 시 1단계 결과로 자동 대체(graceful degradation).

LLM에게 원본 데이터가 아니라 **검증된 통계 사실만** 전달해 환각(hallucination)을
구조적으로 억제합니다 — 프롬프트에도 "JSON에 있는 값만 사용"을 명시.

## 실행 방법

요구사항: Java 17+, Python 3.11+, Node 18+

```bash
# 0) 합성 데이터 생성 (data/ 폴더에 CSV 5종)
python data-gen/generate.py

# 1) SAP Mock 서버 (포트 8081)
cd sap-mock
./mvnw spring-boot:run        # Windows: .\mvnw.cmd spring-boot:run

# 2) AI 서비스 (포트 8000)
cd ai-service
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000

# 3) 대시보드 (포트 5173)
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 접속 → **[데이터 동기화 + 재학습]** 클릭 →
**[AI 리포트 생성]** 클릭.

OData API를 직접 확인하려면:

```
http://localhost:8081/sap/opu/odata/sap/ZHR_EMP_SRV/                 # 서비스 문서
http://localhost:8081/sap/opu/odata/sap/ZHR_EMP_SRV/$metadata        # EDMX 스키마
http://localhost:8081/sap/opu/odata/sap/ZHR_EMP_SRV/EmployeeSet?$filter=Stat2 eq '0'&$top=5
http://localhost:8081/sap/opu/odata/sap/ZHR_EMP_SRV/EmployeeSet('10000001')
```

### 트러블슈팅: Windows에서 Tomcat이 "Unable to establish loopback connection"으로 죽을 때

일부 Windows 환경(보안 정책으로 AF_UNIX 소켓 연결이 차단된 경우)에서 JDK 17+의
NIO Selector 초기화가 실패합니다. JDK는 유닉스 도메인 소켓 **bind가 실패하면**
TCP 루프백으로 폴백하므로, 소켓 파일 생성 경로를 존재하지 않는 곳으로 지정해
폴백을 강제하면 해결됩니다:

```bash
.\mvnw.cmd spring-boot:run "-Dspring-boot.run.jvmArguments=-Djdk.net.unixdomain.tmpdir=C:\__no_such_dir__"
```

## 기술 스택 선택 이유

| 선택 | 이유 |
|---|---|
| Spring Boot로 Mock 직접 구현 | SAP 접근 불가라는 제약을 OData 프로토콜·HCM 테이블 학습 기회로 전환 |
| OData v2 (v4 아님) | SAP NetWeaver Gateway의 실무 표준이 여전히 v2 |
| H2 인메모리 + JPA | 기동 시 CSV 적재로 재현성 확보, 별도 DB 설치 불필요 |
| FastAPI 분리 서비스 | ML 생태계(Python)와 ERP(Java)의 언어 경계를 API 계약으로 해결 |
| 순열 중요도 | 모델 교체(LR→RF→GB)와 무관하게 동일한 해석 파이프라인 유지 |
| 규칙 기반 + LLM 이중화 | 외부 API 장애가 핵심 기능을 막지 않도록 |

## 한계 (정직하게)

- **합성 데이터**: 실제 HR 데이터의 노이즈·결측·조직 특수성이 없어 성능 지표가
  실전보다 낙관적입니다. 이 프로젝트의 검증 대상은 "예측 정확도"가 아니라
  "설계한 인과 구조를 복원하는 파이프라인의 방법론적 올바름"입니다.
- **읽기 전용 Mock**: 실제 SAP 연동이라면 변경 요청(POST/PUT)의 CSRF 토큰 사용,
  배치 요청($batch), 델타 쿼리 등이 추가로 필요합니다.
- **윤리적 고려**: 퇴사 예측은 감시가 아니라 조직 개선(면담·보상 검토)의
  보조 자료로만 쓰여야 하며, 대시보드에도 해당 고지를 명시했습니다.

## 프로젝트 구조

```
sap-hr-insight/
├── data-gen/          # 합성 HR 데이터 생성기 (인과 구조 주입)
├── data/              # 생성된 CSV (git 미포함 — generate.py로 재생성)
├── sap-mock/          # Spring Boot OData v2 모의 SAP 서버
├── ai-service/        # FastAPI + scikit-learn + Claude API
│   └── artifacts/     # 학습 산출물 (git 미포함)
├── frontend/          # React + TS 대시보드
└── docs/
    └── INTERVIEW.md   # 면접 예상 질문과 답변 정리
```
