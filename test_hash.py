import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.audit import AuditLog
from app.services.audit_service import _normalize_timestamp

engine = create_engine('sqlite:///data/sentinelai.db')
Session = sessionmaker(bind=engine)
session = Session()

entry = session.query(AuditLog).filter_by(entry_hash='a6aad7b970ddda33c4304d4a46e4c489c6f180caace897c62a7b09681d5d6fc5').first()
if entry:
    content = (
        f"{entry.prev_hash}|"
        f"{entry.seq}|"
        f"{entry.actor_id}|"
        f"{entry.action}|"
        f"{entry.payload or ''}|"
        f"{_normalize_timestamp(entry.timestamp)}"
    )
    print("DB content:")
    print(repr(content))
    print(f"Hash of DB content: {hashlib.sha256(content.encode('utf-8')).hexdigest()}")
