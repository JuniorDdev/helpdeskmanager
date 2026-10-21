"""Atualizações compatíveis do esquema de usuários para instalações existentes."""

from sqlalchemy import inspect, text

from app.extensions import db


def ensure_user_schema():
    """Inclui os campos e perfis necessários sem apagar usuários existentes."""
    engine = db.engine
    if "usuarios" not in inspect(engine).get_table_names():
        return

    columns = {column["name"] for column in inspect(engine).get_columns("usuarios")}
    with engine.begin() as connection:
        if "matricula" not in columns:
            connection.execute(text("ALTER TABLE usuarios ADD COLUMN matricula VARCHAR(60)"))
        if engine.dialect.name == "mysql":
            connection.execute(
                text(
                    "ALTER TABLE usuarios MODIFY COLUMN perfil "
                    "ENUM('admin','tecnico','usuario','almoxarife','professor') "
                    "NOT NULL DEFAULT 'usuario'"
                )
            )
