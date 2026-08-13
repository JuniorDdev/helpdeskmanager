from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.Enum("admin", "tecnico", "usuario", "almoxarife"), nullable=False, default="usuario")
    setor = db.Column(db.String(100))
    telefone = db.Column(db.String(30))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def is_admin(self):
        return self.perfil == "admin"
