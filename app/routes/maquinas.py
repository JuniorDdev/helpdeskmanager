import ipaddress
import re
from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import (
    Chamado,
    ConferenciaMaquina,
    Manutencao,
    Maquina,
    MovimentacaoMaquina,
    QRCodeMaquina,
    Setor,
    Usuario,
)
from app.utils.authz import roles_required
from app.utils.export import excel_safe
from app.utils.validation import ValidationError, choice, optional_id, optional_text, required_text


maquinas_bp = Blueprint("maquinas", __name__, url_prefix="/maquinas")
MACHINE_STATUS = {"ativa", "manutencao", "reserva", "baixada"}
MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def validate_related(model, value, label):
    if value is not None and not model.query.filter_by(id=value).first():
        raise ValidationError(f"{label} inválido.")
    return value


def validate_active_user(value):
    if value is not None and not Usuario.query.filter_by(id=value, ativo=True).first():
        raise ValidationError("Usuário responsável inválido ou inativo.")
    return value


def apply_machine_fields(maquina):
    maquina.patrimonio = required_text(request.form, "patrimonio", "Patrimônio", 50)
    maquina.nome_maquina = required_text(request.form, "nome_maquina", "Nome da máquina", 100)
    maquina.status = choice(request.form, "status", MACHINE_STATUS, "Status")
    maquina.usuario_responsavel_id = validate_active_user(
        optional_id(request.form, "usuario_responsavel_id")
    )
    maquina.setor_id = validate_related(Setor, optional_id(request.form, "setor_id"), "Setor")
    maquina.localizacao = optional_text(request.form, "localizacao", 150)
    maquina.processador = optional_text(request.form, "processador", 120)
    maquina.memoria_ram = optional_text(request.form, "memoria_ram", 50)
    maquina.armazenamento = optional_text(request.form, "armazenamento", 80)
    maquina.sistema_operacional = optional_text(request.form, "sistema_operacional", 100)

    ip = optional_text(request.form, "ip", 45)
    if ip:
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError:
            raise ValidationError("Endereço IP inválido.")
    maquina.ip = ip

    mac = optional_text(request.form, "mac_address", 50)
    if mac and not MAC_PATTERN.fullmatch(mac):
        raise ValidationError("Endereço MAC inválido. Use o formato AA:BB:CC:DD:EE:FF.")
    maquina.mac_address = mac.upper().replace("-", ":") if mac else None
    maquina.observacao = optional_text(request.form, "observacao")


def machine_query():
    return Maquina.query.options(joinedload(Maquina.usuario_responsavel), joinedload(Maquina.setor))


@maquinas_bp.route("/")
@roles_required("admin", "tecnico")
def listar():
    page = request.args.get("page", 1, type=int)
    pagination = machine_query().order_by(Maquina.id.desc()).paginate(
        page=max(page, 1), per_page=25, error_out=False
    )
    return render_template("maquinas/listar.html", maquinas=pagination.items, pagination=pagination)


@maquinas_bp.route("/nova", methods=["GET", "POST"])
@roles_required("admin", "tecnico")
def nova():
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    setores = Setor.query.order_by(Setor.nome).all()
    if request.method == "POST":
        try:
            maquina = Maquina()
            apply_machine_fields(maquina)
            db.session.add(maquina)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma máquina com esse patrimônio.", "danger")
        else:
            flash("Máquina cadastrada com sucesso.", "success")
            return redirect(url_for("maquinas.listar"))
    return render_template("maquinas/form.html", maquina=None, usuarios=usuarios, setores=setores)


@maquinas_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@roles_required("admin", "tecnico")
def editar(id):
    maquina = Maquina.query.get_or_404(id)
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    setores = Setor.query.order_by(Setor.nome).all()
    if request.method == "POST":
        try:
            apply_machine_fields(maquina)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma máquina com esse patrimônio.", "danger")
        else:
            flash("Máquina atualizada com sucesso.", "success")
            return redirect(url_for("maquinas.listar"))
    return render_template("maquinas/form.html", maquina=maquina, usuarios=usuarios, setores=setores)


