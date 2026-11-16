"""Check the server-rendered contract for progressive password controls."""

from html.parser import HTMLParser

import pytest


class FormControls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        self.toggles = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and "id" in attributes:
            self.inputs[attributes["id"]] = attributes
        if tag == "button" and "data-password-label" in attributes:
            self.toggles.append(attributes)


@pytest.mark.parametrize(
    ("route", "fields", "autocomplete"),
    [
        ("/auth/login", {"password"}, "current-password"),
        ("/auth/register", {"password", "confirm"}, "new-password"),
    ],
)
def test_password_controls_target_masked_fields_and_wait_for_javascript(
    client, route, fields, autocomplete
):
    response = client.get(route)
    assert response.status_code == 200
    parser = FormControls()
    parser.feed(response.get_data(as_text=True))
    assert {button["aria-controls"] for button in parser.toggles} == fields
    for button in parser.toggles:
        assert button["type"] == "button"
        assert button["aria-pressed"] == "false"
        assert "hidden" in button
        field = parser.inputs[button["aria-controls"]]
        assert field["type"] == "password"
        assert field["autocomplete"] == autocomplete
