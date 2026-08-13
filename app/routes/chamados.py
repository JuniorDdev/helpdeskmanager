from datetime import datetime
from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Chamado, HistoricoChamado, Maquina, Setor, SlaRegra, Usuario
from app.services.sla import calculate_sla
from app.utils.authz import SUPPORT_ROLES, can_manage_ticket, has_role
from app.utils.export import excel_safe
from app.utils.validation import ValidationError, choice, optional_id, optional_text, required_text


chamados_bp = Blueprint("chamados", __name__, url_prefix="/chamados")
CATEGORIAS = {"computador", "impressora", "rede", "sistema", "internet", "ramal", "outros"}
PRIORIDADES = {"baixa", "media", "alta", "critica"}
STATUS = {"aberto", "em_andamento", "aguardando_peca", "finalizado", "cancelado"}


def visible_chamados_query():
    query = Chamado.query.options(
        joinedload(Chamado.usuario),
        joinedload(Chamado.tecnico),
        joinedload(Chamado.maquina),
        joinedload(Chamado.setor),
    )
    if not has_role(*SUPPORT_ROLES):
        query = query.filter(Chamado.usuario_id == current_user.id)
    return query


def form_options():
    tecnicos = Usuario.query.filter(Usuario.perfil.in_(SUPPORT_ROLES), Usuario.ativo.is_(True)).all()
    maquinas = Maquina.query
    if not has_role(*SUPPORT_ROLES):
        maquinas = maquinas.filter_by(usuario_responsavel_id=current_user.id)
    return tecnicos, maquinas.order_by(Maquina.nome_maquina).all(), Setor.query.order_by(Setor.nome).all()


def validate_relation(model, value, label, allowed_query=None):
    if value is None:
        return None
    query = allowed_query if allowed_query is not None else model.query
    if not query.filter_by(id=value).first():
        raise ValidationError(f"{label} inválido.")
    return value


def apply_common_fields(chamado):
    chamado.titulo = required_text(request.form, "titulo", "Título", 150)
    chamado.descricao = required_text(request.form, "descricao", "Descrição")
    chamado.categoria = choice(request.form, "categoria", CATEGORIAS, "Categoria")
    chamado.prioridade = choice(request.form, "prioridade", PRIORIDADES, "Prioridade")

    maquina_id = optional_id(request.form, "maquina_id")
    maquinas_permitidas = Maquina.query
    if not has_role(*SUPPORT_ROLES):
        maquinas_permitidas = maquinas_permitidas.filter_by(usuario_responsavel_id=current_user.id)
    chamado.maquina_id = validate_relation(Maquina, maquina_id, "Máquina", maquinas_permitidas)
    chamado.setor_id = validate_relation(Setor, optional_id(request.form, "setor_id"), "Setor")


def apply_requester_fields(chamado):
    """Allow a requester to edit the content of their own open ticket only."""
    chamado.titulo = required_text(request.form, "titulo", "Título", 150)
    chamado.descricao = required_text(request.form, "descricao", "Descrição")
    chamado.categoria = choice(request.form, "categoria", CATEGORIAS, "Categoria")
    chamado.prioridade = choice(request.form, "prioridade", PRIORIDADES, "Prioridade")


@chamados_bp.route("/")
@login_required
def listar():
    page = request.args.get("page", 1, type=int)
    pagination = visible_chamados_query().order_by(Chamado.id.desc()).paginate(
        page=max(page, 1), per_page=25, error_out=False
    )
    regras = {regra.prioridade: regra for regra in SlaRegra.query.all()}
    sla_status = {chamado.id: calculate_sla(chamado, regras) for chamado in pagination.items}
    return render_template(
        "chamados/listar.html",
        chamados=pagination.items,
        pagination=pagination,
        sla_status=sla_status,
    )


@chamados_bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    tecnicos, maquinas, setores = form_options()
    if request.method == "POST":
        try:
            chamado = Chamado(usuario_id=current_user.id, status="aberto")
            apply_common_fields(chamado)
            if has_role(*SUPPORT_ROLES):
                tecnico_id = optional_id(request.form, "tecnico_id")
                tecnicos_query = Usuario.query.filter(
                    Usuario.perfil.in_(SUPPORT_ROLES), Usuario.ativo.is_(True)
                )
                chamado.tecnico_id = validate_relation(Usuario, tecnico_id, "Técnico", tecnicos_query)

            db.session.add(chamado)
            db.session.flush()
            db.session.add(
                HistoricoChamado(
                    chamado_id=chamado.id,
                    usuario_id=current_user.id,
                    acao="Abertura",
                    descricao="Chamado aberto.",
                )
            )
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível abrir o chamado. Revise os dados informados.", "danger")
        else:
            flash("Chamado aberto com sucesso.", "success")
            return redirect(url_for("chamados.listar"))

    return render_template(
        "chamados/form.html",
        tecnicos=tecnicos,
        maquinas=maquinas,
        setores=setores,
        chamado=None,
        suporte=has_role(*SUPPORT_ROLES),
    )


