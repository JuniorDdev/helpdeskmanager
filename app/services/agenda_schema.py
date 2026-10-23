"""Atualizações compatíveis do esquema da agenda para instalações existentes."""

from sqlalchemy import inspect, text

from app.extensions import db


def ensure_agenda_schema():
    """Adiciona os campos da fila de solicitações sem remover dados existentes."""
    engine = db.engine
    if "agendamentos_laboratorio" not in inspect(engine).get_table_names():
        return

    columns = {column["name"] for column in inspect(engine).get_columns("agendamentos_laboratorio")}
    additions = {
        "professor_nome": "VARCHAR(120) NOT NULL DEFAULT ''",
        "professor_matricula": "VARCHAR(60) NOT NULL DEFAULT ''",
        "quantidade_alunos": "INTEGER NOT NULL DEFAULT 0",
        "softwares_necessarios": "TEXT",
        "motivo_decisao": "TEXT",
        "atendido_por_id": "INTEGER",
        "atendido_em": "DATETIME",
        "confirmado_por_id": "INTEGER",
        "confirmado_em": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE agendamentos_laboratorio ADD COLUMN {name} {definition}"))

        if engine.dialect.name == "mysql":
            connection.execute(
                text(
                    "ALTER TABLE agendamentos_laboratorio MODIFY COLUMN status "
                    "ENUM('solicitado','agendado','recusado','cancelado','excluido') "
                    "NOT NULL DEFAULT 'agendado'"
                )
            )
