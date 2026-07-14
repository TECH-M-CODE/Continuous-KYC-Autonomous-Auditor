"""Synthetic account -> entity mapping for the sampled SAML-D transactions.

Two populations, by design:

  * "Suspicious-heavy" accounts (the busiest accounts in Is_laundering=1
    rows) are mapped onto a deterministic pool of watched entities -> when
    ingestion/transactions.py replays these accounts, the anomaly resolves
    to an entity that should plausibly get flagged.
  * A sample of "normal" accounts (never seen in a laundering row) is
    mapped onto the FULL entity pool (watched and unwatched alike) -> a
    realistic false-positive surface, so not every entity with transaction
    activity is inherently suspicious.

NOTE on "high-risk": entities.risk_band is uninformative in the current
seed data (see build_account_map.py's caller docs / gen_directors.py
sibling note) -- every watched entity's risk_band computes to "LOW" because
seed_entities.py's max achievable base_score (37) never crosses its own
"medium" threshold (40). That's Dev 1's seeding logic and out of scope
here, so this script uses the `watched` boolean, which is computed
correctly, as the high-risk signal instead.

Idempotent (clears account_entity_map before inserting) and fully
reproducible via random.seed(RANDOM_SEED).
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

import pandas as pd

from app.models.base import Base, engine
from app.models.entities import AccountEntityMap
from app.repositories.unit_of_work import UnitOfWork

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
TXN_SAMPLE_PATH = Path("data/processed/txn_sample.parquet")

SUSPICIOUS_ACCOUNT_LIMIT = 40
HIGH_RISK_ENTITY_POOL_SIZE = 15
NORMAL_ACCOUNT_COUNT = 80


def _top_laundering_accounts(df: pd.DataFrame, limit: int) -> list[int]:
    """The `limit` accounts appearing most often as sender/receiver of a laundering row."""
    laundering = df[df["Is_laundering"] == 1]
    counts = pd.concat([laundering["Sender_account"], laundering["Receiver_account"]]).value_counts()
    return counts.head(limit).index.tolist()


def _normal_accounts(df: pd.DataFrame, exclude: set[int], count: int, rng: random.Random) -> list[int]:
    """`count` accounts that never appear in a laundering row, excluding `exclude`."""
    laundering_accounts = set(
        pd.concat([df.loc[df["Is_laundering"] == 1, "Sender_account"], df.loc[df["Is_laundering"] == 1, "Receiver_account"]])
    )
    all_accounts = set(pd.concat([df["Sender_account"], df["Receiver_account"]]))
    candidates = sorted(all_accounts - laundering_accounts - exclude)
    if len(candidates) < count:
        logger.warning("only %d normal-account candidates available (wanted %d)", len(candidates), count)
        return candidates
    return rng.sample(candidates, count)


def build_account_map() -> None:
    if not TXN_SAMPLE_PATH.exists():
        raise FileNotFoundError(f"{TXN_SAMPLE_PATH} not found; run data/prep/prep_transactions.py first")

    Base.metadata.create_all(bind=engine)
    rng = random.Random(RANDOM_SEED)

    df = pd.read_parquet(TXN_SAMPLE_PATH, columns=["Sender_account", "Receiver_account", "Is_laundering"])

    with UnitOfWork() as uow:
        all_entities = uow.entities.list()
        watched_entities = [e for e in all_entities if e.watched]
        if len(watched_entities) < HIGH_RISK_ENTITY_POOL_SIZE:
            raise ValueError(
                f"need at least {HIGH_RISK_ENTITY_POOL_SIZE} watched entities, got {len(watched_entities)}; "
                "run data/seed/seed_entities.py first"
            )

        high_risk_pool = rng.sample(watched_entities, HIGH_RISK_ENTITY_POOL_SIZE)

        suspicious_accounts = _top_laundering_accounts(df, SUSPICIOUS_ACCOUNT_LIMIT)
        normal_accounts = _normal_accounts(df, exclude=set(suspicious_accounts), count=NORMAL_ACCOUNT_COUNT, rng=rng)

        mappings: list[tuple[str, str]] = []  # (account_no, entity_id)
        for account in suspicious_accounts:
            entity = rng.choice(high_risk_pool)
            mappings.append((str(account), entity.id))
        for account in normal_accounts:
            entity = rng.choice(all_entities)
            mappings.append((str(account), entity.id))

        deleted = uow.session.query(AccountEntityMap).delete()
        uow.commit()
        logger.info("cleared %d existing account_entity_map rows", deleted)

        for account_no, entity_id in mappings:
            uow.session.add(AccountEntityMap(account_no=account_no, entity_id=entity_id))
        uow.commit()

    logger.info(
        "mapped %d suspicious accounts onto %d high-risk entities, %d normal accounts onto the full %d-entity pool",
        len(suspicious_accounts), len(high_risk_pool), len(normal_accounts), len(all_entities),
    )


if __name__ == "__main__":
    build_account_map()
