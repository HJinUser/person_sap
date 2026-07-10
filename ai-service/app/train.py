# -*- coding: utf-8 -*-
"""
퇴사 예측 모델 학습
===================
세 가지 계열의 모델을 교차검증으로 비교한 뒤 최고 성능 모델을 채택한다.

  - 로지스틱 회귀: 해석이 쉬운 선형 기준선(baseline)
  - 랜덤 포레스트: 비선형 관계를 잡는 배깅 앙상블
  - 그래디언트 부스팅: 순차적으로 오차를 보정하는 부스팅 앙상블

평가 지표는 ROC-AUC를 기본으로 한다. 퇴사자는 전체의 ~14%로 불균형하기
때문에 정확도(accuracy)는 오해를 부른다 — 전부 '재직'이라고 찍어도 86%가
나오기 때문. class_weight='balanced'로 소수 클래스에 가중치를 준다.
"""
import json
import logging
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import (cross_val_predict, cross_val_score,
                                     train_test_split)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import ARTIFACTS_DIR, HIGH_RISK_QUANTILE, MID_RISK_QUANTILE
from .features import (CATEGORICAL_FEATURES, FEATURE_LABELS, LABEL,
                       NUMERIC_FEATURES)

logger = logging.getLogger(__name__)

RANDOM_STATE = 42


def _make_pipeline(model) -> Pipeline:
    """전처리(원핫 인코딩 + 표준화) + 모델을 하나의 파이프라인으로 묶는다."""
    preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", StandardScaler(), NUMERIC_FEATURES),
    ])
    return Pipeline([("prep", preprocessor), ("model", model)])


def train_and_evaluate(df: pd.DataFrame) -> dict:
    """모델 3종 비교 학습 → 최고 성능 모델 채택 → 재직자 위험도 예측 → 산출물 저장"""
    ARTIFACTS_DIR.mkdir(exist_ok=True)

    X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
    y = df[LABEL]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    candidates = {
        "LogisticRegression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE),
        "RandomForest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=RANDOM_STATE),
        "GradientBoosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
    }

    # ── 1단계: 5겹 교차검증으로 후보 비교 ──
    cv_results = {}
    for name, model in candidates.items():
        scores = cross_val_score(_make_pipeline(model), X_train, y_train,
                                 cv=5, scoring="roc_auc")
        cv_results[name] = {"cv_auc_mean": round(scores.mean(), 4),
                            "cv_auc_std": round(scores.std(), 4)}
        logger.info("%s: CV ROC-AUC = %.4f (±%.4f)", name, scores.mean(), scores.std())

    best_name = max(cv_results, key=lambda k: cv_results[k]["cv_auc_mean"])
    best_pipeline = _make_pipeline(candidates[best_name])

    # ── 2단계: 판정 임계값 튜닝 (교차검증 예측 확률에서 F1 최대점 탐색) ──
    # 퇴사자 비율이 ~14%라 기본값 0.5는 재현율을 크게 희생한다.
    cv_proba = cross_val_predict(best_pipeline, X_train, y_train,
                                 cv=5, method="predict_proba")[:, 1]
    thresholds = np.arange(0.10, 0.65, 0.05)
    f1_by_threshold = [f1_score(y_train, cv_proba >= t) for t in thresholds]
    threshold = float(thresholds[int(np.argmax(f1_by_threshold))])
    logger.info("판정 임계값: %.2f (CV F1 최대점)", threshold)

    best_pipeline.fit(X_train, y_train)

    # ── 3단계: 홀드아웃 테스트셋 평가 ──
    proba = best_pipeline.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    cm = confusion_matrix(y_test, pred)
    metrics = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "n_total": len(df),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "attrition_rate": round(float(y.mean()), 4),
        "cv_results": cv_results,
        "best_model": best_name,
        "decision_threshold": round(threshold, 2),
        "test_roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "test_precision": round(float(precision_score(y_test, pred)), 4),
        "test_recall": round(float(recall_score(y_test, pred)), 4),
        "test_f1": round(float(f1_score(y_test, pred)), 4),
        "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
                             "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
    }
    logger.info("채택 모델: %s / 테스트 ROC-AUC: %.4f", best_name, metrics["test_roc_auc"])

    # ── 4단계: 순열 중요도 (모델 종류와 무관하게 피처 기여도 측정) ──
    perm = permutation_importance(best_pipeline, X_test, y_test,
                                  scoring="roc_auc", n_repeats=8,
                                  random_state=RANDOM_STATE)
    importance = sorted(
        [{"feature": f, "label": FEATURE_LABELS.get(f, f),
          "importance": round(float(imp), 4)}
         for f, imp in zip(X.columns, perm.importances_mean)],
        key=lambda x: x["importance"], reverse=True,
    )

    # ── 5단계: 재직자 전원의 퇴사 위험도 예측 + 상대 분위 기반 등급 ──
    active = df[df[LABEL] == 0].copy()
    active["risk"] = best_pipeline.predict_proba(
        active[CATEGORICAL_FEATURES + NUMERIC_FEATURES])[:, 1].round(4)
    high_cut = active["risk"].quantile(HIGH_RISK_QUANTILE)
    mid_cut = active["risk"].quantile(MID_RISK_QUANTILE)
    active["risk_band"] = np.select(
        [active["risk"] >= high_cut, active["risk"] >= mid_cut],
        ["high", "mid"], default="low",
    )

    # ── 산출물 저장 ──
    joblib.dump(best_pipeline, ARTIFACTS_DIR / "model.joblib")
    (ARTIFACTS_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (ARTIFACTS_DIR / "feature_importance.json").write_text(
        json.dumps(importance, ensure_ascii=False, indent=2), encoding="utf-8")
    active.to_csv(ARTIFACTS_DIR / "predictions.csv", index=False, encoding="utf-8-sig")

    return metrics
