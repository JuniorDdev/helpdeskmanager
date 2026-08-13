from functools import wraps

from flask import abort
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


def can_manage_ticket(chamado):
    return has_role(*SUPPORT_ROLES) or chamado.usuario_id == current_user.id
