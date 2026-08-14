import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from app import create_app
from app.extensions import db
from app.models import AgendamentoLaboratorio, Laboratorio, Usuario
from app.services.agenda_excel import import_agenda_workbook, read_agenda_workbook


class AgendaExcelImportTestCase(unittest.TestCase):
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
        self.temp_directory = tempfile.TemporaryDirectory()
        self.workbook_path = Path(self.temp_directory.name) / "mapa.xlsx"
        self._create_workbook()

        with self.app.app_context():
            db.create_all()
            admin = Usuario(
                nome="Admin Importação",
                email="admin@teste.local",
                senha_hash="inutilizado",
                perfil="admin",
                ativo=True,
            )
            labs = [Laboratorio(nome=f"Lab {number:02d}", ativo=True) for number in range(1, 6)]
            db.session.add_all([admin, *labs])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.temp_directory.cleanup()

    def _create_workbook(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Janeiro"
        sheet.append(["Mapa de Agendamento de Laboratório de Informática"])
        sheet.append([])
        sheet.append([])
        sheet.append(["Dia", "Data", "Turno", "Lab 01", "Lab 02", "Lab 03", "Lab 04", "Lab 05"])
        sheet.append(["Segunda-feira", date(2026, 1, 5), "Manhã", "Aula de Redes", None, None, None, "FERIADO"])
        sheet.append([None, None, "Tarde", None, "Treinamento", "/", 0, None])
        sheet.append([None, None, "Noite", None, None, None, None, None])
        workbook.save(self.workbook_path)
        workbook.close()

    def test_le_planilha_com_data_mesclada_por_turno(self):
        data = read_agenda_workbook(self.workbook_path)

        self.assertEqual(len(data.registros), 3)
        self.assertEqual(data.placeholders_ignorados, 2)
        self.assertTrue(all(entry.data == date(2026, 1, 5) for entry in data.registros))
        self.assertEqual(
            {(entry.turno, entry.laboratorio_nome, entry.texto) for entry in data.registros},
            {
                ("manha", "Lab 01", "Aula de Redes"),
                ("manha", "Lab 05", "FERIADO"),
                ("tarde", "Lab 02", "Treinamento"),
            },
        )

    def test_importacao_e_idempotente_e_respeita_horarios(self):
        with self.app.app_context():
            first = import_agenda_workbook(
                self.workbook_path,
                user_email="admin@teste.local",
                commit=True,
            )
            self.assertEqual(first.importados, 3)
            self.assertEqual(AgendamentoLaboratorio.query.count(), 3)

            morning = AgendamentoLaboratorio.query.filter_by(titulo="Aula de Redes").one()
            afternoon = AgendamentoLaboratorio.query.filter_by(titulo="Treinamento").one()
            self.assertEqual(morning.inicio, datetime(2026, 1, 5, 8, 0))
            self.assertEqual(morning.fim, datetime(2026, 1, 5, 12, 0))
            self.assertEqual(afternoon.inicio, datetime(2026, 1, 5, 13, 0))
            self.assertEqual(afternoon.fim, datetime(2026, 1, 5, 17, 0))

            second = import_agenda_workbook(
                self.workbook_path,
                user_email="admin@teste.local",
                commit=True,
            )
            self.assertEqual(second.importados, 0)
            self.assertEqual(second.conflitos, 3)
            self.assertEqual(AgendamentoLaboratorio.query.count(), 3)


if __name__ == "__main__":
    unittest.main()
