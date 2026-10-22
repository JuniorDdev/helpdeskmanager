from datetime import date
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
    "--laboratorios",
    help="Laboratórios a importar, separados por vírgula. Ex.: 5,6,7,8.",
)
@click.option(
    "--a-partir-de",
    "starts_on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Importa somente reservas desta data em diante (AAAA-MM-DD).",
)
@click.option(
    "--confirmar",
    is_flag=True,
    help="Grava no banco. Sem esta opção, executa apenas uma simulação.",
)
@with_appcontext
def importar_agenda_excel_command(arquivo, usuario, laboratorios, starts_on, confirmar):
    """Importa o mapa mensal de laboratórios de um ARQUIVO .xlsx."""
    lab_names = None
    if laboratorios:
        numbers = {part.strip() for part in laboratorios.split(",") if part.strip()}
        if not numbers or any(not number.isdigit() or not 1 <= int(number) <= 8 for number in numbers):
            raise click.ClickException("Use números de laboratórios entre 1 e 8, separados por vírgula.")
        lab_names = {f"Lab {int(number):02d}" for number in numbers}
    try:
        result = import_agenda_workbook(
            arquivo,
            user_email=usuario,
            lab_names=lab_names,
            starts_on=starts_on.date() if starts_on else None,
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
