from app.extensions import db

class Maquina(db.Model):
    __tablename__ = "maquinas"

    id = db.Column(db.Integer, primary_key=True)
    patrimonio = db.Column(db.String(50), unique=True, nullable=False)
    nome_maquina = db.Column(db.String(100), nullable=False)
    usuario_responsavel_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    setor_id = db.Column(db.Integer, db.ForeignKey("setores.id"))
    localizacao = db.Column(db.String(150))
    processador = db.Column(db.String(120))
    memoria_ram = db.Column(db.String(50))
    armazenamento = db.Column(db.String(80))
    sistema_operacional = db.Column(db.String(100))
    ip = db.Column(db.String(45))
    mac_address = db.Column(db.String(50))
    status = db.Column(db.Enum("ativa", "manutencao", "reserva", "baixada"), default="ativa")
    foto = db.Column(db.String(255))
    ultima_manutencao = db.Column(db.Date)
    observacao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    usuario_responsavel = db.relationship("Usuario", foreign_keys=[usuario_responsavel_id])
    setor = db.relationship("Setor")
