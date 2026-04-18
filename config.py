"""
Configuration module for Raphael backend.
✅ UPDATED: Added Auth0 configuration for complete authentication
"""
import os

class Config:
    """Application configuration"""
    
    # ==========================================
    # FLASK SETTINGS
    # ==========================================
    SECRET_KEY = os.getenv('SECRET_KEY', 'asteroiddestroyer911')
    DEBUG = os.getenv('FLASK_ENV', 'development') == 'development'
    
    # ==========================================
    # AUTH0 CONFIGURATION
    # ==========================================
    AUTH0_DOMAIN = os.getenv('AUTH0_DOMAIN', 'dev-chronos.jp.auth0.com')
    AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID', 'BOsFc3puib2P0495rCVvvv5k5IYPWSKj')
    AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET')  # Must be set in environment
    AUTH0_AUDIENCE = os.getenv('AUTH0_AUDIENCE', 'http://127.0.0.1:8000')
    AUTH0_ALGORITHMS = ['RS256']
    RAPHAEL_INTERNAL_SECRET = os.getenv('RAPHAEL_INTERNAL_SECRET', 'asteroiddestroyer911')
    # Auth0 Management API (for user management)
    AUTH0_MGMT_API_AUDIENCE = f'https://{AUTH0_DOMAIN}/api/v2/'
    
    # ==========================================
    # DATABASE (PostgreSQL)
    # ==========================================
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://raphael_admin:viktor911@localhost:5432/raphael-db')
    
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
    REDIS_URL = os.getenv('REDIS_URL', 'redis://:redis_password@localhost:6379/0')
    
    # ==========================================
    # LLM (Groq)
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
    
    


    # ==========================================
    # CORS
    # ==========================================
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    
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
        
        # Auth0 validation
        if not Config.AUTH0_CLIENT_SECRET:
            errors.append("AUTH0_CLIENT_SECRET is required")
        
        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
    
    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        Config.validate()
        app.logger.info("✅ Configuration loaded")
        app.logger.info(f"📊 Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}")
        app.logger.info(f"🔴 Redis: {app.config.get('REDIS_URL', 'Not configured')}")
        app.logger.info(f"🔐 Auth0 Domain: {app.config.get('AUTH0_DOMAIN', 'Not configured')}")
