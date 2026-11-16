"""Persisted question draw state and selection."""

import hashlib
import random
from collections.abc import Mapping
from typing import Any, NotRequired, TypedDict, cast


class DrawState(TypedDict):
    """Persisted progress through a shuffled question catalog."""

    version: str
    remaining: list[str]
    last: str | None


class UserBag(DrawState):
    """Global state plus optional per-category state; old bags omit categories."""

    categories: NotRequired[dict[str, DrawState]]


def read_state(bag: Mapping[str, Any], category: str | None) -> Mapping[str, Any]:
    if category is None:
        return bag
    return bag.get("categories", {}).get(category, {})


def write_state(
    bag: Mapping[str, Any], category: str | None, state: DrawState
) -> UserBag:
    if category is None:
        return cast(UserBag, {**bag, **state})
    categories = dict(bag.get("categories", {}))
    categories[category] = state
    return cast(UserBag, {**bag, "categories": categories})


def take_questions(
    catalog: list[str],
    state: Mapping[str, Any],
    count: int,
    rng: random.Random,
) -> tuple[list[str], DrawState]:
    """Draw without replacement; retain bounded state across successive rounds."""
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or not 0 <= count <= len(catalog)
    ):
        raise ValueError("A unique catalog and a count within its size are required.")
    version = hashlib.sha256("\n".join(sorted(catalog)).encode()).hexdigest()
    remaining = (
        list(state.get("remaining", [])) if state.get("version") == version else []
    )
    last = state.get("last")
    selected: list[str] = []
    for _ in range(count):
        if not remaining:
            remaining = list(catalog)
            rng.shuffle(remaining)
            if len(remaining) > 1 and remaining[-1] == last:
                remaining[0], remaining[-1] = remaining[-1], remaining[0]
        # Keep questions already selected for a later round.
        index = next(
            i for i in range(len(remaining) - 1, -1, -1) if remaining[i] not in selected
        )
        last = remaining.pop(index)
        selected.append(last)
    return selected, {"version": version, "remaining": remaining, "last": last}
