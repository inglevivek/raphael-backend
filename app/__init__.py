from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from app.utils.redis.client import redis_client
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app(config_class=None):
    """
    Create Flask application with automatic config detection.
    
    Args:
        config_class: Configuration class (auto-detected if None)
    """
    app = Flask(__name__)
    
    limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
     storage_uri=app.config.get('REDIS_URL', 'memory://')   # Use REDIS_URL from config
)
    # ✅ Load configuration from class (not string)
    if config_class is None:
        from config import get_config
        config_class = get_config()
    
    app.config.from_object(config_class)
    
    # Initialize config (validation + logging)
    config_class.init_app(app)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    redis_client.init_app(app)
    
    from app import models
    
    # Configure CORS
    CORS(app,
         origins=[app.config['FRONTEND_URL']],
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        return response
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
    
    return app