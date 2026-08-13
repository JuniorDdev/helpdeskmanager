from app.extensions import db


class ConferenciaMaquina(db.Model):
    __tablename__ = "conferencias_maquinas"

    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey("maquinas.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    status_conferencia = db.Column(db.Enum("ok", "pendente", "inconsistente"), default="ok", nullable=False)
    observacao = db.Column(db.Text)
    conferido_em = db.Column(db.DateTime, server_default=db.func.now())

    maquina = db.relationship(
        "Maquina",
        backref=db.backref("conferencias", order_by="ConferenciaMaquina.conferido_em"),
    )
    usuario = db.relationship("Usuario")
