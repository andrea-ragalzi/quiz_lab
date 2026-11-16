"""Italian presentation labels for stable domain values and safe error messages."""

from werkzeug.exceptions import (
    BadRequest,
    MethodNotAllowed,
    NotFound,
    RequestEntityTooLarge,
)

from app.domain import CATEGORY_LABELS, ROUND_LENGTH

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
