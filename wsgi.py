"""Entrada WSGI para servidores de produção (Railway, PythonAnywhere, etc.)."""

from app import create_app


application = create_app()

# Alias útil para plataformas que procuram o nome "app".
app = application
