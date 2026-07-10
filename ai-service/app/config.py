# -*- coding: utf-8 -*-
"""AI 서비스 설정"""
import os
from pathlib import Path

# SAP Mock 서버 (NetWeaver Gateway OData v2 규격)
SAP_BASE_URL = os.getenv(
    "SAP_BASE_URL", "http://localhost:8081/sap/opu/odata/sap/ZHR_EMP_SRV"
)

# 데이터 스냅샷 기준일 (재직자의 피처 계산 기준 시점)
CUTOFF_DATE = "2026-06-30"

# 학습 산출물 저장 위치
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"

# 위험 등급 기준 (재직자 위험도 분포의 상대 분위 — 트리 모델의 확률값은
# 보정되지 않아 절대 임계값보다 "우선순위 상위 N%" 방식이 실무적으로 타당)
HIGH_RISK_QUANTILE = 0.95   # 상위 5% = 고위험
MID_RISK_QUANTILE = 0.80    # 상위 20% = 중위험

# AI 리포트에 사용할 Claude 모델 (API 키 없으면 규칙 기반 리포트로 대체)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")
