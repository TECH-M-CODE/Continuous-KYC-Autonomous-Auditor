import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/sentinelai.db")

# Standardize engine url to sync format for standard SQLAlchemy connections
sync_db_url = DATABASE_URL
if sync_db_url.startswith("sqlite+aiosqlite://"):
    sync_db_url = sync_db_url.replace("sqlite+aiosqlite://", "sqlite://")

# Ensure target database folder exists
if sync_db_url.startswith("sqlite:///"):
    db_path = sync_db_url.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        db_dir = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

@event.listens_for(engine, "connect")
def set_wal(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
