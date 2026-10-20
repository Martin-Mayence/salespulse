import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def get_connection():
    """Ouvre une connexion à la base SalesPulse."""
    required = [
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    ]

    missing = [
        key for key in required
        if not os.getenv(key)
    ]

    if missing:
        raise RuntimeError(
            f"Variables manquantes dans .env : {missing}"
        )

    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


def test_connection():
    """Vérifie que PostgreSQL répond."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            return cur.fetchone()[0]