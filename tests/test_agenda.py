import unittest
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import (
    AgendamentoLaboratorio,
    HistoricoAgendamentoLaboratorio,
    Laboratorio,
    NotificacaoAgenda,
    NotificacaoSistema,
    Recado,
    Usuario,
)


class AgendaRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "RATELIMIT_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            admin = Usuario(
                nome="Admin Teste",
                email="admin@teste.local",
                senha_hash="inutilizado",
                perfil="admin",
                ativo=True,
            )
            usuario = Usuario(
                nome="Usuário Teste",
                email="usuario@teste.local",
                senha_hash="inutilizado",
                perfil="usuario",
                ativo=True,
            )
            outro = Usuario(
                nome="Outro Usuário",
                email="outro@teste.local",
                senha_hash="inutilizado",
                perfil="usuario",
                ativo=True,
            )
            professor = Usuario(
                nome="Professora Teste",
                email="professora@teste.local",
                senha_hash="inutilizado",
                perfil="professor",
                matricula="0-000000",
                ativo=True,
            )
            laboratorios = [Laboratorio(nome=f"Lab {numero:02d}", ativo=True) for numero in range(1, 6)]
            db.session.add_all([admin, usuario, outro, professor, *laboratorios])
            db.session.commit()
            self.admin_id = admin.id
            self.usuario_id = usuario.id
            self.outro_id = outro.id
            self.professor_id = professor.id
            self.laboratorio_id = laboratorios[0].id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, usuario_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(usuario_id)
            session["_fresh"] = True

    def test_solicitacoes_mesmo_turno_entram_em_fila(self):
        self.login(self.usuario_id)
        primeira = {
            "titulo": "Aula 8A",
            "professor_nome": "Usuário Teste",
            "professor_matricula": "MAT-001",
            "quantidade_alunos": "10",
            "laboratorio_id": self.laboratorio_id,
            "data_reserva": "2030-03-15",
            "turno": "manha",
            "data_retorno": "2030-03-15",
        }
        response = self.client.post("/agendamentos/novo", data=primeira)
        self.assertEqual(response.status_code, 302)

        segunda = dict(primeira, titulo="Aula 9B", professor_matricula="MAT-002")
        response = self.client.post("/agendamentos/novo", data=segunda)
        self.assertEqual(response.status_code, 302)

        outro_turno = dict(primeira, titulo="Aula 9C", turno="tarde")
        self.client.post("/agendamentos/novo", data=outro_turno)
        with self.app.app_context():
            self.assertEqual(AgendamentoLaboratorio.query.count(), 3)
            primeira_reserva = AgendamentoLaboratorio.query.order_by(AgendamentoLaboratorio.id).first()
            self.assertEqual(primeira_reserva.inicio, datetime(2030, 3, 15, 8, 0))
            self.assertEqual(primeira_reserva.fim, datetime(2030, 3, 15, 12, 0))
            self.assertEqual(primeira_reserva.status, "solicitado")
            self.assertEqual(HistoricoAgendamentoLaboratorio.query.count(), 3)
            self.assertEqual(NotificacaoAgenda.query.count(), 3)
            self.assertEqual(NotificacaoSistema.query.count(), 3)

    def test_relatorios_de_agendamentos_em_excel_e_pdf(self):
        with self.app.app_context():
            agendamento = AgendamentoLaboratorio(
                laboratorio_id=self.laboratorio_id,
                usuario_id=self.usuario_id,
                professor_nome="Usuário Teste",
                professor_matricula="0-000000",
                quantidade_alunos=18,
                titulo="Aula de programação",
                inicio=datetime(2030, 3, 15, 8, 0),
                fim=datetime(2030, 3, 15, 12, 0),
                status="agendado",
            )
            db.session.add(agendamento)
            db.session.commit()
        self.login(self.admin_id)

        page = self.client.get("/agendamentos/relatorios?periodo=mes&data=2030-03-15")
        excel = self.client.get("/agendamentos/relatorios/excel?periodo=mes&data=2030-03-15")
        pdf = self.client.get("/agendamentos/relatorios/pdf?periodo=ano&data=2030-03-15")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(excel.status_code, 200)
        self.assertIn("agendamentos_03-2030.xlsx", excel.headers["Content-Disposition"])
        self.assertTrue(excel.data.startswith(b"PK"))
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("agendamentos_2030.pdf", pdf.headers["Content-Disposition"])
        self.assertTrue(pdf.data.startswith(b"%PDF"))

    def test_admin_localiza_professor_e_redefine_senha(self):
        self.login(self.admin_id)

        busca = self.client.get("/professores/senha?busca=0-000000")
        atualizacao = self.client.post(
            "/professores/senha",
            data={
                "busca": "0-000000",
                "professor_id": self.professor_id,
                "senha": "senha-nova",
            },
        )

        self.assertEqual(busca.status_code, 200)
        self.assertIn(b"Professora Teste", busca.data)
        self.assertEqual(atualizacao.status_code, 302)
        with self.app.app_context():
            professor = db.session.get(Usuario, self.professor_id)
            self.assertTrue(professor.check_senha("senha-nova"))

    def test_nao_permite_agendamento_no_domingo(self):
        self.login(self.usuario_id)
        response = self.client.post(
            "/agendamentos/novo",
            data={
                "titulo": "Aula no domingo",
                "professor_nome": "Usuário Teste",
                "professor_matricula": "0-000000",
                "quantidade_alunos": "10",
                "laboratorio_id": self.laboratorio_id,
                "data_reserva": "2030-03-17",
                "turno": "manha",
            },
            follow_redirects=True,
        )
        self.assertIn("Não é possível agendar laboratórios aos domingos.".encode(), response.data)
        with self.app.app_context():
            self.assertEqual(AgendamentoLaboratorio.query.count(), 0)

    def test_usuario_altera_a_propria_senha_e_solicita_recuperacao(self):
        with self.app.app_context():
            usuario = db.session.get(Usuario, self.usuario_id)
            usuario.set_senha("senha-atual")
            db.session.commit()
        self.login(self.usuario_id)
        atualizacao = self.client.post(
            "/minha-senha",
            data={"senha_atual": "senha-atual", "nova_senha": "senha-nova"},
        )
        self.assertEqual(atualizacao.status_code, 302)
        with self.app.app_context():
            usuario = db.session.get(Usuario, self.usuario_id)
            self.assertTrue(usuario.check_senha("senha-nova"))

        with self.client.session_transaction() as session:
            session.clear()
        recuperacao = self.client.post(
            "/recuperar-senha",
            data={"identificador": "usuario@teste.local"},
        )
        self.assertEqual(recuperacao.status_code, 302)
        with self.app.app_context():
            notificacao = NotificacaoSistema.query.filter_by(tipo="recuperacao_senha").one()
            self.assertEqual(notificacao.usuario_id, self.admin_id)

    def test_professor_recupera_senha_com_dados_cadastrais(self):
        response = self.client.post(
            "/recuperar-senha-professor",
            data={
                "nome": "Professora Teste",
                "email": "professora@teste.local",
                "matricula": "0-000000",
                "senha": "nova-senha-professor",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            professor = db.session.get(Usuario, self.professor_id)
            self.assertTrue(professor.check_senha("nova-senha-professor"))

    def test_confirma_primeira_solicitacao_e_respeita_capacidade(self):
        with self.app.app_context():
            laboratorio = db.session.get(Laboratorio, self.laboratorio_id)
            laboratorio.capacidade = 10
            db.session.commit()
        self.login(self.usuario_id)
        dados = {
            "titulo": "Aula de redes",
            "professor_nome": "Usuário Teste",
            "professor_matricula": "MAT-001",
            "quantidade_alunos": "10",
            "laboratorio_id": self.laboratorio_id,
            "data_reserva": "2030-03-15",
            "turno": "manha",
        }
        self.client.post("/agendamentos/novo", data=dados)
        dados_2 = dict(dados, titulo="Aula posterior", professor_matricula="MAT-002")
        self.client.post("/agendamentos/novo", data=dados_2)
        with self.app.app_context():
            pendentes = AgendamentoLaboratorio.query.order_by(AgendamentoLaboratorio.id).all()
            primeiro_id, segundo_id = pendentes[0].id, pendentes[1].id

        self.login(self.admin_id)
        response = self.client.post(f"/agendamentos/{segundo_id}/confirmar", follow_redirects=True)
        self.assertIn("chegou antes".encode(), response.data)
        response = self.client.post(f"/agendamentos/{primeiro_id}/confirmar", follow_redirects=True)
        self.assertIn("confirmado:".encode(), response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(AgendamentoLaboratorio, primeiro_id).status, "agendado")
            self.assertEqual(HistoricoAgendamentoLaboratorio.query.filter_by(agendamento_id=primeiro_id).count(), 2)

        self.login(self.usuario_id)
        dados_excesso = dict(dados, data_reserva="2030-03-16", quantidade_alunos="11")
        response = self.client.post("/agendamentos/novo", data=dados_excesso, follow_redirects=True)
        self.assertIn("excede a capacidade".encode(), response.data)

    def test_recado_so_pode_ser_publicado_pelo_suporte(self):
        dados = {
            "titulo": "Manutenção da rede",
            "mensagem": "A internet poderá oscilar.",
            "prioridade": "importante",
            "data_inicio": "2030-03-15",
            "data_fim": "2030-03-16",
            "data_retorno": "2030-03-15",
        }
        self.login(self.usuario_id)
        self.assertEqual(self.client.post("/agendamentos/recados/novo", data=dados).status_code, 403)

        self.login(self.admin_id)
        self.assertEqual(self.client.post("/agendamentos/recados/novo", data=dados).status_code, 302)
        with self.app.app_context():
            self.assertEqual(Recado.query.count(), 1)

        self.login(self.usuario_id)
        response = self.client.get("/agendamentos/?data=2030-03-15")
        self.assertIn("Manutenção da rede".encode(), response.data)

    def test_proprietario_e_suporte_podem_cancelar_reserva(self):
        with self.app.app_context():
            booking = AgendamentoLaboratorio(
                laboratorio_id=self.laboratorio_id,
                usuario_id=self.outro_id,
                titulo="Capacitação",
                professor_nome="Outro Usuário",
                professor_matricula="MAT-003",
                quantidade_alunos=10,
                inicio=datetime(2030, 3, 15, 13, 0),
                fim=datetime(2030, 3, 15, 14, 0),
                status="agendado",
            )
            db.session.add(booking)
            db.session.commit()
            booking_id = booking.id

        self.login(self.usuario_id)
        self.assertEqual(
            self.client.post(f"/agendamentos/{booking_id}/cancelar").status_code, 403
        )

        self.login(self.admin_id)
        self.assertEqual(
            self.client.post(f"/agendamentos/{booking_id}/cancelar").status_code, 302
        )
        with self.app.app_context():
            self.assertEqual(db.session.get(AgendamentoLaboratorio, booking_id).status, "cancelado")
            self.assertEqual(HistoricoAgendamentoLaboratorio.query.filter_by(agendamento_id=booking_id).count(), 1)

    def test_dashboard_e_agenda_renderizam(self):
        self.login(self.usuario_id)
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/agendamentos/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agendamentos e laboratórios".encode(), response.data)
        self.assertIn("Disponibilidade por turno".encode(), response.data)
        self.assertIn(b"Lab 05", response.data)
        self.assertEqual(self.client.get("/agendamento-laboratorios").status_code, 200)

        self.login(self.admin_id)
        response = self.client.get("/agendamentos/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Gerenciar recados".encode(), response.data)
        self.assertIn("Gerenciar laboratórios".encode(), response.data)
        self.assertEqual(self.client.get("/agendamentos/recados").status_code, 200)

    def test_professor_acessa_somente_painel_de_agendamento(self):
        self.login(self.professor_id)
        response = self.client.get("/agendamento-laboratorios")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Professora Teste", response.data)
        self.assertIn(b"0-000000", response.data)
        self.assertEqual(self.client.get("/").status_code, 403)
        self.assertEqual(self.client.get("/chamados/").status_code, 403)

    def test_professor_ve_disponibilidade_sem_dados_de_outros(self):
        with self.app.app_context():
            db.session.add(
                AgendamentoLaboratorio(
                    laboratorio_id=self.laboratorio_id,
                    usuario_id=self.outro_id,
                    titulo="Aula reservada",
                    professor_nome="Outro Usuário",
                    professor_matricula="2-345678",
                    quantidade_alunos=10,
                    inicio=datetime(2030, 3, 15, 8, 0),
                    fim=datetime(2030, 3, 15, 12, 0),
                    status="agendado",
                )
            )
            db.session.commit()
        self.login(self.professor_id)
        response = self.client.get("/agendamento-laboratorios?data=2030-03-15")
        self.assertIn(b"Hor\xc3\xa1rio j\xc3\xa1 reservado", response.data)
        self.assertNotIn(b"Outro Usu\xc3\xa1rio", response.data)
        self.assertIn(b"lab=2", response.data)

    def test_professor_entra_com_matricula_e_senha(self):
        with self.app.app_context():
            professor = db.session.get(Usuario, self.professor_id)
            professor.set_senha("senha-professor-123")
            db.session.commit()

        response = self.client.post(
            "/login-professor",
            data={"matricula": "0-000000", "senha": "senha-professor-123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/agendamento-laboratorios"))

    def test_professor_pode_criar_proprio_cadastro(self):
        response = self.client.post(
            "/cadastro-professor",
            data={
                "nome": "Novo Professor",
                "email": "novo.professor@teste.local",
                "matricula": "1-234567",
                "senha": "senha6",
                "confirmacao_senha": "senha6",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/agendamento-laboratorios"))
        with self.app.app_context():
            professor = Usuario.query.filter_by(matricula="1-234567").first()
            self.assertIsNotNone(professor)
            self.assertEqual(professor.perfil, "professor")


if __name__ == "__main__":
    unittest.main()
