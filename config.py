"""
Configuration module for Raphael backend.
Manages environment-specific settings for development, production, and testing.
"""

import os
from datetime import timedelta
from pathlib import Path

class Config:
    """Base configuration class with common settings."""

    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ==================== LLM PROVIDER CONFIGURATION ====================
    # Change these settings to switch between different LLM providers

    # Primary LLM provider for content generation
    # Options: 'groq', 'gemini', 'ollama', 'openai'
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'groq')

    # LLM API Keys (only needed for cloud providers)
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

    # LLM Models configuration
    LLM_MODELS = {
        'groq': {
            'model': os.environ.get('GROQ_MODEL', 'groq/compound-mini'),
            'temperature': 1.0,
            'top_p': 1.0,
            'stream': True
        },
        'gemini': {
            'model': os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash'),
            'temperature': 0.7,
            'top_p': 0.9
        },
        'ollama': {
            'model': os.environ.get('OLLAMA_MODEL', 'llama2'),
            'base_url': os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'),
            'temperature': 0.8
        },
        'openai': {
            'model': os.environ.get('OPENAI_MODEL', 'gpt-4'),
            'temperature': 0.7,
            'top_p': 0.9
        }
    }

    # External APIs
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

    # Storage
    BASE_DIR = Path(__file__).parent
    COURSES_DIR = BASE_DIR / 'data' / 'courses'

    @classmethod
    def init_app(cls):
        """Initialize application-level configuration."""
        cls.COURSES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_llm_config(cls) -> dict:
        """Get LLM configuration for the selected provider."""
        provider = cls.LLM_PROVIDER.lower()

        if provider not in cls.LLM_MODELS:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        config = cls.LLM_MODELS[provider].copy()

        # Add API key if available
        api_key_map = {
            'groq': cls.GROQ_API_KEY,
            'gemini': cls.GEMINI_API_KEY,
            'openai': cls.OPENAI_API_KEY,
            'ollama': None  # Ollama doesn't need API key
        }

        if provider in api_key_map:
            config['api_key'] = api_key_map[provider]

        return config

class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f'sqlite:///{Config.BASE_DIR / "dev_raphael.db"}'
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_ECHO = False

    @classmethod
    def init_app(cls):
        """Initialize production-specific settings."""
        super().init_app()

        # Validate required API keys based on selected provider
        provider = cls.LLM_PROVIDER.lower()

        if provider == 'groq' and not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY must be set in production")
        elif provider == 'gemini' and not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set in production")
        elif provider == 'openai' and not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set in production")

        if not cls.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY must be set in production")

class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ECHO = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    LLM_PROVIDER = 'mock'  # Use mock provider for testing

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}