"""Server-side identity and password validation."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

IDENTITY = r"^[A-Za-z0-9_]{3,32}$"


def validated_text(field: StringField) -> str:
    """Return the text of a field after ``DataRequired`` has accepted it.

    WTForms types ``data`` as optional; once validation succeeds the value is a
    nonempty string, and this accessor enforces that invariant at runtime.
    """
    if not isinstance(field.data, str):
        raise TypeError(f"Field {field.name!r} has not been validated.")
    return field.data


class LoginForm(FlaskForm):
    username = StringField(
        "Nome utente",
        validators=[
            DataRequired(message="Questo campo è obbligatorio."),
            Length(max=32, message="Usa al massimo 32 caratteri."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Questo campo è obbligatorio."),
            Length(max=128, message="Usa al massimo 128 caratteri."),
        ],
    )


class RegistrationForm(LoginForm):
    username = StringField(
        "Nome utente",
        validators=[
            DataRequired(message="Questo campo è obbligatorio."),
            Regexp(IDENTITY, message="Usa da 3 a 32 lettere, numeri o trattini bassi."),
        ],
    )
    nickname = StringField(
        "Nickname",
        validators=[
            DataRequired(message="Questo campo è obbligatorio."),
            Regexp(IDENTITY, message="Usa da 3 a 32 lettere, numeri o trattini bassi."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Questo campo è obbligatorio."),
            Length(min=8, max=128, message="Usa da 8 a 128 caratteri."),
        ],
    )
    confirm = PasswordField(
        "Conferma password",
        validators=[
            DataRequired(message="Questo campo è obbligatorio."),
            EqualTo("password", message="Le password devono coincidere."),
        ],
    )
