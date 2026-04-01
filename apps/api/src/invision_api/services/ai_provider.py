"""
AI integration for future committee workflows.

Policy:
- Never emit final admission decisions.
- Outputs are assistive (summaries, explainability, risk signals) and stored for human review.
"""

import json
from typing import Any, Protocol

from openai import OpenAI

from invision_api.core.config import get_settings


class AIProvider(Protocol):
    def summarize_candidate_materials(self, *, prompt_version: str, context: dict[str, Any]) -> str: ...

    def structured_profile_summary(self, *, prompt_version: str, context: dict[str, Any]) -> dict[str, Any]: ...

    def explainability_flags(self, *, prompt_version: str, context: dict[str, Any]) -> dict[str, Any]: ...

    def authenticity_risk(self, *, prompt_version: str, context: dict[str, Any]) -> float | None: ...

    def committee_structured_summary(
        self,
        *,
        prompt_version: str,
        compact_payload: dict[str, Any],
        system_prompt: str,
        user_message: str,
    ) -> dict[str, Any]: ...


class OpenAIProvider:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def summarize_candidate_materials(self, *, prompt_version: str, context: dict[str, Any]) -> str:
        system = (
            "You assist admissions reviewers with neutral summaries of applicant materials. "
            "Do not make an admissions decision or recommendation. "
            "Do not infer protected attributes as proxies for fit."
        )
        user = {"prompt_version": prompt_version, "context": context}
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": str(user)},
            ],
            temperature=0.2,
            timeout=60.0,
        )
        return (resp.choices[0].message.content or "").strip()

    def structured_profile_summary(self, *, prompt_version: str, context: dict[str, Any]) -> dict[str, Any]:
        text = self.summarize_candidate_materials(prompt_version=prompt_version, context=context)
        return {"prompt_version": prompt_version, "summary": text}

    def explainability_flags(self, *, prompt_version: str, context: dict[str, Any]) -> dict[str, Any]:
        system = (
            "Return concise, factual notes to support human review. "
            "Never output a final admissions decision. "
            "Flag only content issues (missing materials, inconsistencies), not demographic proxies."
        )
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": str({"prompt_version": prompt_version, "context": context})},
            ],
            temperature=0.1,
            timeout=60.0,
        )
        return {"prompt_version": prompt_version, "notes": (resp.choices[0].message.content or "").strip()}

    def authenticity_risk(self, *, prompt_version: str, context: dict[str, Any]) -> float | None:
        system = (
            "Estimate only document authenticity risk as a number between 0 and 1 based on provided metadata. "
            "This is not an admissions decision. If insufficient data, respond with the single word: null"
        )
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": str({"prompt_version": prompt_version, "context": context})},
            ],
            temperature=0.0,
            timeout=60.0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.lower() == "null":
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def committee_structured_summary(
        self,
        *,
        prompt_version: str,
        compact_payload: dict[str, Any],
        system_prompt: str,
        user_message: str,
    ) -> dict[str, Any]:
        _ = (prompt_version, len(compact_payload))
        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            timeout=90.0,
        )
        text = (resp.choices[0].message.content or "").strip()
        return json.loads(text)


def get_ai_provider() -> OpenAIProvider:
    return OpenAIProvider()
