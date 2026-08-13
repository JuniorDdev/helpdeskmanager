from app.extensions import db


class ConferenciaLivre(db.Model):
    __tablename__ = "conferencias_livres"

    id = db.Column(db.Integer, primary_key=True)
    patrimonio = db.Column(db.String(80))
    nome_maquina = db.Column(db.String(120))
    setor = db.Column(db.String(100))
    localizacao = db.Column(db.String(150))
    status_conferencia = db.Column(db.String(50), nullable=False)
    observacao = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    conferido_em = db.Column(db.DateTime, server_default=db.func.now())

    usuario = db.relationship("Usuario")
