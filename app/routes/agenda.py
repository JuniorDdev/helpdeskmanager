from datetime import date, datetime, time, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import AgendamentoLaboratorio, Laboratorio, Recado
from app.utils.authz import SUPPORT_ROLES, has_role, roles_required
from app.utils.validation import (
    ValidationError,
    choice,
    integer,
    optional_id,
    optional_text,
    required_text,
)


agenda_bp = Blueprint("agenda", __name__, url_prefix="/agenda")
PRIORIDADES_RECADOS = {"normal", "importante", "urgente"}
TURNOS = {
    "manha": {"label": "Manhã", "inicio": time(8, 0), "fim": time(12, 0)},
    "tarde": {"label": "Tarde", "inicio": time(13, 0), "fim": time(17, 0)},
    "noite": {"label": "Noite", "inicio": time(18, 0), "fim": time(22, 0)},
}


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
    turno_codigo = choice(request.form, "turno", set(TURNOS), "Turno")
    turno = TURNOS[turno_codigo]
    inicio = datetime.combine(data_reserva, turno["inicio"])
    fim = datetime.combine(data_reserva, turno["fim"])

    conflict = booking_conflict(laboratorio.id, inicio, fim, booking.id)
    if conflict:
        raise ValidationError(
            "Esse laboratório já está reservado no turno selecionado."
        )

    booking.laboratorio_id = laboratorio.id
    booking.titulo = required_text(request.form, "titulo", "Título", 150)
    booking.finalidade = optional_text(request.form, "finalidade")
    booking.inicio = inicio
    booking.fim = fim


@agenda_bp.route("/")
@login_required
def index():
    data_selecionada = selected_date()
    inicio_dia = datetime.combine(data_selecionada, time.min)
    fim_dia = inicio_dia + timedelta(days=1)

    agendamentos = (
        AgendamentoLaboratorio.query.options(
            joinedload(AgendamentoLaboratorio.laboratorio),
            joinedload(AgendamentoLaboratorio.usuario),
        )
        .filter(
            AgendamentoLaboratorio.status == "agendado",
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
        suporte=has_role(*SUPPORT_ROLES),
    )


@agenda_bp.route("/agendamentos/novo", methods=["POST"])
@login_required
def novo_agendamento():
    booking = AgendamentoLaboratorio(usuario_id=current_user.id, status="agendado")
    try:
        apply_booking_fields(booking)
        db.session.add(booking)
        db.session.commit()
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível salvar a reserva.", "danger")
    else:
        flash("Laboratório reservado com sucesso.", "success")
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))


@agenda_bp.route("/agendamentos/<int:id>/editar", methods=["GET", "POST"])
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


@agenda_bp.route("/agendamentos/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_agendamento(id):
    booking = AgendamentoLaboratorio.query.get_or_404(id)
    if not can_manage_booking(booking):
        abort(403)
    if booking.status == "agendado":
        try:
            booking.status = "cancelado"
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível cancelar a reserva.", "danger")
        else:
            flash("Reserva cancelada.", "success")
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
        flash("Recado publicado com sucesso.", "success")
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))


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
    return redirect(url_for("agenda.index", data=request.form.get("data_retorno") or date.today()))
