from datetime import date, datetime, time, timedelta
from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    AgendamentoLaboratorio,
    HistoricoAgendamentoLaboratorio,
    Laboratorio,
    NotificacaoAgenda,
    Recado,
    Usuario,
)
from app.utils.authz import SUPPORT_ROLES, has_role, roles_required
from app.services.notifications import notify_support as notify_general_support
from app.utils.validation import (
    ValidationError,
    choice,
    integer,
    optional_id,
    optional_text,
    required_text,
)
from app.utils.export import excel_safe


agenda_bp = Blueprint("agenda", __name__, url_prefix="/agendamentos")
PRIORIDADES_RECADOS = {"normal", "importante", "urgente"}
TURNOS = {
    "manha": {"label": "Manhã", "inicio": time(8, 0), "fim": time(12, 0)},
    "tarde": {"label": "Tarde", "inicio": time(13, 0), "fim": time(17, 0)},
    "noite": {"label": "Noite", "inicio": time(18, 0), "fim": time(22, 0)},
}
STATUS_ATIVOS = {"solicitado", "agendado"}
STATUS_LABELS = {
    "solicitado": "Em análise",
    "agendado": "Confirmado",
    "recusado": "Recusado",
    "cancelado": "Cancelado",
    "excluido": "Excluído",
}


def report_period():
    """Retorna o intervalo solicitado para os relatórios de agendamento."""
    periodo = (request.args.get("periodo") or "dia").strip().lower()
    if periodo not in {"dia", "mes", "ano"}:
        raise ValidationError("Período de relatório inválido.")
    referencia = parse_date_value(request.args.get("data") or date.today().isoformat(), "Data")
    if periodo == "dia":
        inicio = referencia
        fim = referencia + timedelta(days=1)
        rotulo = referencia.strftime("%d-%m-%Y")
        titulo = f"Agendamentos de {referencia.strftime('%d/%m/%Y')}"
    elif periodo == "mes":
        inicio = referencia.replace(day=1)
        fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
        rotulo = inicio.strftime("%m-%Y")
        titulo = f"Agendamentos de {inicio.strftime('%m/%Y')}"
    else:
        inicio = referencia.replace(month=1, day=1)
        fim = inicio.replace(year=inicio.year + 1)
        rotulo = str(inicio.year)
        titulo = f"Agendamentos de {inicio.year}"
    return periodo, inicio, fim, rotulo, titulo


def report_bookings(inicio, fim):
    return (
        AgendamentoLaboratorio.query.options(
            joinedload(AgendamentoLaboratorio.laboratorio),
            joinedload(AgendamentoLaboratorio.usuario),
        )
        .filter(
            AgendamentoLaboratorio.status != "excluido",
            AgendamentoLaboratorio.inicio >= datetime.combine(inicio, time.min),
            AgendamentoLaboratorio.inicio < datetime.combine(fim, time.min),
        )
        .order_by(AgendamentoLaboratorio.inicio, AgendamentoLaboratorio.laboratorio_id)
        .all()
    )