@maquinas_bp.route("/<int:id>/excluir", methods=["POST"])
@roles_required("admin")
def excluir(id):
    if not current_user.check_senha(request.form.get("senha_admin") or ""):
        flash("Senha de administrador inválida.", "danger")
        return redirect(url_for("maquinas.listar"))

    maquina = Maquina.query.get_or_404(id)
    total_manutencoes = Manutencao.query.filter_by(maquina_id=maquina.id).count()
    total_chamados = Chamado.query.filter_by(maquina_id=maquina.id).count()
    if total_manutencoes or total_chamados:
        flash(
            f"Não foi possível excluir. Existem {total_manutencoes} manutenções e {total_chamados} chamados vinculados.",
            "danger",
        )
        return redirect(url_for("maquinas.listar"))

    try:
        MovimentacaoMaquina.query.filter_by(maquina_id=maquina.id).delete()
        ConferenciaMaquina.query.filter_by(maquina_id=maquina.id).delete()
        QRCodeMaquina.query.filter_by(maquina_id=maquina.id).delete()
        db.session.delete(maquina)
        db.session.commit()
        flash("Máquina excluída com sucesso.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível excluir a máquina porque ainda existem vínculos.", "danger")
    return redirect(url_for("maquinas.listar"))


@maquinas_bp.route("/conferencia")
@roles_required("admin", "tecnico")
def conferencia():
    maquinas = (
        Maquina.query.options(
            selectinload(Maquina.conferencias).joinedload(ConferenciaMaquina.usuario),
            joinedload(Maquina.setor),
        )
        .order_by(Maquina.patrimonio)
        .all()
    )
    return render_template("maquinas/conferencia.html", maquinas=maquinas)


@maquinas_bp.route("/<int:id>/conferir", methods=["POST"])
@roles_required("admin", "tecnico")
def conferir(id):
    Maquina.query.get_or_404(id)
    try:
        status = choice(
            request.form,
            "status_conferencia",
            {"ok", "pendente", "inconsistente"},
            "Status da conferência",
        )
        db.session.add(
            ConferenciaMaquina(
                maquina_id=id,
                usuario_id=current_user.id,
                status_conferencia=status,
                observacao=optional_text(request.form, "observacao"),
            )
        )
        db.session.commit()
    except ValidationError as error:
        db.session.rollback()
        flash(str(error), "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível registrar a conferência.", "danger")
    else:
        flash("Conferência registrada com sucesso.", "success")
    return redirect(url_for("maquinas.conferencia"))


@maquinas_bp.route("/exportar/excel")
@roles_required("admin", "tecnico")
def exportar_excel():
    maquinas = machine_query().order_by(Maquina.id.asc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Máquinas"
    ws.append(["ID", "Patrimônio", "Nome", "Setor", "Local", "IP", "Status", "Responsável"])
    for maquina in maquinas:
        ws.append(
            [
                maquina.id,
                excel_safe(maquina.patrimonio),
                excel_safe(maquina.nome_maquina),
                excel_safe(maquina.setor.nome if maquina.setor else ""),
                excel_safe(maquina.localizacao),
                excel_safe(maquina.ip),
                maquina.status,
                excel_safe(maquina.usuario_responsavel.nome if maquina.usuario_responsavel else ""),
            ]
        )
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="maquinas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@maquinas_bp.route("/exportar/pdf")
@roles_required("admin", "tecnico")
def exportar_pdf():
    maquinas = machine_query().order_by(Maquina.id.asc()).all()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=landscape(A4))
    _width, height = landscape(A4)
    y = height - 30
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20, y, "Relatório de Máquinas")
    y -= 25
    pdf.setFont("Helvetica", 9)
    for maquina in maquinas:
        linha = (
            f"#{maquina.id} | {maquina.patrimonio} | {maquina.nome_maquina} | "
            f"Setor: {maquina.setor.nome if maquina.setor else '-'} | Local: {maquina.localizacao or '-'} | "
            f"Status: {maquina.status}"
        )
        pdf.drawString(20, y, linha[:170])
        y -= 14
        if y < 20:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 30
    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="maquinas.pdf", mimetype="application/pdf")
