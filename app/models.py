"""
Database models for Raphael backend.
SQLAlchemy ORM models for User and Course entities.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index


db = SQLAlchemy()


class User(db.Model):
    """User model for authentication and course ownership."""
    
    __tablename__ = 'users'
    
    # Fields
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    courses = db.relationship('Course', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """
        Convert user to dictionary representation.
        Excludes sensitive data like password_hash.
        
        Returns:
            dict: User data with id, email, name, created_at
        """
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<User {self.email}>'


class Course(db.Model):
    """Course model for storing generated course metadata."""
    
    __tablename__ = 'courses'
    
    # Fields
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    topic = db.Column(db.String(200), nullable=False)
    level = db.Column(db.String(20), nullable=False)  # beginner|intermediate|advanced
    status = db.Column(db.String(20), nullable=False, default='generating', index=True)  # generating|completed|failed
    json_path = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_user_status', 'user_id', 'status'),
    )
    
    def to_dict(self, include_content=False, base_dir=None):
        """
        Convert course to dictionary representation.
        
        Args:
            include_content (bool): Whether to include JSON content
            base_dir (Path): Base directory for loading content
        
        Returns:
            dict: Course data
        """
        data = {
            'id': self.id,
            'topic': self.topic,
            'level': self.level,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
        
        if self.error_message:
            data['error_message'] = self.error_message
        
        if include_content and self.json_path and base_dir:
            from app.utils.storage import JSONStorage
            try:
                data['content'] = JSONStorage.load_course(self.json_path, base_dir)
            except Exception:
                data['content'] = None
        
        return data
    
    def __repr__(self):
        return f'<Course {self.id}: {self.topic}>'
