from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from app.utils.redis.client import redis_client
from werkzeug.middleware.proxy_fix import ProxyFix
import os


# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=None):
    """
    Create Flask application.
    
    Args:
        config_class: Configuration class (defaults to Config)
    """
    app = Flask(__name__)
    
    # Load configuration
    if config_class is None:
        from config import Config
        config_class = Config
    
    app.config.from_object(config_class)
    
    # Initialize config (validation + logging)
    config_class.init_app(app)
    
    # Add ProxyFix middleware for Railway reverse proxy
    if os.getenv('RAILWAY_ENVIRONMENT') == 'production':
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_port=1,
            x_prefix=1
        )
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    redis_client.init_app(app)
    
    from app import models
    
    # Configure CORS
    allowed_origins = [
        'http://localhost:5000',
        'http://localhost:3000',
        app.config.get('FRONTEND_URL', 'http://localhost:3000')
    ]
    allowed_origins = list(dict.fromkeys([origin for origin in allowed_origins if origin]))
    
    CORS(app,
         origins=allowed_origins,
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    
    # Import and register blueprints
    with app.app_context():
        from app.main.routes import main_bp
        app.register_blueprint(main_bp)
        
        from app.main.auth.routes import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        
        from app.main.courses.routes import courses_bp
        app.register_blueprint(courses_bp, url_prefix='/api/courses')
        
        from app.main.errors import register_error_handlers
        register_error_handlers(app)
        
        # Run database migrations on startup (production only)
        if os.getenv('RAILWAY_ENVIRONMENT') == 'production':
            try:
                from flask_migrate import upgrade
                app.logger.info("🔄 Running database migrations...")
                upgrade()
                app.logger.info("✅ Database migrations completed successfully")
                
                # Verify database connection
                db.session.execute(db.text('SELECT 1'))
                app.logger.info("✅ Database connection verified")
            except Exception as e:
                app.logger.error(f"❌ Database migration/connection error: {e}")
    
    return app
