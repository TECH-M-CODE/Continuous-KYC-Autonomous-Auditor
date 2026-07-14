"""Synthetic director/UBO seeding for entity_persons.

Gives 15-20 watched entities 2-4 directors each, deliberately planting:

  (a) 4 names that are EXACT matches against real rows in
      data/sanctions/opensanctions_targets_cleaned.parquet (verified below,
      not invented) -> true-positive screening hits.
  (b) 3 typo/transliteration variants of those same names -> fuzzy-match
      screening hits (for rapidfuzz-based screening.py).
  (c) One of the exact-match names ("Scott Howell") reused on a second,
      unrelated entity -> the entity-resolution "false positive" trap: an
      innocent director who happens to share a name with a sanctioned
      individual.
  (d) Two pairs of entities sharing a genuine director (same synthetic
      person intentionally reused) -> gives Dev 1's Network Propagator
      something to traverse.

SCHEMA GAP (flagged, not fixed here): the Sprint 2 plan's trap is "matching
name, DIFFERENT DOB/nationality" -- app/models/entities.py's EntityPerson
has no date_of_birth or nationality column, only person_name/role/
ownership_percentage. This script cannot distinguish the trap structurally
from case (a); it only encodes the name collision. Real disambiguation
needs those columns, which belong to Dev 1's model and are out of scope
here. Do not read this trap as fully solving entity resolution.

Idempotent: clears entity_persons before inserting, like seed_entities.py
clears entities. There is no repository for entity_persons (none of the
UnitOfWork's repos cover it), so this writes through uow.session directly,
the same way seed_entities.py does for its own cleanup.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from app.models.base import Base, engine
from app.models.entities import Entity, EntityPerson
from app.repositories.unit_of_work import UnitOfWork

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
NUM_SEED_ENTITIES = 18  # within the plan's 15-20 range
MIN_DIRECTORS_PER_ENTITY = 2
MAX_DIRECTORS_PER_ENTITY = 4

ROLES = ("UBO", "DIRECTOR", "SHAREHOLDER", "SIGNATORY")
OWNERSHIP_ROLES = frozenset({"UBO", "SHAREHOLDER"})

# Verified present in data/sanctions/opensanctions_targets_cleaned.parquet
# (schema == "Person"), exact string + casing as stored in that dataset.
EXACT_MATCH_NAMES: tuple[str, ...] = (
    "Scott Howell",
    "Pierre Cahuzac",
    "CARLA DENISE MESKIL",
    "Jocelyn TEH",
)

# Typo / transliteration variants of three of the names above.
FUZZY_VARIANT_NAMES: tuple[str, ...] = (
    "Scot Howel",
    "Piere Cahuzac",
    "Carla D. Meskill",
)

# Reuses "Scott Howell" on an unrelated entity: same name, different real
# person (see SCHEMA GAP note above for why this can't be proven structurally).
TRAP_NAME = "Scott Howell"

# Same synthetic person intentionally reused across two entities each,
# for the Network Propagator to traverse.
SHARED_DIRECTOR_NAMES: tuple[str, str] = ("Daniel Whitfield", "Amara Osei")

_FIRST_NAMES = (
    "James", "Maria", "Wei", "Fatima", "Lucas", "Olga", "Kenji", "Priya",
    "Ahmed", "Sofia", "Noah", "Ingrid", "Tariq", "Elena", "Hiroshi", "Grace",
    "Mateus", "Chidi", "Anya", "Rafael",
)
_LAST_NAMES = (
    "Okafor", "Novak", "Tanaka", "Silva", "Kowalski", "Haddad", "Larsen",
    "Menon", "Rossi", "Dubois", "Petrova", "Nguyen", "Farrell", "Costa",
    "Weiss", "Adeyemi", "Marsh", "Ibrahim", "Sato", "Cohen",
)


@dataclass(frozen=True, slots=True)
class DirectorSpec:
    person_name: str
    role: str
    ownership_percentage: float | None
    note: str  # why this row exists (logged, not persisted)


def _generic_name(rng: random.Random, used: set[str]) -> str:
    for _ in range(100):
        name = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("exhausted generic name pool without finding a unique name")


def _ownership_for(role: str, rng: random.Random) -> float | None:
    return round(rng.uniform(5.0, 75.0), 1) if role in OWNERSHIP_ROLES else None


def build_director_specs(entities: list[Entity], rng: random.Random) -> dict[str, list[DirectorSpec]]:
    """Map entity_id -> list of DirectorSpec, honoring all four planted scenarios."""
    if len(entities) < 12:
        raise ValueError(f"need at least 12 watched entities to plant all scenarios, got {len(entities)}")

    plan: dict[str, list[DirectorSpec]] = {e.id: [] for e in entities}
    used_names: set[str] = set()

    def plant(entity_index: int, name: str, role: str, note: str) -> None:
        used_names.add(name)
        plan[entities[entity_index].id].append(
            DirectorSpec(person_name=name, role=role, ownership_percentage=_ownership_for(role, rng), note=note)
        )

    # (a) exact sanctions matches
    plant(0, EXACT_MATCH_NAMES[0], "DIRECTOR", "exact sanctions match")
    plant(1, EXACT_MATCH_NAMES[1], "UBO", "exact sanctions match")
    plant(2, EXACT_MATCH_NAMES[2], "SHAREHOLDER", "exact sanctions match")
    plant(3, EXACT_MATCH_NAMES[3], "DIRECTOR", "exact sanctions match")

    # (b) fuzzy variants
    plant(4, FUZZY_VARIANT_NAMES[0], "DIRECTOR", "fuzzy variant of exact match")
    plant(5, FUZZY_VARIANT_NAMES[1], "UBO", "fuzzy variant of exact match")
    plant(6, FUZZY_VARIANT_NAMES[2], "SHAREHOLDER", "fuzzy variant of exact match")

    # (c) same-name-different-person trap: reuses EXACT_MATCH_NAMES[0] on an
    # unrelated entity. Deliberately NOT added to `used_names` exclusion for
    # this specific name (it's supposed to collide).
    plan[entities[7].id].append(
        DirectorSpec(
            person_name=TRAP_NAME,
            role="SIGNATORY",
            ownership_percentage=None,
            note="false-positive trap: same name as entity 0's director, different real person",
        )
    )

    # (d) two shared-director pairs (genuine link, for the propagator)
    plant(8, SHARED_DIRECTOR_NAMES[0], "DIRECTOR", "shared director pair 1a")
    plant(9, SHARED_DIRECTOR_NAMES[0], "UBO", "shared director pair 1b")
    plant(10, SHARED_DIRECTOR_NAMES[1], "DIRECTOR", "shared director pair 2a")
    plant(11, SHARED_DIRECTOR_NAMES[1], "DIRECTOR", "shared director pair 2b")

    # Fill every entity up to its randomly chosen director count (2-4) with
    # generic, non-colliding names.
    for entity in entities:
        target_count = rng.randint(MIN_DIRECTORS_PER_ENTITY, MAX_DIRECTORS_PER_ENTITY)
        specs = plan[entity.id]
        while len(specs) < target_count:
            role = rng.choice(ROLES)
            name = _generic_name(rng, used_names)
            specs.append(
                DirectorSpec(person_name=name, role=role, ownership_percentage=_ownership_for(role, rng), note="generic fill")
            )

    return plan


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    rng = random.Random(RANDOM_SEED)

    with UnitOfWork() as uow:
        watched = sorted(uow.entities.list(watched=True), key=lambda e: e.id)
        if len(watched) < NUM_SEED_ENTITIES:
            logger.warning(
                "only %d watched entities available (wanted %d); using all of them",
                len(watched), NUM_SEED_ENTITIES,
            )
        seed_entities = watched[:NUM_SEED_ENTITIES]

        plan = build_director_specs(seed_entities, rng)

        # Clean re-run: entity_persons has no dedicated repository, so we go
        # through uow.session directly, same as seed_entities.py does.
        deleted = uow.session.query(EntityPerson).delete()
        uow.commit()
        logger.info("cleared %d existing entity_persons rows", deleted)

        total_directors = 0
        for entity in seed_entities:
            for spec in plan[entity.id]:
                uow.session.add(
                    EntityPerson(
                        entity_id=entity.id,
                        person_name=spec.person_name,
                        role=spec.role,
                        ownership_percentage=spec.ownership_percentage,
                    )
                )
                total_directors += 1
                logger.info("%s <- %r (%s) [%s]", entity.id, spec.person_name, spec.role, spec.note)
        uow.commit()

    logger.info(
        "seeded %d directors across %d entities (exact=%d fuzzy=%d trap=1 shared_pairs=2)",
        total_directors, len(seed_entities), len(EXACT_MATCH_NAMES), len(FUZZY_VARIANT_NAMES),
    )


if __name__ == "__main__":
    seed()
