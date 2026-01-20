"""
LLM providers module.
Automatically registers all available providers.
"""

from app.llm.base import BaseLLMProvider, LLMProviderFactory

# Import and register providers
try:
    from app.llm.providers.groq import GroqProvider
    LLMProviderFactory.register('groq', GroqProvider)
except ImportError:
    pass

try:
    from app.llm.providers.gemini import GeminiProvider
    LLMProviderFactory.register('gemini', GeminiProvider)
except ImportError:
    pass

try:
    from app.llm.providers.ollama import OllamaProvider
    LLMProviderFactory.register('ollama', OllamaProvider)
except ImportError:
    pass

__all__ = ['BaseLLMProvider', 'LLMProviderFactory']
