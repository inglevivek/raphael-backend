"""
Flask application factory.
"""
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from config import config
from app.models import db
from app.errors import register_error_handlers
from app.utils.logger import get_logger


logger = get_logger(__name__)
migrate = Migrate()
jwt = JWTManager()


def create_app(config_name='development'):
    """
    Create and configure Flask application.
    
    Args:
        config_name (str): Configuration environment name
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    config[config_name].init_app()
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    from app.main import main_bp
    from app.main.auth import auth_bp
    from app.main.courses import courses_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    
    logger.info(f"Flask app created with config: {config_name}")
    
    return app
