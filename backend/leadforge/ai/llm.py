"""Optional LLM enrichment provider.

Enabled **only** when the ``LEADFORGE_LLM_API_KEY`` environment variable is set
to a non-empty value. The key is read from the environment — never from code,
never logged, never included in ``repr`` or error messages.

Provider-agnostic transport: the actual HTTP call is an injectable ``chat``
callable (``async (system, user) -> str``) so tests use mocks and no real
external API is ever called from the test suite. When no transport is wired,
calls safely resolve to ``None``.

Anti-fabrication rules (system prompt + parsing, defense in depth):

* the model is instructed to use only the input it was given and to return
  ``null`` rather than guess;
* it must never invent facts, contacts, URLs, or addresses;
* responses must be JSON; anything else is discarded (treated as ``None``);
* uncertainty must be explicit — a missing/``null`` field means "unknown",
  never a silent guess.

The pipeline wraps every stored AI value as
``{"value": ..., "ai_derived": True}`` via :func:`tag_ai_fields`, so AI output
is never persisted as if it were a verified source fact.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Awaitable, Callable

from .base import AIProvider

log = logging.getLogger(__name__)

ENV_VAR = "LEADFORGE_LLM_API_KEY"

SYSTEM_PROMPT = """\
You are a careful data assistant helping with B2B lead research.
STRICT RULES — you must obey all of them:
1. Use ONLY the information given in the user message. Never invent facts.
2. Never invent or guess contacts, email addresses, phone numbers, URLs, or street addresses.
3. If a field cannot be determined from the input, return null for that field. Do not guess.
4. State uncertainty explicitly: use null for unknown, never a plausible-sounding fabrication.
5. Respond with a single JSON object only. No prose, no markdown, no code fences.
""".strip()


class NotConfiguredError(RuntimeError):
    """No LLM transport is wired for this provider instance."""


# async (system_prompt, user_prompt) -> raw response text
ChatTransport = Callable[[str, str], Awaitable[str]]


def tag_ai_fields(fields: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Wrap each field as ``{"value": ..., "ai_derived": True}``.

    Nested dicts are tagged leaf-by-leaf; ``None`` values stay ``None`` but
    are still marked ``ai_derived`` so "unknown" is explicit, not silent.
    """
    tagged: dict[str, dict[str, Any]] = {}
    for key, value in fields.items():
        if isinstance(value, dict):
            tagged[key] = {
                sub: {"value": v, "ai_derived": True} for sub, v in value.items()
            }
        else:
            tagged[key] = {"value": value, "ai_derived": True}
    return tagged


class LLMProvider(AIProvider):
    """Optional LLM-backed provider; enabled only with an API key in env."""

    name: str = "llm"

    def __init__(
        self,
        api_key: str | None = None,
        chat: ChatTransport | None = None,
    ) -> None:
        # Key comes from the environment unless explicitly injected (tests).
        # It is stored privately and never surfaces in repr/logs/errors.
        self._api_key = api_key if api_key is not None else os.environ.get(ENV_VAR)
        self._chat = chat

    def __repr__(self) -> str:  # credential-safe: never shows the key
        return f"<LLMProvider enabled={self.enabled}>"

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    # -- AIProvider interface -------------------------------------------------

    async def classify_company(
        self, company: dict[str, Any], industry: str
    ) -> str | None:
        name = company.get("company_name") or "unknown company"
        payload = self._ask(
            f"Company: {name}\nStated industry: {industry or 'not given'}\n"
            "Task: confirm or correct the industry label using ONLY the input. "
            'Respond as JSON: {"industry": "<label>"} or {"industry": null}.'
        )
        data = await payload
        if isinstance(data, dict):
            label = data.get("industry")
            if not label:
                return None
            return str(label).strip() or None
        return None

    async def extract_company_information(self, text: str) -> dict[str, Any] | None:
        data = await self._ask(
            "Extract structured information from the following company description. "
            "Use ONLY facts present in the text; null for anything not stated. "
            'Respond as JSON, e.g. {"website": ..., "phone": ..., "city": ...}.\n\n'
            f"Description:\n{text}"
        )
        return data if isinstance(data, dict) else None

    async def summarize_company(self, company: dict[str, Any]) -> str | None:
        name = company.get("company_name") or "unknown company"
        facts = ", ".join(
            f"{k}={v}"
            for k, v in company.items()
            if v and k in ("industry", "city", "region", "country", "website")
        )
        data = await self._ask(
            f"Summarize this company in one to three sentences using ONLY these "
            f"facts: {name}; {facts}. "
            'Respond as JSON: {"summary": "<text>"} or {"summary": null}.'
        )
        if isinstance(data, dict):
            summary = data.get("summary")
            if not summary:
                return None
            return str(summary).strip() or None
        return None

    # -- internals ------------------------------------------------------------

    async def _ask(self, user_prompt: str) -> Any | None:
        """Send one prompt; return parsed JSON or ``None`` on any failure.

        Never raises: transport errors, malformed responses, and missing
        configuration all resolve to ``None`` so a job can never fail because
        of AI. Failures are logged without credentials.
        """
        if not self.enabled:
            return None
        if self._chat is None:
            log.warning("LLMProvider has a key but no chat transport is wired")
            return None
        try:
            raw = await self._chat(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:  # transport failure — degrade, don't fail
            log.warning("LLMProvider chat transport failed: %s", type(exc).__name__)
            return None
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> Any | None:
        """Parse a JSON response; ``None`` for anything malformed."""
        if not isinstance(raw, str):
            return None
        text = raw.strip()
        # Tolerate a single markdown code fence some models add anyway.
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            log.warning("LLMProvider discarded a malformed (non-JSON) response")
            return None
