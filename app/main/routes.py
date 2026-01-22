"""
Main application routes (health check, etc.).
"""
from flask import Blueprint, jsonify, current_app
from datetime import datetime
from app import db
from app.utils.redis.client import redis_client


main_bp = Blueprint('main', __name__)


@main_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint with database and Redis connectivity checks.
    
    Returns:
        tuple: (response, status_code)
        - 200: Service is healthy
        - 503: Service unhealthy (database/Redis issues)
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {
            'database': 'unknown',
            'redis': 'unknown'
        }
    }
    
    status_code = 200
    
    # Check database connectivity
    try:
        db.session.execute(db.text('SELECT 1'))
        health_status['checks']['database'] = 'connected'
    except Exception as e:
        health_status['checks']['database'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
        status_code = 503
        current_app.logger.error(f"Database health check failed: {e}")
    
    # Check Redis connectivity
    try:
        if redis_client.is_connected():
            health_status['checks']['redis'] = 'connected'
        else:
            health_status['checks']['redis'] = 'disconnected'
            # Redis is optional, so don't fail health check
            current_app.logger.warning("Redis is disconnected but service continues")
    except Exception as e:
        health_status['checks']['redis'] = f'error: {str(e)}'
        # Redis is optional, so don't fail health check
        current_app.logger.warning(f"Redis health check failed: {e}")
    
    return jsonify(health_status), status_code
