from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.models import Usuario
from app.utils.authz import roles_required
from app.utils.validation import ValidationError, choice, optional_text, required_text


auth_bp = Blueprint("auth", __name__)
USER_PROFILES = {"admin", "tecnico", "usuario", "almoxarife"}


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()
        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            return redirect(url_for("dashboard.index"))
        flash("E-mail ou senha inválidos.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com segurança.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/usuarios/novo", methods=["GET", "POST"])
@roles_required("admin")
def novo_usuario():
    if request.method == "POST":
        try:
            nome = required_text(request.form, "nome", "Nome", 120)
            email = required_text(request.form, "email", "E-mail", 120).lower()
            perfil = choice(request.form, "perfil", USER_PROFILES, "Perfil")
            senha = required_text(request.form, "senha", "Senha")
            if len(senha) < 10:
                raise ValidationError("A senha deve ter pelo menos 10 caracteres.")

            usuario = Usuario(
                nome=nome,
                email=email,
                perfil=perfil,
                setor=optional_text(request.form, "setor", 100),
                telefone=optional_text(request.form, "telefone", 30),
                ativo=True,
            )
            usuario.set_senha(senha)
            db.session.add(usuario)
            db.session.commit()
        except ValidationError as error:
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um usuário cadastrado com esse e-mail.", "danger")
        else:
            flash("Usuário cadastrado com sucesso.", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("auth/novo_usuario.html")
