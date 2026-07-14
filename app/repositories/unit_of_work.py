from app.models.base import SessionLocal
from app.repositories.entity_repo import EntityRepository
from app.repositories.event_repo import RawEventRepository
from app.repositories.risk_repo import RiskEventRepository
from app.repositories.alert_repo import AlertRepository
from app.repositories.sar_repo import SARRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.sanctions_repo import SanctionsRepository

class UnitOfWork:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.session = None

    def __enter__(self):
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
            if self.session:
                self.session.close()

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
