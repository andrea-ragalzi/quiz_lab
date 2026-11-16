"""Extension instances shared by the application factory."""

from typing import TYPE_CHECKING

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import MetaData

db = SQLAlchemy(
    metadata=MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
)
login_manager = LoginManager()
csrf = CSRFProtect()

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase

    class Model(DeclarativeBase):
        """Static description of ``db.Model`` for type checkers only.

        Flask-SQLAlchemy 3.1 annotates ``db.Model`` as ``type[_FSAModel]``, which
        declares no constructor, although the runtime declarative base accepts
        mapped attributes as keyword arguments. ``DeclarativeBase`` describes that
        runtime API. The schema is unaffected because the runtime base below is
        unchanged.
        """

else:
    Model = db.Model
