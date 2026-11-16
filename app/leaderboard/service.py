"""Public ranking queries and pagination policy."""

from flask import abort
from flask_sqlalchemy.pagination import Pagination

from app.extensions import db
from app.repositories.users import UserRepository


def ranking_page(page: int) -> Pagination:
    page = max(1, page)
    if page > 1_000_000:
        abort(400)
    return db.paginate(
        UserRepository(db.session).ranking_query(),
        page=page,
        per_page=50,
        error_out=False,
    )
