#!/usr/bin/env python3
"""
VISHMUX provider package – exports all providers and a factory.
"""

from .base import BaseProvider
from .openrouter import OpenRouterProvider
from .groq import GroqProvider
from .nvidia import NvidiaProvider
from .gemini import GeminiProvider
from .together import TogetherProvider
from .mistral import MistralProvider
from .anthropic import AnthropicProvider
from .perplexity import PerplexityProvider

_PROVIDER_MAP = {
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "nvidia": NvidiaProvider,
    "gemini": GeminiProvider,
    "together": TogetherProvider,
    "mistral": MistralProvider,
    "anthropic": AnthropicProvider,
    "perplexity": PerplexityProvider,
}

def get_provider(name: str, api_key: str, model: str) -> BaseProvider:
    """
    Create and return a provider instance based on its config name.
    Raises ValueError if the provider name is unknown.
    """
    name_lower = name.lower()
    if name_lower not in _PROVIDER_MAP:
        raise ValueError(f"Unknown provider: {name}. Available: {', '.join(_PROVIDER_MAP.keys())}")
    return _PROVIDER_MAP[name_lower](api_key=api_key, model=model)
