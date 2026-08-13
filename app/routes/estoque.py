from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Chamado, Estoque, MovimentacaoEstoque, Usuario
from app.utils.authz import roles_required
from app.utils.export import excel_safe
from app.utils.validation import (
    ValidationError,
    choice,
    integer,
    optional_id,
    optional_text,
    required_text,
)


estoque_bp = Blueprint("estoque", __name__, url_prefix="/estoque")


def apply_item_fields(item):
    item.nome_item = required_text(request.form, "nome_item", "Nome do item", 120)
    item.categoria = optional_text(request.form, "categoria", 80)
    item.descricao = optional_text(request.form, "descricao")
    item.quantidade = integer(request.form, "quantidade", "Quantidade", minimum=0)
    item.estoque_minimo = integer(request.form, "estoque_minimo", "Estoque mínimo", minimum=0)
    item.unidade = optional_text(request.form, "unidade", 30) or "unidade"
    item.local_armazenamento = optional_text(request.form, "local_armazenamento", 120)


@estoque_bp.route("/")
@roles_required("admin", "almoxarife", "tecnico")
def listar():
    page = request.args.get("page", 1, type=int)
    pagination = Estoque.query.order_by(Estoque.nome_item.asc()).paginate(
        page=max(page, 1), per_page=25, error_out=False
    )
    return render_template("estoque/listar.html", itens=pagination.items, pagination=pagination)


@estoque_bp.route("/novo", methods=["GET", "POST"])
@roles_required("admin", "almoxarife")
def novo():
    if request.method == "POST":
        try:
            item = Estoque()
            apply_item_fields(item)
            db.session.add(item)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível cadastrar o item.", "danger")
        else:
            flash("Item cadastrado com sucesso.", "success")
            return redirect(url_for("estoque.listar"))
    return render_template("estoque/form.html", item=None)


@estoque_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@roles_required("admin", "almoxarife")
def editar(id):
    item = Estoque.query.get_or_404(id)
    if request.method == "POST":
        try:
            apply_item_fields(item)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível atualizar o item.", "danger")
        else:
            flash("Item atualizado com sucesso.", "success")
            return redirect(url_for("estoque.listar"))
    return render_template("estoque/form.html", item=item)


@estoque_bp.route("/<int:id>/excluir", methods=["POST"])
@roles_required("admin")
def excluir(id):
    senha_admin = request.form.get("senha_admin") or ""
    if not current_user.check_senha(senha_admin):
        flash("Senha de administrador inválida.", "danger")
        return redirect(url_for("estoque.listar"))

    item = Estoque.query.get_or_404(id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash("Item excluído com sucesso.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Não foi possível excluir o item porque existem movimentações vinculadas.", "danger")
    return redirect(url_for("estoque.listar"))


@estoque_bp.route("/<int:id>/movimentar", methods=["GET", "POST"])
@roles_required("admin", "almoxarife")
def movimentar(id):
    item = Estoque.query.get_or_404(id)
    chamados = Chamado.query.order_by(Chamado.id.desc()).limit(200).all()
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    if request.method == "POST":
        try:
            tipo = choice(request.form, "tipo", {"entrada", "saida"}, "Tipo de movimentação")
            quantidade = integer(request.form, "quantidade", "Quantidade", minimum=1)
            autorizado_por_id = optional_id(request.form, "autorizado_por_id")
            chamado_id = optional_id(request.form, "chamado_id")
            if autorizado_por_id and not Usuario.query.filter_by(id=autorizado_por_id, ativo=True).first():
                raise ValidationError("Usuário autorizador inválido.")
            if chamado_id and not Chamado.query.filter_by(id=chamado_id).first():
                raise ValidationError("Chamado inválido.")

            condition = Estoque.id == item.id
            if tipo == "saida":
                condition = condition & (Estoque.quantidade >= quantidade)
                new_quantity = Estoque.quantidade - quantidade
            else:
                new_quantity = Estoque.quantidade + quantidade

            result = db.session.execute(
                update(Estoque).where(condition).values(quantidade=new_quantity)
            )
            if result.rowcount != 1:
                raise ValidationError("Quantidade insuficiente em estoque.")

            db.session.add(
                MovimentacaoEstoque(
                    item_id=item.id,
                    tipo=tipo,
                    quantidade=quantidade,
                    usuario_id=current_user.id,
                    autorizado_por_id=autorizado_por_id,
                    chamado_id=chamado_id,
                    observacao=optional_text(request.form, "observacao"),
                )
            )
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível registrar a movimentação.", "danger")
        else:
            flash("Movimentação registrada com sucesso.", "success")
            return redirect(url_for("estoque.listar"))
    return render_template("estoque/movimentar.html", item=item, chamados=chamados, usuarios=usuarios)


@estoque_bp.route("/exportar/excel")
@roles_required("admin", "almoxarife", "tecnico")
def exportar_excel():
    itens = Estoque.query.order_by(Estoque.id.asc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Estoque"
    ws.append(["ID", "Item", "Categoria", "Quantidade", "Mínimo", "Unidade", "Local"])
    for item in itens:
        ws.append(
            [
                item.id,
                excel_safe(item.nome_item),
                excel_safe(item.categoria),
                item.quantidade,
                item.estoque_minimo,
                excel_safe(item.unidade),
                excel_safe(item.local_armazenamento),
            ]
        )
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="estoque.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@estoque_bp.route("/exportar/pdf")
@roles_required("admin", "almoxarife", "tecnico")
def exportar_pdf():
    itens = Estoque.query.order_by(Estoque.id.asc()).all()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=landscape(A4))
    _width, height = landscape(A4)
    y = height - 30
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20, y, "Relatório de Estoque")
    y -= 25
    pdf.setFont("Helvetica", 9)
    for item in itens:
        linha = (
            f"#{item.id} | {item.nome_item} | Cat: {item.categoria or '-'} | Qtd: {item.quantidade} | "
            f"Mín: {item.estoque_minimo} | Local: {item.local_armazenamento or '-'}"
        )
        pdf.drawString(20, y, linha[:170])
        y -= 14
        if y < 20:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 30
    pdf.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="estoque.pdf", mimetype="application/pdf")
