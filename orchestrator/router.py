from __future__ import annotations

from adapters.base import BaseAdapter
from orchestrator.config import RuntimeConfig
from orchestrator.registry import get_registry


def select_adapter(product_type: str, config: RuntimeConfig) -> BaseAdapter:
    return get_registry().create_adapter(product_type, config)


def adapter_capabilities(product_type: str) -> list[str]:
    return get_registry().capability_names_for(product_type)


def adapter_fallback_mode(product_type: str) -> str:
    return get_registry().fallback_mode_for(product_type)


def adapter_fallback_note(product_type: str) -> str | None:
    return get_registry().fallback_note_for(product_type)
