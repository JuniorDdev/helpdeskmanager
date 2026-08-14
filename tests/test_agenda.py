import unittest
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import AgendamentoLaboratorio, Laboratorio, Recado, Usuario


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

    def test_bloqueia_mesmo_turno_e_aceita_turno_diferente(self):
        self.login(self.usuario_id)
        primeira = {
            "titulo": "Aula 8A",
            "laboratorio_id": self.laboratorio_id,
            "data_reserva": "2030-03-15",
            "turno": "manha",
            "data_retorno": "2030-03-15",
        }
        response = self.client.post("/agenda/agendamentos/novo", data=primeira)
        self.assertEqual(response.status_code, 302)

        conflito = dict(primeira, titulo="Aula 9B")
        response = self.client.post(
            "/agenda/agendamentos/novo", data=conflito, follow_redirects=True
        )
        self.assertIn("já está reservado no turno selecionado".encode(), response.data)

        outro_turno = dict(primeira, titulo="Aula 9C", turno="tarde")
        self.client.post("/agenda/agendamentos/novo", data=outro_turno)
        with self.app.app_context():
            self.assertEqual(AgendamentoLaboratorio.query.count(), 2)
            primeira_reserva = AgendamentoLaboratorio.query.order_by(AgendamentoLaboratorio.id).first()
            self.assertEqual(primeira_reserva.inicio, datetime(2030, 3, 15, 8, 0))
            self.assertEqual(primeira_reserva.fim, datetime(2030, 3, 15, 12, 0))

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

    def test_dashboard_e_agenda_renderizam(self):
        self.login(self.usuario_id)
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/agenda/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agenda e laboratórios".encode(), response.data)
        self.assertIn("Disponibilidade por turno".encode(), response.data)
        self.assertIn(b"Lab 05", response.data)

        self.login(self.admin_id)
        response = self.client.get("/agenda/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Publicar novo recado".encode(), response.data)
        self.assertIn("Gerenciar laboratórios".encode(), response.data)


if __name__ == "__main__":
    unittest.main()
