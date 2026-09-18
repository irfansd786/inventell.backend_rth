from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()

DB_PATH = Path(__file__).resolve().parent.parent.parent / "invintell_dev.db"


def _create_engine():
    url = settings.DATABASE_URL
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    if url.startswith('sqlite'):
        return create_engine(url, connect_args={'check_same_thread': False}, pool_pre_ping=True)

    try:
        eng = create_engine(url, pool_pre_ping=True)
        # Verify database connection works (handles unreachable localhost or invalid credentials)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception as exc:
        print(f'[INVINTELL] WARNING: Database connection failed ({exc}). Falling back to local SQLite dev database at {DB_PATH}.')
        return create_engine(
            f'sqlite:///{DB_PATH}',
            connect_args={'check_same_thread': False},
            pool_pre_ping=True,
        )


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_users_table():
    """Ensure newly added columns exist in users table on local SQLite."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            if res:
                col_names = {row[1] for row in res}
                if 'firebase_uid' not in col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(128)"))
                if 'status' not in col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
                if 'assigned_modules' not in col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN assigned_modules TEXT DEFAULT '[]'"))
                if 'last_login' not in col_names:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_login TIMESTAMP"))
                conn.commit()
    except Exception:
        pass


_migrate_users_table()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
