"""Provider package: discovery abstraction + implementations."""

from .base import (
    CompanyQuery,
    ContactInfo,
    NotConfiguredError,
    ProviderError,
    RawCompany,
    ResearchProvider,
)
from .demo import DemoProvider
from .http import HttpApiProvider

_PROVIDERS: dict[str, type[ResearchProvider]] = {
    DemoProvider.name: DemoProvider,
    HttpApiProvider.name: HttpApiProvider,
}


def get_provider(name: str, **kwargs) -> ResearchProvider:
    """Instantiate a provider by name (``"demo"`` | ``"http"``).

    Raises :class:`ValueError` for unknown provider names.
    """
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        known = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"unknown provider {name!r}; expected one of: {known}") from None
    return provider_cls(**kwargs)


def available_providers() -> list[str]:
    """Names of all registered providers."""
    return sorted(_PROVIDERS)


__all__ = [
    "CompanyQuery",
    "ContactInfo",
    "NotConfiguredError",
    "ProviderError",
    "RawCompany",
    "ResearchProvider",
    "DemoProvider",
    "HttpApiProvider",
    "get_provider",
    "available_providers",
]
