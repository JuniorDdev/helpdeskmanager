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
    professor_nome = db.Column(db.String(120), nullable=False, default="")
    professor_matricula = db.Column(db.String(60), nullable=False, default="")
    quantidade_alunos = db.Column(db.Integer, nullable=False, default=0)
    titulo = db.Column(db.String(150), nullable=False)
    finalidade = db.Column(db.Text)
    softwares_necessarios = db.Column(db.Text)
    inicio = db.Column(db.DateTime, nullable=False, index=True)
    fim = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(
        db.Enum("solicitado", "agendado", "recusado", "cancelado", "excluido"),
        default="solicitado",
        nullable=False,
        index=True,
    )
    motivo_decisao = db.Column(db.Text)
    atendido_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), index=True)
    atendido_em = db.Column(db.DateTime)
    confirmado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    confirmado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    atualizado_em = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    laboratorio = db.relationship("Laboratorio", backref="agendamentos")
    usuario = db.relationship("Usuario", foreign_keys=[usuario_id], backref="agendamentos_laboratorio")
    atendido_por = db.relationship("Usuario", foreign_keys=[atendido_por_id])
    confirmado_por = db.relationship("Usuario", foreign_keys=[confirmado_por_id])

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

    @property
    def protocolo(self):
        return f"AGD-{self.id:05d}" if self.id else "AGD-pendente"


class HistoricoAgendamentoLaboratorio(db.Model):
    __tablename__ = "historico_agendamentos_laboratorio"

    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(
        db.Integer, db.ForeignKey("agendamentos_laboratorio.id"), nullable=False, index=True
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    acao = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    agendamento = db.relationship("AgendamentoLaboratorio", backref="historicos")
    usuario = db.relationship("Usuario")


class NotificacaoAgenda(db.Model):
    __tablename__ = "notificacoes_agenda"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    agendamento_id = db.Column(
        db.Integer, db.ForeignKey("agendamentos_laboratorio.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(40), nullable=False, default="solicitacao")
    mensagem = db.Column(db.String(255), nullable=False)
    lida_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)

    usuario = db.relationship("Usuario")
    agendamento = db.relationship("AgendamentoLaboratorio", backref="notificacoes")


class MensagemAgendamento(db.Model):
    __tablename__ = "mensagens_agendamento"
    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey("agendamentos_laboratorio.id"), nullable=False, index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    agendamento = db.relationship("AgendamentoLaboratorio", backref="mensagens")
    autor = db.relationship("Usuario")


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
