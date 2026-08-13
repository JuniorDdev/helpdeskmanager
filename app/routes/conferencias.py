from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ConferenciaLivre
from app.utils.authz import roles_required
from app.utils.validation import ValidationError, choice, optional_text


conferencias_bp = Blueprint("conferencias", __name__, url_prefix="/conferencias")


@conferencias_bp.route("/", methods=["GET", "POST"])
@roles_required("admin", "tecnico")
def index():
    if request.method == "POST":
        try:
            patrimonio = optional_text(request.form, "patrimonio", 80)
            nome_maquina = optional_text(request.form, "nome_maquina", 120)
            if not patrimonio and not nome_maquina:
                raise ValidationError("Informe ao menos o patrimônio ou o nome da máquina.")
            registro = ConferenciaLivre(
                patrimonio=patrimonio,
                nome_maquina=nome_maquina,
                setor=optional_text(request.form, "setor", 100),
                localizacao=optional_text(request.form, "localizacao", 150),
                status_conferencia=choice(
                    request.form,
                    "status_conferencia",
                    {"ok", "pendente", "inconsistente"},
                    "Status",
                ),
                observacao=optional_text(request.form, "observacao"),
                usuario_id=current_user.id,
            )
            db.session.add(registro)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Não foi possível registrar a conferência.", "danger")
        else:
            flash("Conferência registrada com sucesso.", "success")
            return redirect(url_for("conferencias.index"))

    page = request.args.get("page", 1, type=int)
    pagination = (
        ConferenciaLivre.query.options(joinedload(ConferenciaLivre.usuario))
        .order_by(ConferenciaLivre.id.desc())
        .paginate(page=max(page, 1), per_page=25, error_out=False)
    )
    return render_template(
        "conferencias/index.html", registros=pagination.items, pagination=pagination
    )
