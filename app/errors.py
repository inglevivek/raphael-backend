"""
Global error handlers for Flask application.
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException

from app.exceptions import BaseAPIException
from app.utils.logger import get_logger


logger = get_logger(__name__)


def register_error_handlers(app):
    """
    Register global error handlers.
    
    Args:
        app (Flask): Flask application instance
    """
    
    @app.errorhandler(BaseAPIException)
    def handle_api_exception(error):
        """Handle custom API exceptions."""
        logger.warning(f"API Exception: {error.message}")
        return jsonify(error.to_dict()), error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 Not Found errors."""
        return jsonify({
            'error': 'Resource not found',
            'status_code': 404
        }), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 Internal Server Error."""
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'status_code': 500
        }), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle all other HTTP exceptions."""
        return jsonify({
            'error': error.description,
            'status_code': error.code
        }), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle all unexpected exceptions."""
        logger.error(f"Unexpected error: {str(error)}", exc_info=True)
        return jsonify({
            'error': 'An unexpected error occurred',
            'status_code': 500
        }), 500
