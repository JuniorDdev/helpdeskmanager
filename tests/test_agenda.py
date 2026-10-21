import unittest
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import (
    AgendamentoLaboratorio,
    HistoricoAgendamentoLaboratorio,
    Laboratorio,
    NotificacaoAgenda,
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
            laboratorios = [Laboratorio(nome=f"Lab {numero:02d}", ativo=True) for numero in range(1, 6)]
            db.session.add_all([admin, usuario, outro, *laboratorios])
            db.session.commit()
            self.admin_id = admin.id
            self.usuario_id = usuario.id
            self.outro_id = outro.id
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
        response = self.client.post("/agenda/agendamentos/novo", data=primeira)
        self.assertEqual(response.status_code, 302)

        segunda = dict(primeira, titulo="Aula 9B", professor_matricula="MAT-002")
        response = self.client.post("/agenda/agendamentos/novo", data=segunda)
        self.assertEqual(response.status_code, 302)

        outro_turno = dict(primeira, titulo="Aula 9C", turno="tarde")
        self.client.post("/agenda/agendamentos/novo", data=outro_turno)
        with self.app.app_context():
            self.assertEqual(AgendamentoLaboratorio.query.count(), 3)
            primeira_reserva = AgendamentoLaboratorio.query.order_by(AgendamentoLaboratorio.id).first()
            self.assertEqual(primeira_reserva.inicio, datetime(2030, 3, 15, 8, 0))
            self.assertEqual(primeira_reserva.fim, datetime(2030, 3, 15, 12, 0))
            self.assertEqual(primeira_reserva.status, "solicitado")
            self.assertEqual(HistoricoAgendamentoLaboratorio.query.count(), 3)
            self.assertEqual(NotificacaoAgenda.query.count(), 3)

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
        self.client.post("/agenda/agendamentos/novo", data=dados)
        dados_2 = dict(dados, titulo="Aula posterior", professor_matricula="MAT-002")
        self.client.post("/agenda/agendamentos/novo", data=dados_2)
        with self.app.app_context():
            pendentes = AgendamentoLaboratorio.query.order_by(AgendamentoLaboratorio.id).all()
            primeiro_id, segundo_id = pendentes[0].id, pendentes[1].id

        self.login(self.admin_id)
        response = self.client.post(f"/agenda/agendamentos/{segundo_id}/confirmar", follow_redirects=True)
        self.assertIn("chegou antes".encode(), response.data)
        response = self.client.post(f"/agenda/agendamentos/{primeiro_id}/confirmar", follow_redirects=True)
        self.assertIn("confirmado:".encode(), response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(AgendamentoLaboratorio, primeiro_id).status, "agendado")
            self.assertEqual(HistoricoAgendamentoLaboratorio.query.filter_by(agendamento_id=primeiro_id).count(), 2)

        self.login(self.usuario_id)
        dados_excesso = dict(dados, data_reserva="2030-03-16", quantidade_alunos="11")
        response = self.client.post("/agenda/agendamentos/novo", data=dados_excesso, follow_redirects=True)
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
        self.assertEqual(self.client.post("/agenda/recados/novo", data=dados).status_code, 403)

        self.login(self.admin_id)
        self.assertEqual(self.client.post("/agenda/recados/novo", data=dados).status_code, 302)
        with self.app.app_context():
            self.assertEqual(Recado.query.count(), 1)

        self.login(self.usuario_id)
        response = self.client.get("/agenda/?data=2030-03-15")
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
            self.client.post(f"/agenda/agendamentos/{booking_id}/cancelar").status_code, 403
        )

        self.login(self.admin_id)
        self.assertEqual(
            self.client.post(f"/agenda/agendamentos/{booking_id}/cancelar").status_code, 302
        )
        with self.app.app_context():
            self.assertEqual(db.session.get(AgendamentoLaboratorio, booking_id).status, "cancelado")
            self.assertEqual(HistoricoAgendamentoLaboratorio.query.filter_by(agendamento_id=booking_id).count(), 1)

    def test_dashboard_e_agenda_renderizam(self):
        self.login(self.usuario_id)
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/agenda/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agenda e laboratórios".encode(), response.data)
        self.assertIn("Disponibilidade por turno".encode(), response.data)
        self.assertIn(b"Lab 05", response.data)
        self.assertEqual(self.client.get("/agendamento-laboratorios").status_code, 200)

        self.login(self.admin_id)
        response = self.client.get("/agenda/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Publicar novo recado".encode(), response.data)
        self.assertIn("Gerenciar laboratórios".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
