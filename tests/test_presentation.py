"""Question layout: prose stays proportional, only real code becomes a code block."""

import json
from pathlib import Path

import pytest

from app.web.presentation import QuestionPart, question_layout

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "questions_it.json"


def test_every_bank_question_splits_into_title_and_optional_code():
    for record in json.loads(ARCHIVE.read_text(encoding="utf-8")):
        text = "\n\n".join(filter(None, (record["title"], record["code"])))
        layout = question_layout(text)
        assert layout.prompt == record["title"], record["id"]
        expected = (QuestionPart("code", record["code"]),) if record["code"] else ()
        assert layout.parts == expected, record["id"]


@pytest.mark.parametrize(
    ("text", "prompt", "parts"),
    [
        # Historical snapshot: title, hint, then code.
        (
            "Quanto vale la lunghezza di questa stringa?\n\n"
            "La funzione len() conta anche gli spazi presenti nella stringa.\n\n"
            'print(len("ciao mondo"))',
            "Quanto vale la lunghezza di questa stringa?",
            (
                QuestionPart(
                    "text",
                    "La funzione len() conta anche gli spazi presenti nella stringa.",
                ),
                QuestionPart("code", 'print(len("ciao mondo"))'),
            ),
        ),
        # Hint ending in closing guillemets is still prose.
        (
            "Qual è una limitazione?\n\nConfronta «il cane» e «il gatto».",
            "Qual è una limitazione?",
            (QuestionPart("text", "Confronta «il cane» e «il gatto»."),),
        ),
        # Bare code without a title, with a blank line inside the snippet.
        (
            "def grow(x):\n    return x * 4 + 2\n\nprint(grow(5))",
            None,
            (
                QuestionPart(
                    "code", "def grow(x):\n    return x * 4 + 2\n\nprint(grow(5))"
                ),
            ),
        ),
        # An expression without sentence punctuation is code.
        ("9 > 2 and 2 < 1", None, (QuestionPart("code", "9 > 2 and 2 < 1"),)),
        # English legacy prose.
        (
            "Why should training and inference use compatible tokenization?",
            "Why should training and inference use compatible tokenization?",
            (),
        ),
        # Assignments are code even when a line ends with a period-like token.
        (
            'Che cosa stampa?\n\nname = "Ada."\nprint(name)',
            "Che cosa stampa?",
            (QuestionPart("code", 'name = "Ada."\nprint(name)'),),
        ),
        # Windows line endings and surrounding blank lines are tolerated.
        (
            "\r\nChe cosa stampa?\r\n\r\nprint(7 // 2)\r\n",
            "Che cosa stampa?",
            (QuestionPart("code", "print(7 // 2)"),),
        ),
    ],
)
def test_historical_snapshot_shapes(text, prompt, parts):
    layout = question_layout(text)
    assert layout.prompt == prompt
    assert layout.parts == parts


def test_sentence_mentioning_python_syntax_is_not_code():
    layout = question_layout("Che cosa fa x = 3 in Python?")
    assert layout.prompt == "Che cosa fa x = 3 in Python?"
    assert layout.parts == ()


def test_empty_text_has_no_prompt_and_no_parts():
    assert question_layout("") == (None, ())
