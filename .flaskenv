FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=1
# Database
# DATABASE_URL=postgresql://postgres:QPusIhZHWVxcKjIbVkqcZnBpghIsHqEy@mainline.proxy.rlwy.net:13210/railway
# DATABASE_URL=postgresql://raphael_admin:viktor911@localhost:5432/raphael-db
DATABASE_URL=postgresql://raphael-admin:viktor911@localhost:5433/raphael-db
# API Keys
GEMINI_API_KEY=AIzaSyDp9B_tm2zfhOKchM9PQtnVbt1661cfnFY
YOUTUBE_API_KEY=AIzaSyB6V9x5iFsGeirelFfh4yLrgwwf1C9MSWk
GROQ_API_KEY=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

# Redis
REDIS_URL=redis://:redis_password@localhost:6379/0

# ==========================================
# ✅ AUTH0 CONFIGURATION (NEW)
# ==========================================
AUTH0_DOMAIN=dev-chronos.jp.auth0.com
AUTH0_CLIENT_ID=BOsFc3puib2P0495rCVvvv5k5IYPWSKj
AUTH0_CLIENT_SECRET=bvgZlJRsMOzIAscz-sB3woyq7PCmnaWI6cEnAQtEva7Mv7rlIqL3rAONfB11nZYi
AUTH0_AUDIENCE=http://127.0.0.1:8000
RAPHAEL_INTERNAL_SECRET = asteroiddestroyer911