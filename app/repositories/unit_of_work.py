import threading

from app.models.base import SessionLocal
from app.repositories.entity_repo import EntityRepository
from app.repositories.event_repo import RawEventRepository
from app.repositories.risk_repo import RiskEventRepository
from app.repositories.alert_repo import AlertRepository
from app.repositories.sar_repo import SARRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.sanctions_repo import SanctionsRepository

# Process-wide transaction lock.
#
# SQLite allows a single writer, and the app runs several concurrent producers
# (Loop A ingestion on the scheduler, Loop B agents in worker threads, Loop D
# self-assessment, and API handlers on the event loop). Two of them opening
# separate UnitOfWork transactions at the same time is what broke the
# append-only audit chain: both read "the last audit entry", then both linked
# their new row onto it, forking the hash chain (verify then reports
# "chain integrity compromised"). It also caused sporadic "database is locked".
#
# Serialising every transaction removes both classes of bug: a transaction's
# read snapshot now always reflects all previously-committed writes, so the
# audit chain stays linear. It is an RLock because a few code paths legitimately
# open a nested UnitOfWork on the SAME thread (e.g. sanctions screening opens one
# while the agent's outer one is still in scope) — those must not self-deadlock.
# At this system's scale (transactions are short, LLM/network calls happen
# OUTSIDE any UnitOfWork block) the throughput cost is negligible.
_TXN_LOCK = threading.RLock()


class UnitOfWork:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.session = None
        self._lock_held = False

    def __enter__(self):
        # Acquire BEFORE opening the session so this transaction's read snapshot
        # is established after every prior transaction has committed and released.
        _TXN_LOCK.acquire()
        self._lock_held = True
        self.session = self.session_factory()
        self.entities = EntityRepository(self.session)
        self.events = RawEventRepository(self.session)
        self.risk_events = RiskEventRepository(self.session)
        self.alerts = AlertRepository(self.session)
        self.sars = SARRepository(self.session)
        self.audit_log = AuditRepository(self.session)
        self.sanctions = SanctionsRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.rollback()
        finally:
            try:
                if self.session:
                    self.session.close()
            finally:
                if self._lock_held:
                    self._lock_held = False
                    _TXN_LOCK.release()

    async def __aenter__(self):
        # Async compatibility wrapper mapping to sync session management
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)

    def commit(self):
        if self.session:
            self.session.commit()

    def rollback(self):
        if self.session:
            self.session.rollback()
