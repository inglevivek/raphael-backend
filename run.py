"""
Application entry point.
"""
import os
from app import create_app, db
from app.models import User, Course
from config import Config


app = create_app(Config)

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {
        'db': db,
        'User': User,
        'Course': Course
    }

@app.cli.command('init-db')
def init_db_command():
    """Initialize database tables."""
    db.create_all()
    print("✅ Database tables created successfully!")

@app.cli.command('reset-db')
def reset_db_command():
    """Drop and recreate all database tables."""
    db.drop_all()
    db.create_all()
    print("✅ Database reset successfully!")

if __name__ == '__main__':
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=debug)
