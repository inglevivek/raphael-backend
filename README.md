# Raphael Backend MVP

AI-powered personalized course generation platform backend.

## Features

- **User Authentication**: JWT-based auth with bcrypt password hashing
- **Course Generation**: 4-stage AI pipeline using Google Gemini
- **Video Integration**: Automatic YouTube video search and embedding
- **RESTful API**: Clean architecture with repository-service-controller pattern
- **Single User Focus**: Simplified MVP for rapid development

## Tech Stack

- **Framework**: Flask 3.0
- **Database**: SQLite (dev), PostgreSQL-ready
- **AI**: Google Gemini Pro
- **Video**: YouTube Data API v3
- **Auth**: JWT (flask-jwt-extended)
- **ORM**: SQLAlchemy 2.0

## Installation

### Prerequisites

- Python 3.9+
- Google Gemini API key
- YouTube Data API key

### Setup

1. Clone repository:
