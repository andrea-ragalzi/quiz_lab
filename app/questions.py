"""Load and validate the question bank."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.exc import SQLAlchemyError

from app.domain import CATEGORY_LABELS, DIFFICULTIES, OPTION_COUNT
from app.extensions import db
from app.models import QuestionSnapshot
from app.repositories.questions import QuestionRepository

STATIC_IT_PATH = Path(__file__).resolve().parent.parent / "data" / "questions_it.json"
STATIC_DIFFICULTIES = {"facile": "easy", "medio": "medium", "difficile": "hard"}


def validate_question(question: Mapping[str, Any]) -> QuestionSnapshot:
    """Reject malformed questions before they enter storage or gameplay.

    Returns the validated fields as a typed snapshot.
    """
    for key in ("id", "category", "text", "explanation"):
        if not isinstance(question.get(key), str) or not question[key].strip():
            raise ValueError(f"Question {key} must be a nonempty string.")
    options = question.get("options")
    if (
        not isinstance(options, list)
        or len(options) != OPTION_COUNT
        or any(not isinstance(item, str) or not item.strip() for item in options)
        or len({item.strip().casefold() for item in options}) != OPTION_COUNT
    ):
        raise ValueError("Questions need four distinct nonempty options.")
    index = question.get("correct_index")
    if type(index) is not int or not 0 <= index < OPTION_COUNT:
        raise ValueError("The correct option index must be between zero and three.")
    if question.get("difficulty") not in DIFFICULTIES:
        raise ValueError("Unknown difficulty.")
    return {
        "id": question["id"],
        "category": question["category"],
        "difficulty": question["difficulty"],
        "text": question["text"],
        "options": options,
        "correct_index": index,
        "explanation": question["explanation"],
    }


def load_static_questions(path: Path = STATIC_IT_PATH) -> list[QuestionSnapshot]:
    """Map the supplied static archive to existing columns, without executing code."""
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("The question archive must be a nonempty array.")
    questions: list[QuestionSnapshot] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each question must be an object.")
        for key in (
            "id",
            "category",
            "category_label",
            "difficulty",
            "title",
            "description",
            "explanation",
            "source_url",
        ):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError(f"Question {key} must be a nonempty string.")
        if record["category"] not in CATEGORY_LABELS:
            raise ValueError("Unknown static question category.")
        if record["category_label"] != CATEGORY_LABELS[record["category"]]:
            raise ValueError("The category label does not match its identifier.")
        if record["difficulty"] not in STATIC_DIFFICULTIES:
            raise ValueError("Unknown static question difficulty.")
        if "code" not in record or (
            record["code"] is not None and not isinstance(record["code"], str)
        ):
            raise ValueError("Question code must be a string or null.")
        source = urlsplit(record["source_url"])
        if source.scheme != "https" or not source.netloc:
            raise ValueError("Question source must be an HTTPS URL.")
        if record["id"] in seen_ids or record["title"] in seen_titles:
            raise ValueError("Duplicate question ID or title.")
        seen_ids.add(record["id"])
        seen_titles.add(record["title"])
        candidate = {
            "id": record["id"],
            "category": record["category"],
            "difficulty": STATIC_DIFFICULTIES[record["difficulty"]],
            "text": "\n\n".join(
                filter(
                    None,
                    (
                        record["title"],
                        record["code"],
                    ),
                )
            ),
            "options": record.get("options"),
            "correct_index": record.get("correct_index"),
            "explanation": " ".join((record["description"], record["explanation"])),
        }
        questions.append(validate_question(candidate))
    return questions


def import_static_questions(path: Path = STATIC_IT_PATH) -> int:
    """Upsert an entirely validated archive atomically, preserving round snapshots."""
    questions = load_static_questions(path)
    try:
        QuestionRepository(db.session).upsert_many(questions)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return len(questions)
