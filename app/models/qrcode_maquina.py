from app.extensions import db

class QRCodeMaquina(db.Model):
    __tablename__ = "qrcodes_maquinas"

    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey("maquinas.id"), nullable=False, unique=True)
    codigo = db.Column(db.String(255), nullable=False)
    imagem_qrcode = db.Column(db.String(255))
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    maquina = db.relationship("Maquina")
