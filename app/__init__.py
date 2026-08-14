import os

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError

from app.extensions import csrf, db, limiter, login_manager, migrate
from config import Config


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY não configurada. Copie .env.example para .env e defina uma chave segura."
        )

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        try:
            usuario = db.session.get(Usuario, int(user_id))
        except (TypeError, ValueError):
            return None
        return usuario if usuario and usuario.ativo else None

    from app.routes.auth import auth_bp
    from app.routes.agenda import agenda_bp
    from app.routes.chamados import chamados_bp
    from app.routes.conferencias import conferencias_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.estoque import estoque_bp
    from app.routes.manutencoes import manutencoes_bp
    from app.routes.maquinas import maquinas_bp
    from app.routes.movimentacoes import movimentacoes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(agenda_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(chamados_bp)
    app.register_blueprint(maquinas_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(manutencoes_bp)
    app.register_blueprint(movimentacoes_bp)
    app.register_blueprint(conferencias_bp)

    from app.cli import importar_agenda_excel_command

    app.cli.add_command(importar_agenda_excel_command)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; font-src 'self' https://cdn.jsdelivr.net; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template(
            "errors/error.html",
            status=400,
            titulo="Requisição inválida",
            mensagem="O formulário expirou ou não é válido. Atualize a página e tente novamente.",
        ), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template(
            "errors/error.html",
            status=403,
            titulo="Acesso negado",
            mensagem="Seu perfil não possui permissão para executar esta ação.",
        ), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "errors/error.html",
            status=404,
            titulo="Página não encontrada",
            mensagem="O endereço solicitado não existe.",
        ), 404

    @app.errorhandler(429)
    def rate_limited(_error):
        return render_template(
            "errors/error.html",
            status=429,
            titulo="Muitas tentativas",
            mensagem="Aguarde alguns minutos antes de tentar novamente.",
        ), 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error("Erro interno não tratado: %s", error)
        return render_template(
            "errors/error.html",
            status=500,
            titulo="Erro interno",
            mensagem="Não foi possível concluir a operação.",
        ), 500

    return app
