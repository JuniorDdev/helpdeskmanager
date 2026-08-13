from app.extensions import db

class MovimentacaoMaquina(db.Model):
    __tablename__ = "movimentacoes_maquinas"

    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey("maquinas.id"), nullable=False)
    setor_antigo_id = db.Column(db.Integer, db.ForeignKey("setores.id"))
    setor_novo_id = db.Column(db.Integer, db.ForeignKey("setores.id"))
    local_antigo = db.Column(db.String(150))
    local_novo = db.Column(db.String(150))
    usuario_antigo_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario_novo_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    autorizado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    movimentado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    motivo = db.Column(db.Text)
    data_movimentacao = db.Column(db.DateTime, server_default=db.func.now())

    maquina = db.relationship("Maquina")
    setor_antigo = db.relationship("Setor", foreign_keys=[setor_antigo_id])
    setor_novo = db.relationship("Setor", foreign_keys=[setor_novo_id])
    usuario_antigo = db.relationship("Usuario", foreign_keys=[usuario_antigo_id])
    usuario_novo = db.relationship("Usuario", foreign_keys=[usuario_novo_id])
    autorizado_por = db.relationship("Usuario", foreign_keys=[autorizado_por_id])
    movimentado_por = db.relationship("Usuario", foreign_keys=[movimentado_por_id])
