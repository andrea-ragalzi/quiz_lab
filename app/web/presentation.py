"""Italian presentation labels, question layout and safe error messages."""

import re
from typing import Literal, NamedTuple

from werkzeug.exceptions import (
    BadRequest,
    MethodNotAllowed,
    NotFound,
    RequestEntityTooLarge,
)

from app.domain.constants import CATEGORY_LABELS, ROUND_LENGTH

LABELS = {
    **CATEGORY_LABELS,
    NotFound.description: "La pagina richiesta non esiste. Controlla l'indirizzo.",
    BadRequest.description: "La richiesta non è valida. Ricarica la pagina e riprova.",
    MethodNotAllowed.description: "Questa operazione non è consentita.",
    RequestEntityTooLarge.description: "La richiesta supera la dimensione consentita.",
    "easy": "Facile",
    "medium": "Medio",
    "hard": "Difficile",
    "Bad Request": "Richiesta non valida",
    "Not Found": "Pagina non trovata",
    "Conflict": "Operazione non disponibile",
    "Method Not Allowed": "Metodo non consentito",
    "Request Entity Too Large": "Richiesta troppo grande",
    "The CSRF token is missing.": (
        "La sessione del modulo non è valida. Ricarica la pagina."
    ),
    "The CSRF token has expired.": "Il modulo è scaduto. Ricarica la pagina e riprova.",
    "The CSRF token is invalid.": (
        "Il modulo non è valido. Ricarica la pagina e riprova."
    ),
    "The CSRF tokens do not match.": (
        "Il modulo non è valido. Ricarica la pagina e riprova."
    ),
    "The CSRF session token is missing.": "La sessione è scaduta. Ricarica la pagina.",
    "Something went wrong": "Si è verificato un problema",
    "Please try again in a moment.": "Riprova tra qualche istante.",
}


def italian(value: str) -> str:
    """Translate presentation values while leaving stored snapshots unchanged."""
    return LABELS.get(value, value)


SAFE_MESSAGES = {
    "Round non trovato.",
    "Utente non trovato.",
    "Scegli una delle quattro categorie disponibili.",
    "Completa il round in corso prima di cambiare categoria.",
    f"Servono almeno {ROUND_LENGTH} domande per iniziare un round.",
    "La risposta è già registrata oppure la domanda non è quella attuale.",
    "Scegli una delle quattro risposte.",
    "Questa risposta è già stata registrata.",
    "Manca il riferimento alla domanda.",
    "Completa il round prima di vedere i risultati.",
}


class QuestionPart(NamedTuple):
    """One paragraph of a stored question, rendered as prose or as code."""

    kind: Literal["text", "code"]
    content: str


class QuestionLayout(NamedTuple):
    """The question heading (when the text has one) and the parts that follow."""

    prompt: str | None
    parts: tuple[QuestionPart, ...]


# A line is code when it is indented, is a REPL prompt, starts with a Python
# keyword or builtin call used by the question bank, or is an assignment.
# Matching is case-sensitive, so Italian or English sentences never match.
_CODE_LINE = re.compile(
    r"^(?:[ \t]+\S|>>>"
    r"|(?:def|class|for|while|if|elif|else|try|except|with|return|import|from"
    r"|print|lambda)\b"
    r"|[A-Za-z_][\w.\[\]]*\s*=[^=])"
)
# Prose ends like a sentence, optionally followed by closing quotes.
# Closing marks: right double quote, right single quote, right guillemet.
_SENTENCE_END = re.compile("[.?!:\u2026][\"'\u201d\u2019\u00bb]*$")


def _is_code(block: str) -> bool:
    if any(_CODE_LINE.match(line) for line in block.splitlines()):
        return True
    return not _SENTENCE_END.search(block.rstrip())


def question_layout(text: str) -> QuestionLayout:
    """Split a stored question into prose and code without changing its content.

    Snapshots have several historical shapes ("title", "title + code",
    "title + hint + code", bare code), so each blank-line-separated paragraph
    is classified on its own. Consecutive code paragraphs stay one block and
    keep their blank line; reading order is always preserved.
    """
    parts: list[QuestionPart] = []
    for block in re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n").strip("\n")):
        if not block.strip():
            continue
        kind: Literal["text", "code"] = "code" if _is_code(block) else "text"
        if kind == "code" and parts and parts[-1].kind == "code":
            parts[-1] = QuestionPart("code", f"{parts[-1].content}\n\n{block}")
        else:
            parts.append(QuestionPart(kind, block if kind == "code" else block.strip()))
    if parts and parts[0].kind == "text":
        return QuestionLayout(parts[0].content, tuple(parts[1:]))
    return QuestionLayout(None, tuple(parts))
