from __future__ import annotations

import os
from typing import Any

import httpx

INTERNAL_LLM_SUMMARY_URL = os.getenv("INTERNAL_LLM_SUMMARY_URL")
INTERNAL_LLM_API_KEY = os.getenv("INTERNAL_LLM_API_KEY")


class LLMSummaryClient:
    def __init__(self, endpoint: str | None = None, api_key: str | None = None, *, timeout_sec: float = 20.0) -> None:
        self._endpoint = endpoint or INTERNAL_LLM_SUMMARY_URL
        self._api_key = api_key or INTERNAL_LLM_API_KEY
        self._timeout = timeout_sec

    @property
    def enabled(self) -> bool:
        return bool(self._endpoint)

    def summarize(self, *, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._endpoint:
            return None
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request_payload = {
            "task": "candidate_data_check_summary",
            "payload": payload,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(self._endpoint, json=request_payload, headers=headers)
            if resp.status_code >= 300:
                return None
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                return None
            return data if isinstance(data, dict) else None
