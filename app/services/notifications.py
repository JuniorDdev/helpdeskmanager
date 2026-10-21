"""Centraliza as notificações que exigem visualização da equipe de suporte."""

from app.extensions import db
from app.models import NotificacaoSistema, Usuario
from app.utils.authz import SUPPORT_ROLES


def notify_support(tipo, titulo, mensagem, destino):
    """Cria uma notificação interna para administradores e técnicos ativos."""
    recipients = Usuario.query.filter(
        Usuario.ativo.is_(True), Usuario.perfil.in_(SUPPORT_ROLES)
    ).all()
    for recipient in recipients:
        db.session.add(
            NotificacaoSistema(
                usuario_id=recipient.id,
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
                destino=destino,
            )
        )
