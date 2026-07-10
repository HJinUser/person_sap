# -*- coding: utf-8 -*-
"""
SAP OData v2 클라이언트
=======================
SAP NetWeaver Gateway 의 OData v2 프로토콜로 HR 데이터를 수집한다.

실제 SAP 연동과 동일한 규칙을 따른다:
  - 응답 형식: {"d": {"results": [...]}}
  - 페이징: $top / $skip (대량 데이터를 나눠서 수집)
  - CSRF 토큰 핸드셰이크: 변경 요청 전 X-CSRF-Token: Fetch (여기선 조회만 하지만
    SAP 클라이언트의 표준 절차를 그대로 구현)
"""
import logging

import pandas as pd
import requests

from .config import SAP_BASE_URL

logger = logging.getLogger(__name__)

PAGE_SIZE = 5000


class SapODataClient:
    def __init__(self, base_url: str = SAP_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.csrf_token: str | None = None

    def handshake(self) -> None:
        """SAP 표준 CSRF 토큰 핸드셰이크 (서비스 문서 조회 + 토큰 발급)"""
        resp = self.session.get(
            f"{self.base_url}/", headers={"X-CSRF-Token": "Fetch"}, timeout=10
        )
        resp.raise_for_status()
        self.csrf_token = resp.headers.get("X-CSRF-Token")
        entity_sets = resp.json()["d"]["EntitySets"]
        logger.info("SAP 서비스 연결 성공 — 엔티티셋: %s", entity_sets)

    def fetch_entity_set(self, entity_set: str, filter_expr: str | None = None) -> pd.DataFrame:
        """엔티티셋 전체를 페이징하며 수집해 DataFrame으로 반환"""
        rows: list[dict] = []
        skip = 0
        while True:
            params: dict[str, str] = {"$top": str(PAGE_SIZE), "$skip": str(skip)}
            if filter_expr:
                params["$filter"] = filter_expr
            resp = self.session.get(f"{self.base_url}/{entity_set}", params=params, timeout=30)
            resp.raise_for_status()
            page = resp.json()["d"]["results"]
            for row in page:
                row.pop("__metadata", None)  # OData 메타데이터는 분석에 불필요
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                break
            skip += PAGE_SIZE
        logger.info("%s: %d건 수집", entity_set, len(rows))
        return pd.DataFrame(rows)

    def fetch_all(self) -> dict[str, pd.DataFrame]:
        """분석에 필요한 5개 엔티티셋을 모두 수집"""
        self.handshake()
        return {
            "employees": self.fetch_entity_set("EmployeeSet"),
            "salaries": self.fetch_entity_set("SalarySet"),
            "overtime": self.fetch_entity_set("OvertimeSet"),
            "absences": self.fetch_entity_set("AbsenceSet"),
            "appraisals": self.fetch_entity_set("AppraisalSet"),
        }
