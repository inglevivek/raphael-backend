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
    
    # API Keys
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    
    # Storage
    BASE_DIR = Path(__file__).parent
    COURSES_DIR = BASE_DIR / 'data' / 'courses'
    
    # Ensure courses directory exists
    @classmethod
    def init_app(cls):
        """Initialize application-level configuration."""
        cls.COURSES_DIR.mkdir(parents=True, exist_ok=True)


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
        if not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set in production")
        if not cls.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY must be set in production")


class TestingConfig(Config):
    """Testing environment configuration."""
    
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ECHO = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
