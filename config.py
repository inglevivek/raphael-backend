"""
Configuration module for Raphael backend.

Auto-detects environment:
- Development: Local or Docker development
- Production: Railway deployment

Environment Variables:
- DATABASE_URL: PostgreSQL connection string
- REDIS_URL: Redis connection string
- GROQ_API_KEY: Groq API key
- YOUTUBE_API_KEY: YouTube Data API key
- JWT_SECRET_KEY: Secret key for JWT tokens
"""

import os
from datetime import timedelta
from pickle import TRUE


class Config:
    """Base configuration with shared settings"""

    # ==========================================
    # ENVIRONMENT DETECTION
    # ==========================================
    ENV = os.getenv('FLASK_ENV', 'development')
    RAILWAY_ENVIRONMENT = os.getenv('RAILWAY_ENVIRONMENT')  # Set by Railway

    # ==========================================
    # FLASK SETTINGS
    # ==========================================
    SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')

    # ==========================================
    # DATABASE (PostgreSQL)
    # ==========================================
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    # Handle Railway's postgres:// vs postgresql:// prefix
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            'postgres://', 'postgresql://', 1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20
    }

    # ==========================================
    # REDIS
    # ==========================================
    REDIS_URL = os.getenv('REDIS_URL')
    
    # ==========================================
    # JWT AUTHENTICATION
    # ==========================================
    # JWT Cookie Settings
    JWT_TOKEN_LOCATION = ['cookies']  # Store in cookies, not headers
    JWT_COOKIE_SECURE = False  # True in production (HTTPS only)
    JWT_COOKIE_HTTPONLY = True  # Can't access via JavaScript
    JWT_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)  # 7 days

    # CORS for cookies
    CORS_SUPPORTS_CREDENTIALS = True
    

    # ==========================================
    # LLM (Groq Only)
    # ==========================================
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'groq/compound-mini')

    # ==========================================
    # YOUTUBE API
    # ==========================================
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

    # ==========================================
    # COURSE GENERATION SETTINGS
    # ==========================================
    MAX_RETRIES = 3
    CHECKPOINT_ENABLED = True

    @staticmethod
    def validate():
        """Validate required configuration"""
        errors = []
        
        if not Config.SQLALCHEMY_DATABASE_URI:
            errors.append("DATABASE_URL is required")
        if not Config.GROQ_API_KEY:
            errors.append("GROQ_API_KEY is required")
        if not Config.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY is required")
        
        # Add this:
        if Config.RAILWAY_ENVIRONMENT == 'production':
            if not Config.JWT_SECRET_KEY or Config.JWT_SECRET_KEY == 'dev-secret-key-change-in-production':
                errors.append("JWT_SECRET_KEY must be set in production")
            if not Config.SECRET_KEY or Config.SECRET_KEY == 'dev-secret-key-change-in-production':
                errors.append("SECRET_KEY must be set in production")
            # Add FRONTEND_URL check
            if 'FRONTEND_URL' not in os.environ:
                errors.append("FRONTEND_URL must be set in production")
        
        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f" - {e}" for e in errors)
            raise ValueError(error_msg)

    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        Config.validate()


class DevelopmentConfig(Config):
    """Development environment configuration (local or Docker)"""

    DEBUG = True
    TESTING = False

    # Verbose SQL logging in development
    SQLALCHEMY_ECHO = False

    # More detailed error pages
    PROPAGATE_EXCEPTIONS = True
    FRONTEND_URL ='http://localhost:3000'
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        app.logger.info("🔧 Development mode enabled")
        app.logger.info(f"📊 Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
        app.logger.info(f"🔴 Redis: {app.config.get('REDIS_URL', 'Not configured')}")


class ProductionConfig(Config):
    """Production environment configuration (Railway)"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    PROPAGATE_EXCEPTIONS = False
    
    # ✅ Production-specific overrides
    JWT_COOKIE_SECURE = True  # HTTPS only
    JWT_COOKIE_SAMESITE = 'None'  # For cross-origin cookies with HTTPS
    
    FRONTEND_URL = os.getenv('FRONTEND_URL')
    
    # Production-optimized database settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 1800,
        'pool_pre_ping': True,
        'max_overflow': 40,
        'pool_timeout': 30
    }
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Production-specific initialization
        app.logger.info("🚀 Production mode enabled (Railway)")
        app.logger.info(f"✅ Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'Unknown')}")
        app.logger.info("✅ PostgreSQL configured")
        app.logger.info("✅ Redis configured" if app.config.get('REDIS_URL') else "⚠️ Redis not configured")
        app.logger.info(f"✅ Groq API key: {'Set' if app.config.get('GROQ_API_KEY') else 'Missing'}")
        app.logger.info(f"✅ YouTube API key: {'Set' if app.config.get('YOUTUBE_API_KEY') else 'Missing'}")
        app.logger.info(f"✅ Frontend URL: {app.config.get('FRONTEND_URL', 'Not set')}")
        
        # ✅ Fail fast if critical production settings are wrong
        if not app.config.get('JWT_COOKIE_SECURE'):
            app.logger.warning("⚠️ JWT_COOKIE_SECURE is False in production!")

class TestingConfig(Config):
    """Testing environment configuration"""

    TESTING = True
    DEBUG = True

    # Use separate test database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'TEST_DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/raphael_test'
    )

    # Disable Redis in tests (or use separate instance)
    REDIS_URL = None

    # Fast password hashing for tests
    BCRYPT_LOG_ROUNDS = 4

    @staticmethod
    def init_app(app):
        app.logger.info("🧪 Testing mode enabled")


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """
    Get configuration based on environment.

    Priority:
    1. RAILWAY_ENVIRONMENT (set by Railway)
    2. FLASK_ENV (set by user)
    3. Default to development

    Returns:
        Config: Configuration class
    """
    # Railway sets RAILWAY_ENVIRONMENT=production
    if os.getenv('RAILWAY_ENVIRONMENT') == 'production':
        return ProductionConfig

    # Otherwise use FLASK_ENV
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, DevelopmentConfig)
