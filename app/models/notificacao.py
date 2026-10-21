from app.extensions import db


class NotificacaoSistema(db.Model):
    __tablename__ = "notificacoes_sistema"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo = db.Column(db.String(50), nullable=False, index=True)
    titulo = db.Column(db.String(150), nullable=False)
    mensagem = db.Column(db.String(255), nullable=False)
    destino = db.Column(db.String(255), nullable=False)
    lida_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    usuario = db.relationship("Usuario", backref="notificacoes_sistema")
