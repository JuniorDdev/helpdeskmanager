from app.extensions import db

class Manutencao(db.Model):
    __tablename__ = "manutencoes"
    __table_args__ = (
        db.CheckConstraint("custo >= 0", name="ck_manutencao_custo_nao_negativo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey("maquinas.id"), nullable=False)
    chamado_id = db.Column(db.Integer, db.ForeignKey("chamados.id"))
    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tipo = db.Column(db.Enum("preventiva", "corretiva"), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    peca_utilizada = db.Column(db.String(120))
    custo = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    data_manutencao = db.Column(db.DateTime, server_default=db.func.now())
    observacoes = db.Column(db.Text)

    maquina = db.relationship("Maquina")
    chamado = db.relationship("Chamado")
    tecnico = db.relationship("Usuario")
