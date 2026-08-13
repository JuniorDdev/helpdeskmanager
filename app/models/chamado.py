from app.extensions import db

class Chamado(db.Model):
    __tablename__ = "chamados"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.Enum("computador", "impressora", "rede", "sistema", "internet", "ramal", "outros"), nullable=False)
    prioridade = db.Column(
        db.Enum("baixa", "media", "alta", "critica"), default="media", nullable=False, index=True
    )
    status = db.Column(
        db.Enum("aberto", "em_andamento", "aguardando_peca", "finalizado", "cancelado"),
        default="aberto",
        nullable=False,
        index=True,
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    maquina_id = db.Column(db.Integer, db.ForeignKey("maquinas.id"))
    setor_id = db.Column(db.Integer, db.ForeignKey("setores.id"))
    aberto_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    iniciado_em = db.Column(db.DateTime)
    finalizado_em = db.Column(db.DateTime)
    tempo_resolucao_minutos = db.Column(db.Integer)
    observacao_final = db.Column(db.Text)

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])
    tecnico = db.relationship("Usuario", foreign_keys=[tecnico_id])
    maquina = db.relationship("Maquina")
    setor = db.relationship("Setor")

class HistoricoChamado(db.Model):
    __tablename__ = "historico_chamados"

    id = db.Column(db.Integer, primary_key=True)
    chamado_id = db.Column(db.Integer, db.ForeignKey("chamados.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    acao = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    chamado = db.relationship("Chamado", backref="historicos")
    usuario = db.relationship("Usuario")
