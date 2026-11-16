import random

from app.quiz.service import take_questions


def test_shuffle_bag_exhausts_before_refilling_and_avoids_boundary_repeat():
    state = {}
    first, state = take_questions(["a", "b", "c"], state, 3, random.Random(2))
    second, state = take_questions(["a", "b", "c"], state, 3, random.Random(3))
    assert set(first) == set(second) == {"a", "b", "c"}
    assert first[-1] != second[0]
    assert state["remaining"] == []


def test_bag_resumes_and_rebuilds_after_catalog_change():
    first, state = take_questions(["a", "b", "c"], {}, 1, random.Random(0))
    rest, state = take_questions(["a", "b", "c"], state, 2, random.Random(0))
    assert len(set(first + rest)) == 3
    changed, _ = take_questions(["x", "y"], state, 2, random.Random(0))
    assert set(changed) == {"x", "y"}
