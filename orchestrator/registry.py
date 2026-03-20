from __future__ import annotations

from dataclasses import dataclass

from adapters.api_adapter import ApiAdapter
from adapters.base import BaseAdapter
from adapters.llm_app_adapter import LlmAppAdapter
from adapters.mobile_adapter import MobileAdapter
from adapters.model_adapter import ModelAdapter
from adapters.web_adapter import WebAdapter
from orchestrator.capabilities import CORE_CAPABILITIES, Capability, capability_names
from orchestrator.config import RuntimeConfig


@dataclass(frozen=True)
class RegistryEntry:
    product_type: str
    adapter_class: type[BaseAdapter]
    capabilities: tuple[Capability, ...]
    fallback_mode: str
    fallback_note: str | None = None


class AdapterRegistry:
    def __init__(self, entries: dict[str, RegistryEntry], default_product_type: str = "web") -> None:
        self._entries = entries
        self._default_product_type = default_product_type

    def _normalized(self, product_type: str) -> str:
        return (product_type or "").lower().strip()

    def get_entry(self, product_type: str) -> RegistryEntry:
        normalized = self._normalized(product_type)
        if normalized in self._entries:
            return self._entries[normalized]
        fallback = self._entries[self._default_product_type]
        return RegistryEntry(
            product_type=normalized or self._default_product_type,
            adapter_class=fallback.adapter_class,
            capabilities=fallback.capabilities,
            fallback_mode=f"unsupported_product_type:{normalized or 'empty'}->web",
            fallback_note=f"Product type '{normalized or 'empty'}' is unsupported; routed to web adapter fallback.",
        )

    def create_adapter(self, product_type: str, config: RuntimeConfig) -> BaseAdapter:
        entry = self.get_entry(product_type)
        return entry.adapter_class(config)

    def capability_names_for(self, product_type: str) -> list[str]:
        return capability_names(self.get_entry(product_type).capabilities)

    def fallback_mode_for(self, product_type: str) -> str:
        return self.get_entry(product_type).fallback_mode

    def fallback_note_for(self, product_type: str) -> str | None:
        return self.get_entry(product_type).fallback_note

    def supported_product_types(self) -> list[str]:
        return sorted(self._entries.keys())


def _entry(
    product_type: str,
    adapter_class: type[BaseAdapter],
    fallback_mode: str = "native",
    fallback_note: str | None = None,
    capabilities: tuple[Capability, ...] = CORE_CAPABILITIES,
) -> RegistryEntry:
    return RegistryEntry(
        product_type=product_type,
        adapter_class=adapter_class,
        capabilities=capabilities,
        fallback_mode=fallback_mode,
        fallback_note=fallback_note,
    )


def build_default_registry() -> AdapterRegistry:
    entries = {
        "web": _entry("web", WebAdapter),
        "api": _entry("api", ApiAdapter),
        "model": _entry("model", ModelAdapter),
        "mobile": _entry(
            "mobile",
            MobileAdapter,
            fallback_mode="skeleton_smoke",
            fallback_note="Mobile adapter is running deterministic skeleton smoke execution in v1.5.",
        ),
        "llm_app": _entry(
            "llm_app",
            LlmAppAdapter,
            fallback_mode="skeleton_smoke",
            fallback_note="llm_app adapter is running deterministic skeleton evaluation in v1.5.",
        ),
    }
    return AdapterRegistry(entries=entries, default_product_type="web")


_DEFAULT_REGISTRY = build_default_registry()


def get_registry() -> AdapterRegistry:
    return _DEFAULT_REGISTRY
