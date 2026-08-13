from app.extensions import db

class SlaRegra(db.Model):
    __tablename__ = "sla_regras"
    __table_args__ = (
        db.CheckConstraint("tempo_resposta_minutos > 0", name="ck_sla_resposta_positiva"),
        db.CheckConstraint("tempo_resolucao_minutos > 0", name="ck_sla_resolucao_positiva"),
    )

    id = db.Column(db.Integer, primary_key=True)
    prioridade = db.Column(
        db.Enum("baixa", "media", "alta", "critica"), nullable=False, unique=True
    )
    tempo_resposta_minutos = db.Column(db.Integer, nullable=False)
    tempo_resolucao_minutos = db.Column(db.Integer, nullable=False)
