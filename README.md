# Helpdesk Manager

Sistema web em Flask para chamados de suporte, patrimonio de maquinas, movimentacao de equipamentos, estoque de TI, manutencoes e conferencias.

## Tecnologias

- Python 3.11+
- Flask, Flask-SQLAlchemy, Flask-Login
- Flask-WTF (CSRF), Flask-Limiter (login), Flask-Migrate
- MySQL com PyMySQL
- Bootstrap e Chart.js
- Exportacao Excel e PDF

## Execucao no Windows

1. Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependencias:

```powershell
python -m pip install -r requirements.txt
```

3. Crie o banco no MySQL:

```powershell
mysql -u root -p < create_database.sql
```

4. Copie `.env.example` para `.env` e preencha uma `SECRET_KEY`, a senha do MySQL e uma `ADMIN_PASSWORD` com pelo menos 10 caracteres. O sistema nao inicia sem `SECRET_KEY`.

5. Inicialize tabelas e dados basicos:

```powershell
python init_db.py
```

O comando cria o administrador indicado por `ADMIN_EMAIL` e gera uma senha aleatoria quando `ADMIN_PASSWORD` nao for informada. Guarde a senha exibida no terminal.

6. Inicie o servidor:

```powershell
python app.py
```

Acesse `http://127.0.0.1:5000`.

## Exposicao temporaria com ngrok

Mantenha o Flask em um terminal e, em outro, aponte o ngrok explicitamente para IPv4:

```powershell
ngrok http 127.0.0.1:5000
```

Evite `ngrok http 5000` neste ambiente, pois `localhost` pode ser resolvido como `::1` e nao encontrar o servidor IPv4.

## Perfis

- `admin`: administracao de usuarios, patrimonio e estoque.
- `tecnico`: chamados, maquinas, movimentacoes, manutencoes e leitura do estoque.
- `almoxarife`: leitura e movimentacao do estoque.
- `usuario`: abertura e acompanhamento dos proprios chamados.

Chamados, estoque, maquinas e conferencias sao filtrados conforme o perfil. Operacoes de escrita exigem protecao CSRF e validacao no servidor.

## Banco e migracoes

O banco padrao e `helpdesk_manager`. Para ambientes existentes, use Flask-Migrate depois de instalar as dependencias:

```powershell
flask --app app.py db init
flask --app app.py db migrate -m "estrutura inicial"
flask --app app.py db upgrade
```

Nao inclua `.env`, `.venv`, uploads, backups ou dados exportados no controle de versao.

## Producao

Use um servidor WSGI, HTTPS, `SESSION_COOKIE_SECURE=1` e um armazenamento compartilhado para o rate limit, como Redis (`RATELIMIT_STORAGE_URI`). Mantenha `FLASK_DEBUG=0`.
