"""
Utility modules for Raphael backend.
"""
from app.utils.logger import get_logger

# Optional imports (only if modules exist)
try:
    from app.utils.gemini import GeminiClient
except ImportError:
    GeminiClient = None

try:
    from app.utils.groq import GroqClient
except ImportError:
    GroqClient = None

try:
    from app.utils.youtube import YouTubeClient
except ImportError:
    YouTubeClient = None

__all__ = [
    'get_logger',
]

# Add optional exports if available
if GeminiClient:
    __all__.append('GeminiClient')
if GroqClient:
    __all__.append('GroqClient')
if YouTubeClient:
    __all__.append('YouTubeClient')
