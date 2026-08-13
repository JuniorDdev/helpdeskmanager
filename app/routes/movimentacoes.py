from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Maquina, MovimentacaoMaquina, Setor, Usuario
from app.utils.authz import roles_required
from app.utils.validation import ValidationError, optional_id, optional_text


movimentacoes_bp = Blueprint("movimentacoes", __name__, url_prefix="/movimentacoes")


@movimentacoes_bp.route("/")
@roles_required("admin", "tecnico")
def listar():
    page = request.args.get("page", 1, type=int)
    pagination = (
        MovimentacaoMaquina.query.options(
            joinedload(MovimentacaoMaquina.maquina),
            joinedload(MovimentacaoMaquina.setor_antigo),
            joinedload(MovimentacaoMaquina.setor_novo),
            joinedload(MovimentacaoMaquina.usuario_antigo),
            joinedload(MovimentacaoMaquina.usuario_novo),
            joinedload(MovimentacaoMaquina.movimentado_por),
        )
        .order_by(MovimentacaoMaquina.id.desc())
        .paginate(page=max(page, 1), per_page=25, error_out=False)
    )
    return render_template(
        "movimentacoes/listar.html", movimentacoes=pagination.items, pagination=pagination
    )


@movimentacoes_bp.route("/nova", methods=["GET", "POST"])
@roles_required("admin", "tecnico")
def nova():
    maquinas = Maquina.query.order_by(Maquina.nome_maquina).all()
    setores = Setor.query.order_by(Setor.nome).all()
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    if request.method == "POST":
        try:
            maquina_id = optional_id(request.form, "maquina_id")
            maquina = Maquina.query.filter_by(id=maquina_id).first()
            if not maquina:
                raise ValidationError("Máquina inválida.")

            setor_novo_id = optional_id(request.form, "setor_novo_id")
            usuario_novo_id = optional_id(request.form, "usuario_novo_id")
            autorizado_por_id = optional_id(request.form, "autorizado_por_id")
            if setor_novo_id and not Setor.query.filter_by(id=setor_novo_id).first():
                raise ValidationError("Setor inválido.")
            if usuario_novo_id and not Usuario.query.filter_by(id=usuario_novo_id, ativo=True).first():
                raise ValidationError("Novo responsável inválido.")
            if autorizado_por_id and not Usuario.query.filter_by(id=autorizado_por_id, ativo=True).first():
                raise ValidationError("Usuário autorizador inválido.")

            local_novo = optional_text(request.form, "local_novo", 150)
            if not local_novo:
                raise ValidationError("Novo local é obrigatório.")
            if (
                setor_novo_id == maquina.setor_id
                and usuario_novo_id == maquina.usuario_responsavel_id
                and local_novo == maquina.localizacao
            ):
                raise ValidationError("A movimentação não altera setor, local ou responsável.")

            mov = MovimentacaoMaquina(
                maquina_id=maquina.id,
                setor_antigo_id=maquina.setor_id,
                setor_novo_id=setor_novo_id,
                local_antigo=maquina.localizacao,
                local_novo=local_novo,
                usuario_antigo_id=maquina.usuario_responsavel_id,
                usuario_novo_id=usuario_novo_id,
                autorizado_por_id=autorizado_por_id,
                movimentado_por_id=current_user.id,
                motivo=optional_text(request.form, "motivo"),
            )
            maquina.setor_id = mov.setor_novo_id
            maquina.localizacao = mov.local_novo
            maquina.usuario_responsavel_id = mov.usuario_novo_id
            db.session.add(mov)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível registrar a movimentação.", "danger")
        else:
            flash("Movimentação de máquina registrada com sucesso.", "success")
            return redirect(url_for("movimentacoes.listar"))
    return render_template(
        "movimentacoes/form.html", maquinas=maquinas, setores=setores, usuarios=usuarios
    )
