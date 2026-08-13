import os
import secrets

from app import create_app
from app.extensions import db
from app.models import Usuario, Setor, SlaRegra, Estoque

app = create_app()

with app.app_context():
    db.create_all()

    admin_email = (os.getenv("ADMIN_EMAIL") or "admin@admin.com").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    if len(admin_password) < 10:
        raise RuntimeError("ADMIN_PASSWORD deve ter pelo menos 10 caracteres.")

    if not Usuario.query.filter_by(email=admin_email).first():
        admin = Usuario(
            nome="Administrador",
            email=admin_email,
            perfil="admin",
            setor="TI",
            telefone="",
            ativo=True,
        )
        admin.set_senha(admin_password)
        db.session.add(admin)

    setores_padrao = ["TI", "Financeiro", "RH", "Coordenação", "Secretaria", "Laboratório", "Almoxarifado"]
    for nome in setores_padrao:
        if not Setor.query.filter_by(nome=nome).first():
            db.session.add(Setor(nome=nome, descricao=f"Setor {nome}"))

    regras_sla = {
        "baixa": (240, 2880),
        "media": (120, 1440),
        "alta": (60, 480),
        "critica": (30, 240),
    }
    for prioridade, tempos in regras_sla.items():
        if not SlaRegra.query.filter_by(prioridade=prioridade).first():
            db.session.add(SlaRegra(
                prioridade=prioridade,
                tempo_resposta_minutos=tempos[0],
                tempo_resolucao_minutos=tempos[1],
            ))

    itens_padrao = [
        ("Mouse", "Periférico", 10, 3),
        ("Teclado", "Periférico", 10, 3),
        ("SSD 240GB", "Armazenamento", 5, 2),
        ("Memória RAM 8GB", "Hardware", 4, 2),
        ("Cabo de rede", "Rede", 20, 5),
        ("Toner", "Impressora", 3, 1),
    ]
    for nome, categoria, qtd, minimo in itens_padrao:
        if not Estoque.query.filter_by(nome_item=nome).first():
            db.session.add(Estoque(nome_item=nome, categoria=categoria, quantidade=qtd, estoque_minimo=minimo))

    db.session.commit()
    print("Banco inicializado com sucesso.")
    print(f"Login: {admin_email}")
    print(f"Senha inicial: {admin_password}")
