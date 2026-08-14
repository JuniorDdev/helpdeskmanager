import os
import secrets

from app import create_app
from app.extensions import db
from app.models import Estoque, Laboratorio, Setor, SlaRegra, Usuario

app = create_app()

with app.app_context():
    db.create_all()

    admin_email = (os.getenv("ADMIN_EMAIL") or "admin@admin.com").strip().lower()
    configured_admin_password = os.getenv("ADMIN_PASSWORD")
    admin_password = configured_admin_password or secrets.token_urlsafe(12)
    if len(admin_password) < 10:
        raise RuntimeError("ADMIN_PASSWORD deve ter pelo menos 10 caracteres.")

    admin_created = not Usuario.query.filter_by(email=admin_email).first()
    if admin_created:
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

    laboratorio_inicial = Laboratorio.query.filter_by(nome="Laboratório de Informática").first()
    laboratorio_01 = Laboratorio.query.filter_by(nome="Lab 01").first()
    if laboratorio_inicial and not laboratorio_01:
        laboratorio_inicial.nome = "Lab 01"
        laboratorio_inicial.descricao = "Laboratório de informática 01."
    elif laboratorio_inicial and laboratorio_01:
        laboratorio_inicial.ativo = False

    for numero in range(1, 6):
        nome = f"Lab {numero:02d}"
        if not Laboratorio.query.filter_by(nome=nome).first():
            db.session.add(
                Laboratorio(
                    nome=nome,
                    localizacao="Bloco principal",
                    descricao=f"Laboratório de informática {numero:02d}.",
                    ativo=True,
                )
            )

    db.session.commit()
    print("Banco inicializado com sucesso.")
    print(f"Login: {admin_email}")
    if admin_created and not configured_admin_password:
        print(f"Senha inicial gerada: {admin_password}")
    elif admin_created:
        print("Administrador criado com a senha definida no arquivo .env.")
    else:
        print("O administrador já estava cadastrado; a senha existente foi preservada.")
