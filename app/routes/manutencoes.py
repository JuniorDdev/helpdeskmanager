from datetime import date
from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Chamado, Manutencao, Maquina, Usuario
from app.utils.authz import SUPPORT_ROLES, roles_required
from app.utils.export import excel_safe
from app.utils.validation import (
    ValidationError,
    choice,
    non_negative_decimal,
    optional_id,
    optional_text,
    required_text,
)


manutencoes_bp = Blueprint("manutencoes", __name__, url_prefix="/manutencoes")


def maintenance_query():
    return Manutencao.query.options(
        joinedload(Manutencao.maquina), joinedload(Manutencao.chamado), joinedload(Manutencao.tecnico)
    )


@manutencoes_bp.route("/")
@roles_required("admin", "tecnico")
def listar():
    page = request.args.get("page", 1, type=int)
    pagination = maintenance_query().order_by(Manutencao.id.desc()).paginate(
        page=max(page, 1), per_page=25, error_out=False
    )
    return render_template(
        "manutencoes/listar.html", manutencoes=pagination.items, pagination=pagination
    )


@manutencoes_bp.route("/nova", methods=["GET", "POST"])
@roles_required("admin", "tecnico")
def nova():
    maquinas = Maquina.query.order_by(Maquina.nome_maquina).all()
    chamados = Chamado.query.order_by(Chamado.id.desc()).limit(200).all()
    tecnicos = Usuario.query.filter(
        Usuario.perfil.in_(SUPPORT_ROLES), Usuario.ativo.is_(True)
    ).order_by(Usuario.nome).all()
    if request.method == "POST":
        try:
            maquina_id = optional_id(request.form, "maquina_id")
            tecnico_id = optional_id(request.form, "tecnico_id")
            chamado_id = optional_id(request.form, "chamado_id")
            maquina = Maquina.query.filter_by(id=maquina_id).first()
            if not maquina:
                raise ValidationError("Máquina inválida.")
            tecnico = Usuario.query.filter(
                Usuario.id == tecnico_id,
                Usuario.perfil.in_(SUPPORT_ROLES),
                Usuario.ativo.is_(True),
            ).first()
            if not tecnico:
                raise ValidationError("Técnico inválido.")
            if chamado_id and not Chamado.query.filter_by(id=chamado_id).first():
                raise ValidationError("Chamado inválido.")

            manutencao = Manutencao(
                maquina_id=maquina.id,
                chamado_id=chamado_id,
                tecnico_id=tecnico.id,
                tipo=choice(request.form, "tipo", {"preventiva", "corretiva"}, "Tipo"),
                descricao=required_text(request.form, "descricao", "Descrição"),
                peca_utilizada=optional_text(request.form, "peca_utilizada", 120),
                custo=non_negative_decimal(request.form, "custo", "Custo"),
                observacoes=optional_text(request.form, "observacoes"),
            )
            maquina.ultima_manutencao = date.today()
            db.session.add(manutencao)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível registrar a manutenção.", "danger")
        else:
            flash("Manutenção registrada com sucesso.", "success")
            return redirect(url_for("manutencoes.listar"))
    return render_template(
        "manutencoes/form.html", maquinas=maquinas, chamados=chamados, tecnicos=tecnicos
    )


@manutencoes_bp.route("/exportar/excel")
@roles_required("admin", "tecnico")
def exportar_excel():
    manutencoes = maintenance_query().order_by(Manutencao.id.asc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Manutenções"
    ws.append(["ID", "Máquina", "Tipo", "Técnico", "Peça", "Custo", "Data"])
    for manutencao in manutencoes:
        ws.append(
            [
                manutencao.id,
                excel_safe(
                    f"{manutencao.maquina.patrimonio} - {manutencao.maquina.nome_maquina}"
                    if manutencao.maquina
                    else ""
                ),
                manutencao.tipo,
                excel_safe(manutencao.tecnico.nome if manutencao.tecnico else ""),
                excel_safe(manutencao.peca_utilizada),
                float(manutencao.custo or 0),
                manutencao.data_manutencao.strftime("%Y-%m-%d") if manutencao.data_manutencao else "",
            ]
        )
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="manutencoes.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@manutencoes_bp.route("/exportar/pdf")
@roles_required("admin", "tecnico")
def exportar_pdf():
    manutencoes = maintenance_query().order_by(Manutencao.id.asc()).all()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=landscape(A4))
    _width, height = landscape(A4)
    y = height - 30
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20, y, "Relatório de Manutenções")
    y -= 25
    pdf.setFont("Helvetica", 9)
    for manutencao in manutencoes:
        linha = (
            f"#{manutencao.id} | {manutencao.maquina.nome_maquina if manutencao.maquina else '-'} | "
            f"{manutencao.tipo} | Técnico: {manutencao.tecnico.nome if manutencao.tecnico else '-'} | "
            f"Peça: {manutencao.peca_utilizada or '-'} | Custo: R$ {manutencao.custo}"
        )
        pdf.drawString(20, y, linha[:170])
        y -= 14
        if y < 20:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 30
    pdf.save()
    output.seek(0)
    return send_file(
        output, as_attachment=True, download_name="manutencoes.pdf", mimetype="application/pdf"
    )
