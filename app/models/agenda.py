from datetime import time

from app.extensions import db


class Laboratorio(db.Model):
    __tablename__ = "laboratorios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    localizacao = db.Column(db.String(150))
    capacidade = db.Column(db.Integer)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False, index=True)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)


class AgendamentoLaboratorio(db.Model):
    __tablename__ = "agendamentos_laboratorio"
    __table_args__ = (
        db.CheckConstraint("fim > inicio", name="ck_agendamento_periodo_valido"),
        db.Index("ix_agendamento_laboratorio_periodo", "laboratorio_id", "inicio", "fim"),
    )

    id = db.Column(db.Integer, primary_key=True)
    laboratorio_id = db.Column(
        db.Integer, db.ForeignKey("laboratorios.id"), nullable=False, index=True
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    titulo = db.Column(db.String(150), nullable=False)
    finalidade = db.Column(db.Text)
    inicio = db.Column(db.DateTime, nullable=False, index=True)
    fim = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(
        db.Enum("agendado", "cancelado"), default="agendado", nullable=False, index=True
    )
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    laboratorio = db.relationship("Laboratorio", backref="agendamentos")
    usuario = db.relationship("Usuario", backref="agendamentos_laboratorio")

    @property
    def turno_codigo(self):
        """Compatibiliza reservas antigas por horário com o novo mapa por turno."""
        horario = self.inicio.time() if self.inicio else time.min
        if horario < time(12, 0):
            return "manha"
        if horario < time(18, 0):
            return "tarde"
        return "noite"

    @property
    def turno_label(self):
        return {"manha": "Manhã", "tarde": "Tarde", "noite": "Noite"}[self.turno_codigo]


class Recado(db.Model):
    __tablename__ = "recados"
    __table_args__ = (
        db.CheckConstraint("data_fim >= data_inicio", name="ck_recado_periodo_valido"),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    prioridade = db.Column(
        db.Enum("normal", "importante", "urgente"), default="normal", nullable=False, index=True
    )
    data_inicio = db.Column(db.Date, nullable=False, index=True)
    data_fim = db.Column(db.Date, nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    autor = db.relationship("Usuario", backref="recados_publicados")
