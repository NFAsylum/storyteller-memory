"""Seed 3 fake characters into the world_state DB. Re-runnable (clears the seed session first).

Run: poetry run python scripts/seed_test_data.py
"""

from __future__ import annotations

from core.db import get_engine, get_sessionmaker
from core.memory.world_state import Base, Character, WorldState

SEED_SESSION = "seed"
FAKE_CHARACTERS = [
    ("Aria", ["leal", "corajosa"]),
    ("Vex", ["ambicioso", "traiçoeiro"]),
    ("Doran", ["justo", "cansado"]),
]


def main() -> int:
    engine = get_engine()
    # Safety net so the script runs standalone; a no-op if migrations already created them.
    Base.metadata.create_all(engine)

    with get_sessionmaker(engine)() as session:
        world = WorldState(session)
        for existing in world.list(Character, SEED_SESSION):
            world.delete(existing)
        for turn, (name, traits) in enumerate(FAKE_CHARACTERS, start=1):
            world.add(
                Character(
                    session_id=SEED_SESSION,
                    name=name,
                    traits=traits,
                    first_appeared_turn=turn,
                    last_seen_turn=turn,
                )
            )
        world.commit()
        count = len(world.list(Character, SEED_SESSION))

    print(f"{count} of {len(FAKE_CHARACTERS)} fake characters seeded into session {SEED_SESSION!r}")
    return 0 if count == len(FAKE_CHARACTERS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
