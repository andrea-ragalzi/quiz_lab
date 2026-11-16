from app.quiz.draw_state import DrawState, read_state, write_state


def test_legacy_bag_retains_global_state_when_category_is_written():
    legacy = {"version": "v1", "remaining": ["a"], "last": "b"}
    topic: DrawState = {"version": "v2", "remaining": ["c"], "last": None}
    updated = write_state(legacy, "python", topic)
    assert read_state(updated, None) == {**legacy, "categories": {"python": topic}}
    assert read_state(updated, "python") == topic
    assert legacy == {"version": "v1", "remaining": ["a"], "last": "b"}


def test_current_bag_preserves_categories_when_global_state_is_written():
    topic: DrawState = {"version": "v2", "remaining": ["c"], "last": None}
    bag = {
        "version": "v1",
        "remaining": ["a"],
        "last": "b",
        "categories": {"python": topic},
    }
    next_state: DrawState = {"version": "v3", "remaining": [], "last": "a"}
    updated = write_state(bag, None, next_state)
    assert updated == {**next_state, "categories": {"python": topic}}
    assert read_state(updated, "python") == topic
    assert read_state(updated, "nlp") == {}


def test_first_category_draw_does_not_create_global_state():
    state: DrawState = {"version": "v1", "remaining": [], "last": "a"}
    assert write_state({}, "python", state) == {"categories": {"python": state}}
