from functools import wraps

from flask import abort, current_app
from flask_login import current_user, login_required


SUPPORT_ROLES = {"admin", "tecnico"}
STOCK_ROLES = {"admin", "almoxarife"}


def has_role(*roles):
    return current_user.is_authenticated and current_user.perfil in roles


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.perfil not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def master_admin_required(view):
    """Restringe a gestão completa de acessos ao administrador master configurado."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        master_email = (current_app.config.get("MASTER_ADMIN_EMAIL") or "").casefold()
        if current_user.perfil != "admin" or current_user.email.casefold() != master_email:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def is_master_admin():
    master_email = (current_app.config.get("MASTER_ADMIN_EMAIL") or "").casefold()
    return current_user.is_authenticated and current_user.perfil == "admin" and current_user.email.casefold() == master_email


def can_manage_ticket(chamado):
    return has_role(*SUPPORT_ROLES) or chamado.usuario_id == current_user.id
