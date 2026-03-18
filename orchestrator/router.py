from __future__ import annotations

from adapters.api_adapter import ApiAdapter
from adapters.base import BaseAdapter
from adapters.model_adapter import ModelAdapter
from adapters.web_adapter import WebAdapter
from orchestrator.config import RuntimeConfig


def select_adapter(product_type: str, config: RuntimeConfig) -> BaseAdapter:
    mapping: dict[str, type[BaseAdapter]] = {
        "web": WebAdapter,
        "api": ApiAdapter,
        "model": ModelAdapter,
    }
    adapter_cls = mapping.get(product_type)
    if adapter_cls is None:
        raise ValueError(f"Unsupported project type: {product_type}")
    return adapter_cls(config)
