import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:123@localhost:5432/chatbot")
    COHERE_API_KEY = os.getenv("COHERE_API_KEY", "your-cohere-api-key")
    CORS_ORIGINS = ["http://localhost:3000"]
    JWT_ALGORITHM = "HS256"


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
