import os

from dotenv import load_dotenv

load_dotenv()


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///./shop.db"
    # Supabase/Neon give postgres:// or postgresql:// - SQLAlchemy needs a driver name
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _db_url()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")
MAILGUN_FROM = os.getenv("MAILGUN_FROM", "")
MAILGUN_API_BASE = os.getenv("MAILGUN_API_BASE", "https://api.mailgun.net")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