def parse_date_value(value, label):
    try:
        return date.fromisoformat((value or "").strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{label} inválida.")


def selected_date():
    value = (request.args.get("data") or "").strip()
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


def can_manage_booking(booking):
    return has_role(*SUPPORT_ROLES) or booking.usuario_id == current_user.id


def register_history(booking, action, description=None, actor=None):
    db.session.add(
        HistoricoAgendamentoLaboratorio(
            agendamento=booking,
            usuario_id=(actor or current_user).id,
            acao=action,
            descricao=description,
        )
    )


def notify_support(booking):
    recipients = Usuario.query.filter(
        Usuario.ativo.is_(True), Usuario.perfil.in_(SUPPORT_ROLES)
    ).all()
    for recipient in recipients:
        db.session.add(
            NotificacaoAgenda(
                usuario_id=recipient.id,
                agendamento=booking,
                mensagem=(
                    f"Nova solicitação {booking.protocolo}: {booking.professor_nome} "
                    f"solicitou {booking.laboratorio.nome}."
                ),
            )
        )
    notify_general_support(
        "agendamento",
        "Nova solicitação de agendamento",
        f"{booking.professor_nome} solicitou {booking.laboratorio.nome} ({booking.protocolo}).",
        url_for("agenda.index", data=booking.inicio.date().isoformat()),
    )


def booking_conflict(laboratorio_id, inicio, fim, ignore_id=None):
    query = AgendamentoLaboratorio.query.filter(
        AgendamentoLaboratorio.laboratorio_id == laboratorio_id,
        AgendamentoLaboratorio.status == "agendado",
        AgendamentoLaboratorio.inicio < fim,
        AgendamentoLaboratorio.fim > inicio,
    )
    if ignore_id is not None:
        query = query.filter(AgendamentoLaboratorio.id != ignore_id)
    return query.with_for_update().first()


def apply_booking_fields(booking):
    laboratorio_id = optional_id(request.form, "laboratorio_id")
    laboratorio = Laboratorio.query.filter_by(id=laboratorio_id, ativo=True).first()
    if not laboratorio:
        raise ValidationError("Laboratório inválido ou indisponível.")

    data_reserva = parse_date_value(request.form.get("data_reserva"), "Data da reserva")
    if data_reserva.weekday() == 6:
        raise ValidationError("Não é possível agendar laboratórios aos domingos.")
    turno_codigo = choice(request.form, "turno", set(TURNOS), "Turno")
    turno = TURNOS[turno_codigo]
    inicio = datetime.combine(data_reserva, turno["inicio"])
    fim = datetime.combine(data_reserva, turno["fim"])

    quantidade_alunos = integer(request.form, "quantidade_alunos", "Quantidade de alunos", 1)
    if laboratorio.capacidade and quantidade_alunos > laboratorio.capacidade:
        raise ValidationError(
            f"A quantidade de alunos excede a capacidade de {laboratorio.capacidade} computadores do laboratório."
        )

    if booking.status == "agendado":
        conflict = booking_conflict(laboratorio.id, inicio, fim, booking.id)
        if conflict:
            raise ValidationError("Esse laboratório já está reservado no turno selecionado.")

    booking.laboratorio_id = laboratorio.id
    booking.professor_nome = required_text(request.form, "professor_nome", "Nome do professor", 120)
    booking.professor_matricula = required_text(request.form, "professor_matricula", "Matrícula", 60)
    booking.quantidade_alunos = quantidade_alunos
    booking.titulo = required_text(request.form, "titulo", "Título", 150)
    booking.finalidade = optional_text(request.form, "finalidade")
    booking.inicio = inicio
    booking.fim = fim


@agenda_bp.route("/")
@login_required
def index():
    if current_user.perfil == "professor":
        return redirect(url_for("agendamento_laboratorios"))
    data_selecionada = selected_date()
    inicio_dia = datetime.combine(data_selecionada, time.min)
    fim_dia = inicio_dia + timedelta(days=1)

    agendamentos = (
        AgendamentoLaboratorio.query.options(
            joinedload(AgendamentoLaboratorio.laboratorio),
            joinedload(AgendamentoLaboratorio.usuario),
        )
        .filter(
            AgendamentoLaboratorio.status.in_(STATUS_ATIVOS),
            AgendamentoLaboratorio.inicio < fim_dia,
            AgendamentoLaboratorio.fim > inicio_dia,
        )
        .order_by(AgendamentoLaboratorio.inicio, AgendamentoLaboratorio.laboratorio_id)
        .all()
    )
    recados = (
        Recado.query.options(joinedload(Recado.autor))
        .filter(Recado.data_inicio <= data_selecionada, Recado.data_fim >= data_selecionada)
        .order_by(
            case(
                (Recado.prioridade == "urgente", 0),
                (Recado.prioridade == "importante", 1),
                else_=2,
            ),
            Recado.criado_em.desc(),
        )
        .all()
    )
    laboratorios = Laboratorio.query.filter_by(ativo=True).order_by(Laboratorio.nome).all()
    mapa_turnos = []
    for codigo, turno in TURNOS.items():
        inicio_turno = datetime.combine(data_selecionada, turno["inicio"])
        fim_turno = datetime.combine(data_selecionada, turno["fim"])
        slots = []
        for laboratorio in laboratorios:
            reservas_slot = [
                item
                for item in agendamentos
                if item.laboratorio_id == laboratorio.id
                and item.inicio < fim_turno
                and item.fim > inicio_turno
            ]
            slots.append({"laboratorio": laboratorio, "reservas": reservas_slot})
        mapa_turnos.append(
            {
                "codigo": codigo,
                "label": turno["label"],
                "periodo": f"{turno['inicio'].strftime('%H:%M')}–{turno['fim'].strftime('%H:%M')}",
                "slots": slots,
            }
        )

    preselected_lab_id = request.args.get("lab", type=int)
    if not any(item.id == preselected_lab_id for item in laboratorios):
        preselected_lab_id = laboratorios[0].id if laboratorios else None
    preselected_turno = request.args.get("turno")
    if preselected_turno not in TURNOS:
        preselected_turno = "manha"
    todos_laboratorios = []
    if has_role(*SUPPORT_ROLES):
        todos_laboratorios = Laboratorio.query.order_by(Laboratorio.nome).all()
    notificacoes = []
    solicitacoes_pendentes = []
    if has_role(*SUPPORT_ROLES):
        notificacoes = (
            NotificacaoAgenda.query.options(joinedload(NotificacaoAgenda.agendamento))
            .filter_by(usuario_id=current_user.id, lida_em=None)
            .order_by(NotificacaoAgenda.criado_em.desc())
            .limit(10)
            .all()
        )
        solicitacoes_pendentes = (
            AgendamentoLaboratorio.query.options(
                joinedload(AgendamentoLaboratorio.laboratorio),
                joinedload(AgendamentoLaboratorio.usuario),
            )
            .filter_by(status="solicitado")
            .order_by(AgendamentoLaboratorio.criado_em, AgendamentoLaboratorio.id)
            .all()
        )

    return render_template(
        "agenda/index.html",
        agendamentos=agendamentos,
        recados=recados,
        laboratorios=laboratorios,
        mapa_turnos=mapa_turnos,
        turnos=TURNOS,
        preselected_lab_id=preselected_lab_id,
        preselected_turno=preselected_turno,
        todos_laboratorios=todos_laboratorios,
        data_selecionada=data_selecionada,
        data_anterior=data_selecionada - timedelta(days=1),
        proxima_data=data_selecionada + timedelta(days=1),
        hoje=date.today(),
        domingo=data_selecionada.weekday() == 6,
        suporte=has_role(*SUPPORT_ROLES),
        status_labels=STATUS_LABELS,
        notificacoes=notificacoes,
        solicitacoes_pendentes=solicitacoes_pendentes,
    )


@agenda_bp.route("/relatorios")
@roles_required("admin", "tecnico")
def relatorios():
    periodo = (request.args.get("periodo") or "dia").strip().lower()
    if periodo not in {"dia", "mes", "ano"}:
        periodo = "dia"
    try:
        referencia = parse_date_value(request.args.get("data") or date.today().isoformat(), "Data")
    except ValidationError:
        referencia = date.today()
    return render_template("agenda/relatorios.html", periodo=periodo, referencia=referencia)


@agenda_bp.route("/relatorios/excel")
@roles_required("admin", "tecnico")
def relatorio_excel():
    try:
        _periodo, inicio, fim, rotulo, titulo = report_period()
    except ValidationError as error:
        flash(str(error), "danger")
        return redirect(url_for("agenda.relatorios"))

    agendamentos = report_bookings(inicio, fim)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Agendamentos"
    worksheet.append([titulo])
    worksheet.append([f"Período: {inicio.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}"])
    worksheet.append([])
    headers = [
        "Protocolo", "Data", "Turno", "Laboratório", "Professor", "Matrícula",
        "Alunos", "Atividade", "Status", "Solicitado em", "Confirmado em",
    ]
    worksheet.append(headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True, size=14, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3B70")
    for cell in worksheet[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4169E1")
    for booking in agendamentos:
        worksheet.append(
            [
                booking.protocolo,
                booking.inicio.date(),
                booking.turno_label,
                excel_safe(booking.laboratorio.nome),
                excel_safe(booking.professor_nome or booking.usuario.nome),
                excel_safe(booking.professor_matricula),
                booking.quantidade_alunos,
                excel_safe(booking.titulo),
                STATUS_LABELS.get(booking.status, booking.status),
                booking.criado_em.strftime("%d/%m/%Y %H:%M") if booking.criado_em else "",
                booking.confirmado_em.strftime("%d/%m/%Y %H:%M") if booking.confirmado_em else "",
            ]
        )
    worksheet.freeze_panes = "A5"
    worksheet.auto_filter.ref = f"A4:K{max(4, worksheet.max_row)}"
    for cell in worksheet["B"][4:]:
        cell.number_format = "dd/mm/yyyy"
    widths = [16, 13, 12, 16, 28, 16, 10, 40, 16, 20, 20]
    for column, width in enumerate(widths, start=1):
        worksheet.column_dimensions[chr(64 + column)].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"agendamentos_{rotulo}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@agenda_bp.route("/relatorios/pdf")
@roles_required("admin", "tecnico")
def relatorio_pdf():
    try:
        _periodo, inicio, fim, rotulo, titulo = report_period()
    except ValidationError as error:
        flash(str(error), "danger")
        return redirect(url_for("agenda.relatorios"))

    agendamentos = report_bookings(inicio, fim)
    output = BytesIO()
    largura, altura = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=landscape(A4))

    def cabecalho():
        y_pos = altura - 34
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(28, y_pos, titulo)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(28, y_pos - 15, f"Período: {inicio.strftime('%d/%m/%Y')} a {(fim - timedelta(days=1)).strftime('%d/%m/%Y')}")
        y_pos -= 34
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(28, y_pos, "Data / turno")
        pdf.drawString(105, y_pos, "Laboratório")
        pdf.drawString(180, y_pos, "Professor")
        pdf.drawString(350, y_pos, "Atividade")
        pdf.drawString(600, y_pos, "Alunos")
        pdf.drawString(652, y_pos, "Status")
        return y_pos - 13

    y = cabecalho()
    pdf.setFont("Helvetica", 8)
    for booking in agendamentos:
        if y < 34:
            pdf.showPage()
            y = cabecalho()
            pdf.setFont("Helvetica", 8)
        data_turno = f"{booking.inicio.strftime('%d/%m/%Y')}\n{booking.turno_label}"
        pdf.drawString(28, y, data_turno.replace("\n", " "))
        pdf.drawString(105, y, booking.laboratorio.nome[:13])
        pdf.drawString(180, y, (booking.professor_nome or booking.usuario.nome)[:29])
        pdf.drawString(350, y, booking.titulo[:42])
        pdf.drawRightString(630, y, str(booking.quantidade_alunos))
        pdf.drawString(652, y, STATUS_LABELS.get(booking.status, booking.status)[:15])
        y -= 14
    if not agendamentos:
        pdf.drawString(28, y, "Nenhum agendamento encontrado para o período.")
    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"agendamentos_{rotulo}.pdf", mimetype="application/pdf")


@agenda_bp.route("/solicitar")
@login_required
def solicitar_professor():
    data_selecionada = selected_date()
    inicio_dia = datetime.combine(data_selecionada, time.min)
    fim_dia = inicio_dia + timedelta(days=1)
    laboratorios = Laboratorio.query.filter_by(ativo=True).order_by(Laboratorio.nome).all()
    confirmados = (
        AgendamentoLaboratorio.query.filter(
            AgendamentoLaboratorio.status == "agendado",
            AgendamentoLaboratorio.inicio < fim_dia,
            AgendamentoLaboratorio.fim > inicio_dia,
        )
        .all()
    )
    mapa_turnos = []
    for codigo, turno in TURNOS.items():
        inicio_turno = datetime.combine(data_selecionada, turno["inicio"])
        fim_turno = datetime.combine(data_selecionada, turno["fim"])
        slots = []
        for laboratorio in laboratorios:
            ocupado = any(
                item.laboratorio_id == laboratorio.id
                and item.inicio < fim_turno
                and item.fim > inicio_turno
                for item in confirmados
            )
            slots.append({"laboratorio": laboratorio, "ocupado": ocupado})
        mapa_turnos.append({"codigo": codigo, "label": turno["label"], "periodo": f"{turno['inicio'].strftime('%H:%M')}–{turno['fim'].strftime('%H:%M')}", "slots": slots})

    preselected_lab_id = request.args.get("lab", type=int)
    if not any(laboratorio.id == preselected_lab_id for laboratorio in laboratorios):
        preselected_lab_id = laboratorios[0].id if laboratorios else None
    preselected_turno = request.args.get("turno")
    if preselected_turno not in TURNOS:
        preselected_turno = "manha"
    agendamentos = (
        AgendamentoLaboratorio.query.options(joinedload(AgendamentoLaboratorio.laboratorio))
        .filter_by(usuario_id=current_user.id)
        .order_by(AgendamentoLaboratorio.inicio.desc())
        .all()
    )
    return render_template(
        "agenda/solicitar.html",
        laboratorios=laboratorios,
        turnos=TURNOS,
        hoje=date.today(),
        professor=current_user,
        agendamentos=agendamentos,
        data_selecionada=data_selecionada,
        data_anterior=data_selecionada - timedelta(days=1),
        proxima_data=data_selecionada + timedelta(days=1),
        mapa_turnos=mapa_turnos,
        preselected_lab_id=preselected_lab_id,
        preselected_turno=preselected_turno,
        domingo=data_selecionada.weekday() == 6,
    )


@agenda_bp.route("/novo", methods=["POST"])
@login_required
def novo_agendamento():
    booking = AgendamentoLaboratorio(usuario_id=current_user.id, status="solicitado")
    try:
        apply_booking_fields(booking)
        db.session.add(booking)
        db.session.flush()
        register_history(booking, "solicitacao_criada", "Solicitação aguardando análise da equipe.")
        notify_support(booking)
        db.session.commit()
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível salvar a reserva.", "danger")
    else:
        flash(
            f"Solicitação {booking.protocolo} enviada. A equipe confirmará o agendamento após análise.",
            "success",
        )
    destino = "agendamento_laboratorios" if current_user.perfil == "professor" else "agenda.index"
    return redirect(url_for(destino, data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_agendamento(id):
    booking = AgendamentoLaboratorio.query.get_or_404(id)
    if not can_manage_booking(booking) or booking.status != "agendado":
        abort(403)

    laboratorios = Laboratorio.query.filter(
        (Laboratorio.ativo.is_(True)) | (Laboratorio.id == booking.laboratorio_id)
    ).order_by(Laboratorio.nome).all()
    if request.method == "POST":
        try:
            apply_booking_fields(booking)
            register_history(booking, "solicitacao_atualizada", "Dados da solicitação foram atualizados.")
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível atualizar a reserva.", "danger")
        else:
            flash("Reserva atualizada com sucesso.", "success")
            return redirect(url_for("agenda.index", data=booking.inicio.date()))

    return render_template(
        "agenda/agendamento_form.html", booking=booking, laboratorios=laboratorios, turnos=TURNOS
    )


@agenda_bp.route("/<int:id>/historico")
@login_required
def historico_agendamento(id):
    booking = AgendamentoLaboratorio.query.get_or_404(id)
    if not can_manage_booking(booking):
        abort(403)
    historicos = (
        HistoricoAgendamentoLaboratorio.query.options(joinedload(HistoricoAgendamentoLaboratorio.usuario))
        .filter_by(agendamento_id=booking.id)
        .order_by(HistoricoAgendamentoLaboratorio.criado_em.desc())
        .all()
    )
    return render_template("agenda/historico.html", booking=booking, historicos=historicos)


@agenda_bp.route("/<int:id>/confirmar", methods=["POST"])
@roles_required("admin", "tecnico")
def confirmar_agendamento(id):
    booking = AgendamentoLaboratorio.query.with_for_update().get_or_404(id)
    try:
        if booking.status != "solicitado":
            raise ValidationError("Somente solicitações pendentes podem ser confirmadas.")
        if booking.laboratorio.capacidade and booking.quantidade_alunos > booking.laboratorio.capacidade:
            raise ValidationError("A quantidade de alunos excede a capacidade do laboratório.")
        anterior = (
            AgendamentoLaboratorio.query.filter(
                AgendamentoLaboratorio.laboratorio_id == booking.laboratorio_id,
                AgendamentoLaboratorio.status == "solicitado",
                AgendamentoLaboratorio.inicio == booking.inicio,
                AgendamentoLaboratorio.fim == booking.fim,
                AgendamentoLaboratorio.id < booking.id,
            )
            .order_by(AgendamentoLaboratorio.criado_em, AgendamentoLaboratorio.id)
            .first()
        )
        if anterior:
            raise ValidationError(
                f"A solicitação {anterior.protocolo} chegou antes e deve ser analisada primeiro."
            )
        if booking_conflict(booking.laboratorio_id, booking.inicio, booking.fim, booking.id):
            raise ValidationError("Este horário já foi confirmado para outra solicitação.")
        booking.status = "agendado"
        booking.confirmado_por_id = current_user.id
        booking.confirmado_em = datetime.utcnow()
        booking.motivo_decisao = optional_text(request.form, "motivo_decisao")
        register_history(booking, "agendamento_confirmado", booking.motivo_decisao or "Agendamento confirmado.")
        db.session.commit()
    except (ValidationError, SQLAlchemyError) as error:
        db.session.rollback()
        flash(str(error) if isinstance(error, ValidationError) else "Não foi possível confirmar a solicitação.", "danger")
    else:
        flash(
            f"{booking.protocolo} confirmado: {booking.laboratorio.nome}, {booking.inicio.strftime('%d/%m/%Y')} "
            f"no turno da {booking.turno_label.lower()}, para {booking.quantidade_alunos} alunos. "
            "Oriente o professor a chegar com antecedência e comunicar qualquer cancelamento.",
            "success",
        )
    return redirect(url_for("agenda.index", data=booking.inicio.date()))


@agenda_bp.route("/<int:id>/recusar", methods=["POST"])
@roles_required("admin", "tecnico")
def recusar_agendamento(id):
    booking = AgendamentoLaboratorio.query.get_or_404(id)
    try:
        if booking.status != "solicitado":
            raise ValidationError("Somente solicitações pendentes podem ser recusadas.")
        booking.status = "recusado"
        booking.motivo_decisao = required_text(request.form, "motivo_decisao", "Motivo da recusa")
        register_history(booking, "solicitacao_recusada", booking.motivo_decisao)
        db.session.commit()
    except (ValidationError, SQLAlchemyError) as error:
        db.session.rollback()
        flash(str(error) if isinstance(error, ValidationError) else "Não foi possível recusar a solicitação.", "danger")
    else:
        flash(f"{booking.protocolo} foi recusada e ficou registrada no histórico.", "success")
    return redirect(url_for("agenda.index", data=booking.inicio.date()))


@agenda_bp.route("/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_agendamento(id):
    booking = AgendamentoLaboratorio.query.get_or_404(id)
    if not can_manage_booking(booking):
        abort(403)
    if booking.status in STATUS_ATIVOS:
        try:
            booking.status = "cancelado"
            booking.motivo_decisao = optional_text(request.form, "motivo_decisao") or "Cancelado pelo solicitante ou pela equipe."
            register_history(booking, "agendamento_cancelado", booking.motivo_decisao)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível cancelar a reserva.", "danger")
        else:
            flash("Agendamento cancelado e preservado no histórico.", "success")
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/<int:id>/excluir", methods=["POST"])
@roles_required("admin", "tecnico")
def excluir_agendamento(id):
    booking = AgendamentoLaboratorio.query.get_or_404(id)
    try:
        if booking.status == "excluido":
            raise ValidationError("Este agendamento já foi excluído.")
        booking.status = "excluido"
        booking.motivo_decisao = optional_text(request.form, "motivo_decisao") or "Excluído pela equipe responsável."
        register_history(booking, "agendamento_excluido", booking.motivo_decisao)
        db.session.commit()
    except (ValidationError, SQLAlchemyError) as error:
        db.session.rollback()
        flash(str(error) if isinstance(error, ValidationError) else "Não foi possível excluir o agendamento.", "danger")
    else:
        flash("Agendamento excluído do painel ativo e preservado no histórico.", "success")
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/laboratorios/novo", methods=["POST"])
@roles_required("admin", "tecnico")
def novo_laboratorio():
    try:
        capacidade_raw = (request.form.get("capacidade") or "").strip()
        laboratorio = Laboratorio(
            nome=required_text(request.form, "nome", "Nome", 120),
            localizacao=optional_text(request.form, "localizacao", 150),
            capacidade=integer(request.form, "capacidade", "Capacidade", 1)
            if capacidade_raw
            else None,
            descricao=optional_text(request.form, "descricao"),
            ativo=True,
        )
        db.session.add(laboratorio)
        db.session.commit()
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "danger")
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um laboratório com esse nome.", "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível cadastrar o laboratório.", "danger")
    else:
        flash("Laboratório cadastrado com sucesso.", "success")
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/laboratorios/<int:id>/alternar", methods=["POST"])
@roles_required("admin", "tecnico")
def alternar_laboratorio(id):
    laboratorio = Laboratorio.query.get_or_404(id)
    try:
        laboratorio.ativo = not laboratorio.ativo
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível alterar o laboratório.", "danger")
    else:
        estado = "ativado" if laboratorio.ativo else "desativado"
        flash(f"Laboratório {estado}.", "success")
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/recados/novo", methods=["POST"])
@roles_required("admin", "tecnico")
def novo_recado():
    try:
        data_inicio = parse_date_value(request.form.get("data_inicio"), "Data inicial")
        data_fim = parse_date_value(request.form.get("data_fim"), "Data final")
        if data_fim < data_inicio:
            raise ValidationError("A data final deve ser igual ou posterior à data inicial.")
        recado = Recado(
            titulo=required_text(request.form, "titulo", "Título", 150),
            mensagem=required_text(request.form, "mensagem", "Mensagem"),
            prioridade=choice(
                request.form, "prioridade", PRIORIDADES_RECADOS, "Prioridade"
            ),
            data_inicio=data_inicio,
            data_fim=data_fim,
            autor_id=current_user.id,
        )
        db.session.add(recado)
        db.session.commit()
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível publicar o recado.", "danger")
    else:
        notify_general_support(
            "recado",
            "Novo recado publicado",
            f"{recado.titulo} ficará visível até {recado.data_fim.strftime('%d/%m/%Y')}.",
            url_for("agenda.recados"),
        )
        db.session.commit()
        flash("Recado publicado com sucesso.", "success")
    return redirect(url_for("agenda.recados", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/recados/<int:id>/excluir", methods=["POST"])
@roles_required("admin", "tecnico")
def excluir_recado(id):
    recado = Recado.query.get_or_404(id)
    try:
        db.session.delete(recado)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível excluir o recado.", "danger")
    else:
        flash("Recado excluído.", "success")
    return redirect(url_for("agenda.recados", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/recados")
@roles_required("admin", "tecnico")
def recados():
    hoje = date.today()
    recados_publicados = (
        Recado.query.options(joinedload(Recado.autor))
        .order_by(Recado.data_inicio.desc(), Recado.criado_em.desc())
        .all()
    )
    return render_template("agenda/recados.html", recados=recados_publicados, hoje=hoje)
