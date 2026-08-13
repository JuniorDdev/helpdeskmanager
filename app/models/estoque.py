from app.extensions import db

class Estoque(db.Model):
    __tablename__ = "estoque"
    __table_args__ = (
        db.CheckConstraint("quantidade >= 0", name="ck_estoque_quantidade_nao_negativa"),
        db.CheckConstraint("estoque_minimo >= 0", name="ck_estoque_minimo_nao_negativo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome_item = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(80))
    descricao = db.Column(db.Text)
    quantidade = db.Column(db.Integer, default=0, nullable=False)
    estoque_minimo = db.Column(db.Integer, default=0, nullable=False)
    unidade = db.Column(db.String(30), default="unidade")
    local_armazenamento = db.Column(db.String(120))
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def baixo_estoque(self):
        return self.quantidade <= self.estoque_minimo

class MovimentacaoEstoque(db.Model):
    __tablename__ = "movimentacoes_estoque"
    __table_args__ = (
        db.CheckConstraint("quantidade > 0", name="ck_mov_estoque_quantidade_positiva"),
    )

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("estoque.id"), nullable=False)
    tipo = db.Column(db.Enum("entrada", "saida"), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    autorizado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    chamado_id = db.Column(db.Integer, db.ForeignKey("chamados.id"))
    observacao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    item = db.relationship("Estoque", backref="movimentacoes")
    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])
    autorizado_por = db.relationship("Usuario", foreign_keys=[autorizado_por_id])
    chamado = db.relationship("Chamado")
