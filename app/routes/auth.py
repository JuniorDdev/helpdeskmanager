import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db, limiter
from app.models import AuditoriaAdmin, Usuario
from app.services.notifications import notify_support
from app.utils.authz import master_admin_required, roles_required
from app.utils.validation import ValidationError, choice, optional_text, required_text


auth_bp = Blueprint("auth", __name__)
USER_PROFILES = {"admin", "tecnico", "usuario", "almoxarife", "professor"}
MATRICULA_PROFESSOR_PATTERN = re.compile(r"^\d-\d{6}$")


def professor_matricula(value):
    matricula = (value or "").strip()
    if not MATRICULA_PROFESSOR_PATTERN.fullmatch(matricula):
        raise ValidationError("A matrícula deve seguir o padrão 0-000000.")
    return matricula


def staff_matricula(value):
    return required_text({"matricula": value}, "matricula", "Matrícula", 60)


def normalized_name(value):
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def usuario_por_matricula_curta(identificador):
    """Localiza um membro da equipe pelos últimos dígitos da matrícula oficial."""
    digitos = re.sub(r"\D", "", identificador or "")
    if not digitos or len(digitos) < 4 or not identificador.strip().isdigit():
        return None
    candidatos = Usuario.query.filter(
        Usuario.ativo.is_(True),
        Usuario.perfil.in_({"admin", "tecnico"}),
        Usuario.matricula.like(f"%{digitos}"),
    ).all()
    candidatos = [
        usuario
        for usuario in candidatos
        if re.sub(r"\D", "", usuario.matricula or "").endswith(digitos)
    ]
    return candidatos[0] if len(candidatos) == 1 else None


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        if current_user.perfil == "professor":
            return redirect(url_for("agendamento_laboratorios"))
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        identificador = (request.form.get("identificador") or request.form.get("email") or "").strip()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter(
            Usuario.ativo.is_(True),
            or_(
                db.func.lower(Usuario.email) == identificador.lower(),
                Usuario.matricula == identificador,
            ),
        ).first()
        if not usuario:
            usuario = usuario_por_matricula_curta(identificador)
        if usuario and usuario.perfil == "professor":
            flash("Professores devem acessar com matrícula e senha.", "info")
            return redirect(url_for("auth.login_professor"))
        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            return redirect(url_for("dashboard.index"))
        flash("E-mail ou matrícula, ou senha inválidos.", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/login-professor", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login_professor():
    if current_user.is_authenticated:
        return redirect(
            url_for("agendamento_laboratorios")
            if current_user.perfil == "professor"
            else url_for("dashboard.index")
        )

    if request.method == "POST":
        matricula = (request.form.get("matricula") or "").strip()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(
            matricula=matricula, perfil="professor", ativo=True
        ).first()
        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            return redirect(url_for("agendamento_laboratorios"))
        flash("Matrícula ou senha inválidas.", "danger")
    return render_template("auth/login_professor.html")


@auth_bp.route("/cadastro-professor", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def cadastro_professor():
    if current_user.is_authenticated:
        return redirect(
            url_for("agendamento_laboratorios")
            if current_user.perfil == "professor"
            else url_for("dashboard.index")
        )

    if request.method == "POST":
        try:
            nome = required_text(request.form, "nome", "Nome", 120)
            email = required_text(request.form, "email", "E-mail", 120).lower()
            matricula = professor_matricula(request.form.get("matricula"))
            senha = required_text(request.form, "senha", "Senha")
            confirmacao_senha = request.form.get("confirmacao_senha") or ""
            if len(senha) < 6:
                raise ValidationError("A senha deve ter pelo menos 6 caracteres.")
            if senha != confirmacao_senha:
                raise ValidationError("A confirmação de senha não confere.")

            usuario = Usuario(
                nome=nome,
                email=email,
                matricula=matricula,
                perfil="professor",
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
            flash("Já existe um Professor cadastrado com este e-mail ou matrícula.", "danger")
        else:
            login_user(usuario)
            flash("Cadastro concluído. Agora você já pode solicitar um laboratório.", "success")
            return redirect(url_for("agendamento_laboratorios"))

    return render_template("auth/cadastro_professor.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com segurança.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/minha-senha", methods=["GET", "POST"])
@login_required
def minha_senha():
    if request.method == "POST":
        try:
            senha_atual = request.form.get("senha_atual") or ""
            nova_senha = required_text(request.form, "nova_senha", "Nova senha")
            if not current_user.check_senha(senha_atual):
                raise ValidationError("A senha atual está incorreta.")
            if len(nova_senha) < 6:
                raise ValidationError("A nova senha deve ter pelo menos 6 caracteres.")
            current_user.set_senha(nova_senha)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        else:
            flash("Sua senha foi atualizada com sucesso.", "success")
            return redirect(url_for("auth.minha_senha"))
    return render_template("auth/minha_senha.html")


@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def recuperar_senha():
    if current_user.is_authenticated:
        return redirect(url_for("auth.minha_senha"))
    if request.method == "POST":
        identificador = (request.form.get("identificador") or "").strip()
        usuario = None
        if identificador:
            usuario = Usuario.query.filter(
                Usuario.ativo.is_(True),
                or_(
                    db.func.lower(Usuario.email) == identificador.lower(),
                    Usuario.matricula == identificador,
                ),
            ).first()
        if usuario:
            notify_support(
                "recuperacao_senha",
                "Solicitação de recuperação de senha",
                f"{usuario.nome} solicitou recuperação de senha ({usuario.email}).",
                url_for("auth.redefinir_senha_usuario", busca=usuario.email),
            )
            db.session.commit()
        flash(
            "Se os dados informados estiverem cadastrados, a equipe receberá sua solicitação de recuperação.",
            "success",
        )
        return redirect(url_for("auth.login"))
    return render_template("auth/recuperar_senha.html")


@auth_bp.route("/recuperar-senha-professor", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def recuperar_senha_professor():
    if current_user.is_authenticated:
        return redirect(
            url_for("auth.minha_senha")
            if current_user.perfil == "professor"
            else url_for("dashboard.index")
        )
    if request.method == "POST":
        try:
            nome = required_text(request.form, "nome", "Nome completo", 120)
            email = required_text(request.form, "email", "E-mail", 120).lower()
            matricula = professor_matricula(request.form.get("matricula"))
            senha = required_text(request.form, "senha", "Nova senha")
            if len(senha) < 6:
                raise ValidationError("A nova senha deve ter pelo menos 6 caracteres.")
            professor = Usuario.query.filter_by(
                perfil="professor", ativo=True, email=email, matricula=matricula
            ).first()
            if not professor or normalized_name(professor.nome) != normalized_name(nome):
                raise ValidationError("Os dados informados não conferem com um professor cadastrado.")
            professor.set_senha(senha)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        else:
            flash("Senha atualizada. Agora entre com sua matrícula e a nova senha.", "success")
            return redirect(url_for("auth.login_professor"))
    return render_template("auth/recuperar_senha_professor.html")


@auth_bp.route("/usuarios/novo", methods=["GET", "POST"])
@master_admin_required
def novo_usuario():
    if request.method == "POST":
        try:
            nome = required_text(request.form, "nome", "Nome", 120)
            email = required_text(request.form, "email", "E-mail", 120).lower()
            perfil = choice(request.form, "perfil", USER_PROFILES, "Perfil")
            matricula = optional_text(request.form, "matricula", 60)
            if perfil == "professor":
                matricula = professor_matricula(matricula)
            elif perfil in {"admin", "tecnico"}:
                matricula = staff_matricula(matricula)
            senha = required_text(request.form, "senha", "Senha")
            if len(senha) < 6:
                raise ValidationError("A senha deve ter pelo menos 6 caracteres.")

            usuario = Usuario(
                nome=nome,
                email=email,
                perfil=perfil,
                setor=optional_text(request.form, "setor", 100),
                telefone=optional_text(request.form, "telefone", 30),
                matricula=matricula or None,
                ativo=True,
            )
            usuario.set_senha(senha)
            db.session.add(usuario)
            db.session.commit()
        except ValidationError as error:
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um usuário cadastrado com esse e-mail ou matrícula.", "danger")
        else:
            flash("Usuário cadastrado com sucesso.", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("auth/novo_usuario.html")


@auth_bp.route("/usuarios")
@master_admin_required
def listar_usuarios():
    busca = (request.args.get("busca") or "").strip()
    perfil = (request.args.get("perfil") or "").strip()
    query = Usuario.query
    if busca:
        termo = f"%{busca}%"
        query = query.filter(
            or_(
                Usuario.nome.ilike(termo),
                Usuario.email.ilike(termo),
                Usuario.matricula.ilike(termo),
            )
        )
    if perfil in USER_PROFILES:
        query = query.filter_by(perfil=perfil)
    usuarios = query.order_by(Usuario.nome).all()
    return render_template(
        "auth/listar_usuarios.html",
        busca=busca,
        perfil=perfil,
        perfis=sorted(USER_PROFILES),
        usuarios=usuarios,
    )


@auth_bp.route("/usuarios/<int:id>/editar", methods=["GET", "POST"])
@master_admin_required
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if request.method == "POST":
        try:
            nome = required_text(request.form, "nome", "Nome", 120)
            email = required_text(request.form, "email", "E-mail", 120).lower()
            perfil = choice(request.form, "perfil", USER_PROFILES, "Perfil")
            matricula = optional_text(request.form, "matricula", 60)
            if perfil == "professor":
                matricula = professor_matricula(matricula)
            elif perfil in {"admin", "tecnico"}:
                matricula = staff_matricula(matricula)
            if usuario.id == current_user.id and request.form.get("ativo") != "on":
                raise ValidationError("Você não pode desativar o próprio acesso.")

            usuario.nome = nome
            usuario.email = email
            usuario.perfil = perfil
            usuario.matricula = matricula or None
            usuario.setor = optional_text(request.form, "setor", 100)
            usuario.telefone = optional_text(request.form, "telefone", 30)
            usuario.ativo = request.form.get("ativo") == "on"
            nova_senha = optional_text(request.form, "senha")
            if nova_senha:
                if len(nova_senha) < 6:
                    raise ValidationError("A nova senha deve ter pelo menos 6 caracteres.")
                usuario.set_senha(nova_senha)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um usuário cadastrado com esse e-mail ou matrícula.", "danger")
        else:
            flash(f"Cadastro de {usuario.nome} atualizado com sucesso.", "success")
            return redirect(url_for("auth.listar_usuarios", busca=usuario.matricula or usuario.email))
    return render_template("auth/editar_usuario.html", usuario=usuario, perfis=sorted(USER_PROFILES))


@auth_bp.route("/auditoria")
@master_admin_required
def auditoria():
    busca = (request.args.get("busca") or "").strip()
    consulta = AuditoriaAdmin.query.outerjoin(Usuario, AuditoriaAdmin.usuario_id == Usuario.id)
    if busca:
        termo = f"%{busca}%"
        consulta = consulta.filter(
            or_(
                Usuario.nome.ilike(termo),
                AuditoriaAdmin.matricula.ilike(termo),
                AuditoriaAdmin.modulo.ilike(termo),
                AuditoriaAdmin.acao.ilike(termo),
                AuditoriaAdmin.alteracoes.ilike(termo),
            )
        )
    pagina = max(request.args.get("page", 1, type=int), 1)
    registros_paginados = consulta.order_by(
        AuditoriaAdmin.criado_em.desc(), AuditoriaAdmin.id.desc()
    ).paginate(page=pagina, per_page=20, error_out=False)
    return render_template(
        "auth/auditoria.html",
        registros=registros_paginados.items,
        pagination=registros_paginados,
        busca=busca,
    )


@auth_bp.route("/minha-matricula", methods=["GET", "POST"])
@roles_required("admin", "tecnico")
def minha_matricula():
    if request.method == "POST":
        try:
            current_user.matricula = staff_matricula(request.form.get("matricula"))
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Esta matrícula já está cadastrada para outro usuário.", "danger")
        else:
            flash("Matrícula atualizada. Ela será registrada nas próximas decisões de agenda.", "success")
            return redirect(url_for("agenda.index"))
    return render_template("auth/minha_matricula.html")


@auth_bp.route("/usuarios/senha", methods=["GET", "POST"])
@master_admin_required
def redefinir_senha_usuario():
    termo = (request.values.get("busca") or "").strip()
    usuarios = []
    if termo:
        usuarios = (
            Usuario.query.filter(
                Usuario.ativo.is_(True),
                or_(
                    db.func.lower(Usuario.email) == termo.lower(),
                    Usuario.matricula == termo,
                ),
            )
            .order_by(Usuario.nome)
            .all()
        )
    if request.method == "POST":
        try:
            usuario_id = request.form.get("usuario_id", type=int)
            usuario = Usuario.query.filter_by(id=usuario_id, ativo=True).first()
            if not usuario:
                raise ValidationError("Usuário não encontrado.")
            senha = required_text(request.form, "senha", "Nova senha")
            if len(senha) < 6:
                raise ValidationError("A nova senha deve ter pelo menos 6 caracteres.")
            usuario.set_senha(senha)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        else:
            flash(f"Senha de {usuario.nome} atualizada com sucesso.", "success")
            return redirect(url_for("auth.redefinir_senha_usuario", busca=usuario.email))
    return render_template("auth/redefinir_senha_usuario.html", busca=termo, usuarios=usuarios)


@auth_bp.route("/professores/senha", methods=["GET", "POST"])
@master_admin_required
def redefinir_senha_professor():
    termo = (request.values.get("busca") or "").strip()
    professores = []
    if termo:
        professores = (
            Usuario.query.filter(
                Usuario.perfil == "professor",
                or_(
                    db.func.lower(Usuario.email) == termo.lower(),
                    Usuario.matricula == termo,
                ),
            )
            .order_by(Usuario.nome)
            .all()
        )

    if request.method == "POST":
        try:
            professor_id = request.form.get("professor_id", type=int)
            professor = Usuario.query.filter_by(id=professor_id, perfil="professor").first()
            if not professor:
                raise ValidationError("Professor não encontrado.")
            senha = required_text(request.form, "senha", "Nova senha")
            if len(senha) < 6:
                raise ValidationError("A nova senha deve ter pelo menos 6 caracteres.")
            professor.set_senha(senha)
            db.session.commit()
        except ValidationError as error:
            db.session.rollback()
            flash(str(error), "danger")
        else:
            flash(f"Senha de {professor.nome} atualizada com sucesso.", "success")
            return redirect(url_for("auth.redefinir_senha_professor", busca=professor.matricula))

    return render_template(
        "auth/redefinir_senha_professor.html", busca=termo, professores=professores
    )
