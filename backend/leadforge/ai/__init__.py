"""AI enrichment providers.

Default is :class:`NullAIProvider` (disabled, offline, no credentials) — the
application is fully usable without any AI key. When ``LEADFORGE_LLM_API_KEY``
is set, :func:`get_ai_provider` returns the optional :class:`LLMProvider`.
"""

from .base import AIProvider
from .llm import ENV_VAR, LLMProvider, NotConfiguredError, tag_ai_fields
from .null import NullAIProvider


def get_ai_provider() -> AIProvider:
    """Return the configured AI provider.

    ``LLMProvider`` when ``LEADFORGE_LLM_API_KEY`` is set, otherwise the
    disabled :class:`NullAIProvider` default. Never raises.
    """
    llm = LLMProvider()
    return llm if llm.enabled else NullAIProvider()


__all__ = [
    "AIProvider",
    "ENV_VAR",
    "LLMProvider",
    "NotConfiguredError",
    "NullAIProvider",
    "get_ai_provider",
    "tag_ai_fields",
]
