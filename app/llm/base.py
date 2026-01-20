"""
LLM Provider Factory - Plug-and-play LLM provider system.
Switch between different LLM providers with just config changes.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)

class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, api_key: str = None, model: str = None, **kwargs):
        """
        Initialize LLM provider.

        Args:
            api_key: API key for the provider
            model: Model name/identifier
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.model = model
        self.config = kwargs

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text response.

        Args:
            prompt: Input prompt
            **kwargs: Provider-specific parameters

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    def generate_json(self, prompt: str, **kwargs) -> dict:
        """
        Generate and parse JSON response.

        Args:
            prompt: Input prompt
            **kwargs: Provider-specific parameters

        Returns:
            Parsed JSON dict
        """
        pass

    def generate_with_context(self, messages: list, **kwargs) -> str:
        """
        Generate response with conversation context.
        Optional - not all providers need to implement this.

        Args:
            messages: List of message dicts with role and content
            **kwargs: Provider-specific parameters

        Returns:
            Generated response
        """
        # Default implementation: concatenate messages
        prompt = "\n\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        return self.generate(prompt, **kwargs)


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    _providers = {}

    @classmethod
    def register(cls, provider_name: str, provider_class: type):
        """Register a new provider."""
        cls._providers[provider_name.lower()] = provider_class
        logger.info(f"Registered LLM provider: {provider_name}")

    @classmethod
    def create(cls, provider_name: str, **kwargs) -> BaseLLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider_name: Name of the provider (e.g., 'groq', 'gemini', 'ollama')
            **kwargs: Provider-specific initialization parameters

        Returns:
            BaseLLMProvider instance

        Raises:
            ValueError: If provider not found
        """
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown LLM provider: {provider_name}. "
                f"Available providers: {available}"
            )

        logger.info(f"Creating LLM provider: {provider_name}")
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list:
        """Get list of registered providers."""
        return list(cls._providers.keys())
