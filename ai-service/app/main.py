# -*- coding: utf-8 -*-
"""
AI 서비스 API (FastAPI)
=======================
SAP Mock ↔ ML 모델 ↔ 대시보드를 잇는 백엔드.

  POST /api/sync-train      SAP에서 데이터 수집 → 피처 생성 → 모델 학습 → 예측 저장
  GET  /api/summary         전사 KPI 요약
  GET  /api/departments     부서별 위험 현황
  GET  /api/employees/risk  위험도 상위 직원 목록
  GET  /api/model/metrics   모델 성능 지표
  GET  /api/model/features  피처 중요도
  POST /api/report/generate AI 분석 리포트 생성
  GET  /api/report/latest   최근 생성 리포트 조회
"""
import json
import logging

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import ARTIFACTS_DIR
from .features import build_features
from .insights import build_insights, generate_report
from .odata_client import SapODataClient
from .train import train_and_evaluate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="SAP HR Insight — AI Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_artifacts():
    if not (ARTIFACTS_DIR / "predictions.csv").exists():
        raise HTTPException(
            status_code=409,
            detail="아직 학습된 모델이 없습니다. POST /api/sync-train 을 먼저 호출하세요.",
        )


@app.get("/api/health")
def health():
    return {"status": "ok", "trained": (ARTIFACTS_DIR / "model.joblib").exists()}


@app.post("/api/sync-train")
def sync_and_train():
    """SAP OData 수집 → 피처 엔지니어링 → 모델 학습 → 위험도 예측 (전체 파이프라인)"""
    try:
        data = SapODataClient().fetch_all()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SAP OData 수집 실패: {e}")
    df = build_features(data)
    metrics = train_and_evaluate(df)
    return {"message": "학습 완료", "metrics": metrics}


@app.get("/api/summary")
def summary():
    _require_artifacts()
    pred = pd.read_csv(ARTIFACTS_DIR / "predictions.csv", dtype={"pernr": str})
    metrics = json.loads((ARTIFACTS_DIR / "metrics.json").read_text(encoding="utf-8"))
    return {
        "active_headcount": len(pred),
        "high_risk_count": int((pred["risk_band"] == "high").sum()),
        "avg_risk": round(float(pred["risk"].mean()), 4),
        "model": metrics["best_model"],
        "test_roc_auc": metrics["test_roc_auc"],
        "trained_at": metrics["trained_at"],
    }


@app.get("/api/departments")
def departments():
    _require_artifacts()
    return build_insights()["departments"]


@app.get("/api/employees/risk")
def employees_risk(limit: int = 20):
    _require_artifacts()
    pred = pd.read_csv(ARTIFACTS_DIR / "predictions.csv", dtype={"pernr": str})
    cols = ["pernr", "name", "dept", "position", "tenure_years", "ot_avg_6m",
            "years_since_raise", "last_score", "risk", "risk_band"]
    top = pred.sort_values("risk", ascending=False).head(limit)[cols]
    return top.round(3).to_dict(orient="records")


@app.get("/api/model/metrics")
def model_metrics():
    _require_artifacts()
    return json.loads((ARTIFACTS_DIR / "metrics.json").read_text(encoding="utf-8"))


@app.get("/api/model/features")
def model_features():
    _require_artifacts()
    return json.loads(
        (ARTIFACTS_DIR / "feature_importance.json").read_text(encoding="utf-8"))


@app.post("/api/report/generate")
def report_generate():
    _require_artifacts()
    return generate_report()


@app.get("/api/report/latest")
def report_latest():
    path = ARTIFACTS_DIR / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404,
                            detail="생성된 리포트가 없습니다. POST /api/report/generate 를 먼저 호출하세요.")
    return json.loads(path.read_text(encoding="utf-8"))
