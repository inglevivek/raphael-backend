from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.main.routes import router as main_router
from app.main.auth.routes import router as auth_router
from app.main.courses.routes import router as course_router
from app.errors import register_exception_handlers
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=".flaskenv", override=True)
app = FastAPI(title="Raphael API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)
app.include_router(auth_router, prefix="/auth")
app.include_router(course_router, prefix="/courses")

register_exception_handlers(app)
