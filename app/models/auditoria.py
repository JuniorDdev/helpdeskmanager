from app.extensions import db


class AuditoriaAdmin(db.Model):
    __tablename__ = "auditoria_admin"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    matricula = db.Column(db.String(60), nullable=False, default="")
    modulo = db.Column(db.String(80), nullable=False)
    acao = db.Column(db.String(20), nullable=False)
    registro_id = db.Column(db.Integer)
    alteracoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    usuario = db.relationship("Usuario")
