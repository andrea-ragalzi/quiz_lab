"""Italian presentation labels for stable domain values and safe error messages."""

from werkzeug.exceptions import (
    BadRequest,
    MethodNotAllowed,
    NotFound,
    RequestEntityTooLarge,
)

from app.questions import CATEGORY_LABELS

LABELS = {
    **CATEGORY_LABELS,
    NotFound.description: "La pagina richiesta non esiste. Controlla l'indirizzo.",
    BadRequest.description: "La richiesta non è valida. Ricarica la pagina e riprova.",
    MethodNotAllowed.description: "Questa operazione non è consentita.",
    RequestEntityTooLarge.description: "La richiesta supera la dimensione consentita.",
    "easy": "Facile",
    "medium": "Medio",
    "hard": "Difficile",
    "Monday": "Lunedì",
    "Tuesday": "Martedì",
    "Wednesday": "Mercoledì",
    "Thursday": "Giovedì",
    "Friday": "Venerdì",
    "Saturday": "Sabato",
    "Sunday": "Domenica",
    "Clear sky": "Sereno",
    "Mainly clear": "Prevalentemente sereno",
    "Partly cloudy": "Parzialmente nuvoloso",
    "Overcast": "Coperto",
    "Fog": "Nebbia",
    "Rime fog": "Nebbia con brina",
    "Light drizzle": "Pioviggine debole",
    "Moderate drizzle": "Pioviggine moderata",
    "Dense drizzle": "Pioviggine intensa",
    "Freezing drizzle": "Pioviggine gelata",
    "Dense freezing drizzle": "Pioviggine gelata intensa",
    "Light rain": "Pioggia debole",
    "Moderate rain": "Pioggia moderata",
    "Heavy rain": "Pioggia intensa",
    "Freezing rain": "Pioggia gelata",
    "Heavy freezing rain": "Pioggia gelata intensa",
    "Light snow": "Neve debole",
    "Moderate snow": "Neve moderata",
    "Heavy snow": "Neve intensa",
    "Snow grains": "Nevischio",
    "Light rain showers": "Rovesci deboli",
    "Moderate rain showers": "Rovesci moderati",
    "Violent rain showers": "Rovesci intensi",
    "Light snow showers": "Rovesci di neve deboli",
    "Heavy snow showers": "Rovesci di neve intensi",
    "Thunderstorm": "Temporale",
    "Thunderstorm with hail": "Temporale con grandine",
    "Severe thunderstorm with hail": "Forte temporale con grandine",
    "Unknown conditions": "Condizioni non disponibili",
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
    "Servono almeno 10 domande per iniziare un round.",
    "La risposta è già registrata oppure la domanda non è quella attuale.",
    "Scegli una delle quattro risposte.",
    "Questa risposta è già stata registrata.",
    "Manca il riferimento alla domanda.",
    "Completa il round prima di vedere i risultati.",
}