@chamados_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    chamado = Chamado.query.get_or_404(id)
    if not can_manage_ticket(chamado):
        abort(403)
    suporte = has_role(*SUPPORT_ROLES)
    if not suporte and chamado.status != "aberto":
        abort(403)

    tecnicos, maquinas, setores = form_options()
    if request.method == "POST":
        try:
            status_anterior = chamado.status
            if suporte:
                apply_common_fields(chamado)
            else:
                apply_requester_fields(chamado)

            if suporte:
                novo_status = choice(request.form, "status", STATUS, "Status")
                tecnico_id = optional_id(request.form, "tecnico_id")
                tecnicos_query = Usuario.query.filter(
                    Usuario.perfil.in_(SUPPORT_ROLES), Usuario.ativo.is_(True)
                )
                chamado.tecnico_id = validate_relation(Usuario, tecnico_id, "Técnico", tecnicos_query)
                chamado.observacao_final = optional_text(request.form, "observacao_final")
                chamado.status = novo_status

                if novo_status == "em_andamento" and not chamado.iniciado_em:
                    chamado.iniciado_em = datetime.now()
                if novo_status == "finalizado" and status_anterior != "finalizado":
                    chamado.finalizado_em = datetime.now()
                    if chamado.aberto_em:
                        chamado.tempo_resolucao_minutos = max(
                            0, int((chamado.finalizado_em - chamado.aberto_em).total_seconds() / 60)
                        )
                elif status_anterior == "finalizado" and novo_status != "finalizado":
                    chamado.finalizado_em = None
                    chamado.tempo_resolucao_minutos = None

            acao = "Alteração de status" if status_anterior != chamado.status else "Atualização"
            descricao = (
                f"{status_anterior} -> {chamado.status}"
                if status_anterior != chamado.status
                else "Dados do chamado atualizados."
            )
            db.session.add(
                HistoricoChamado(
                    chamado_id=chamado.id,
                    usuario_id=current_user.id,
                    acao=acao,
                    descricao=descricao,
                )
            )
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível atualizar o chamado. Revise os dados informados.", "danger")
        else:
            flash("Chamado atualizado com sucesso.", "success")
            return redirect(url_for("chamados.listar"))

    return render_template(
        "chamados/form.html",
        chamado=chamado,
        tecnicos=tecnicos,
        maquinas=maquinas,
        setores=setores,
        suporte=suporte,
    )


@chamados_bp.route("/exportar/excel")
@login_required
def exportar_excel():
    chamados = visible_chamados_query().order_by(Chamado.id.asc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Chamados"
    ws.append(["ID", "Título", "Categoria", "Prioridade", "Status", "Técnico", "Data Abertura"])
    for chamado in chamados:
        ws.append(
            [
                chamado.id,
                excel_safe(chamado.titulo),
                chamado.categoria,
                chamado.prioridade,
                chamado.status,
                excel_safe(chamado.tecnico.nome if chamado.tecnico else ""),
                chamado.aberto_em.strftime("%Y-%m-%d %H:%M") if chamado.aberto_em else "",
            ]
        )
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="chamados.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@chamados_bp.route("/exportar/pdf")
@login_required
def exportar_pdf():
    chamados = visible_chamados_query().order_by(Chamado.id.asc()).all()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=landscape(A4))
    _width, height = landscape(A4)
    y = height - 30
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20, y, "Relatório de Chamados")
    y -= 25
    pdf.setFont("Helvetica", 9)
    for chamado in chamados:
        linha = (
            f"#{chamado.id} | {chamado.titulo} | {chamado.categoria} | {chamado.prioridade} | "
            f"{chamado.status} | Técnico: {chamado.tecnico.nome if chamado.tecnico else '-'}"
        )
        pdf.drawString(20, y, linha[:170])
        y -= 14
        if y < 20:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 30
    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="chamados.pdf", mimetype="application/pdf")
