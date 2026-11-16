"""WSGI entrypoint for PythonAnywhere and other WSGI hosts."""

from app import create_app

application = create_app()
