from pathlib import Path

import click
from flask.cli import with_appcontext

from app.services.agenda_excel import AgendaExcelError, import_agenda_workbook


@click.command("importar-agenda-excel")
@click.argument(
    "arquivo",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--usuario",
    help="E-mail do usuário responsável. Sem a opção, usa o primeiro admin/técnico ativo.",
)
@click.option(
    "--confirmar",
    is_flag=True,
    help="Grava no banco. Sem esta opção, executa apenas uma simulação.",
)
@with_appcontext
def importar_agenda_excel_command(arquivo, usuario, confirmar):
    """Importa o mapa mensal de laboratórios de um ARQUIVO .xlsx."""
    try:
        result = import_agenda_workbook(
            arquivo,
            user_email=usuario,
            commit=confirmar,
        )
    except AgendaExcelError as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"Registros encontrados: {result.encontrados}")
    click.echo(f"Prontos para importar: {result.prontos}")
    click.echo(f"Conflitos já existentes: {result.conflitos}")
    click.echo(f"Duplicados na planilha: {result.duplicados_na_planilha}")
    click.echo(f"Marcadores vazios ignorados: {result.placeholders_ignorados}")
    for warning in result.avisos:
        click.echo(f"Aviso: {warning}", err=True)

    if confirmar:
        click.secho(f"Importados com sucesso: {result.importados}", fg="green")
    else:
        click.secho(
            "Simulação concluída; nada foi gravado. Use --confirmar para importar.",
            fg="yellow",
        )
