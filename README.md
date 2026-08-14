# Helpdesk Manager

Sistema web em Flask para chamados de suporte, patrimonio de maquinas, movimentacao de equipamentos, estoque de TI, manutencoes, conferencias e agenda de laboratorios com mural de recados.

## Autoria e licença

Desenvolvido por **Domingos Junior (JuniorDdev)**.

Copyright © 2026 Domingos Junior. Todos os direitos reservados. Este projeto
está sob licença proprietária. A visualização e os forks realizados pelas
funcionalidades do GitHub são permitidos, mas cópia, modificação, distribuição,
uso comercial ou criação de obras derivadas exigem autorização prévia e por
escrito do titular. Consulte o arquivo [LICENSE](LICENSE) para os termos
completos.

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

Em uma instalacao existente, execute novamente `python init_db.py` depois de atualizar o codigo. O comando cria as tabelas da agenda sem apagar os dados atuais e garante os laboratorios `Lab 01` a `Lab 05`.

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

Todos os perfis podem consultar o mapa diario, reservar um dos cinco laboratorios por manha, tarde ou noite e administrar as proprias reservas. Administradores e tecnicos podem administrar todas as reservas, cadastrar laboratorios e publicar ou excluir recados.

## Importar o mapa de agendamentos do Excel

O importador reconhece as abas mensais com as colunas `Data`, `Turno` e `Lab 01` a `Lab 05`. Ele usa as datas reais armazenadas nas células, associa Manhã a 08:00–12:00, Tarde a 13:00–17:00 e Noite a 18:00–22:00, e ignora automaticamente reservas que conflitem com dados já cadastrados.

Primeiro, faça uma simulação sem alterar o banco:

```powershell
python -m flask --app app.py importar-agenda-excel "C:\caminho\Mapa de Agendamento_2025.xlsx"
```

Depois de conferir os totais, grave os dados:

```powershell
python -m flask --app app.py importar-agenda-excel "C:\caminho\Mapa de Agendamento_2025.xlsx" --confirmar
```

Por padrão, o primeiro administrador ou técnico ativo fica como responsável pelas reservas importadas. Para escolher uma conta, acrescente `--usuario email@exemplo.com`. A carga pode ser executada novamente: registros já existentes são tratados como conflitos e não são duplicados.

Chamados, estoque, maquinas e conferencias sao filtrados conforme o perfil. Operacoes de escrita exigem protecao CSRF e validacao no servidor.

## Banco e migracoes

O banco padrao e `helpdesk_manager`. Para ambientes existentes, use Flask-Migrate depois de instalar as dependencias:

```powershell
flask --app app.py db init
flask --app app.py db migrate -m "estrutura inicial"
flask --app app.py db upgrade
```

Nao inclua `.env`, `.venv`, uploads, backups ou dados exportados no controle de versao.

## Deploy no Railway

O repositorio inclui `wsgi.py` e `Procfile` para iniciar o Flask com Gunicorn.
Depois de conectar o repositorio ao Railway:

1. Adicione um servico MySQL ao projeto.
2. No servico web, crie `SECRET_KEY`, `ADMIN_EMAIL` e `ADMIN_PASSWORD` como variaveis privadas.
3. Crie `DATABASE_URL` como referencia para `MYSQL_URL` do servico MySQL:
   `${{MySQL.MYSQL_URL}}` (use o nome exato do seu servico).
4. Mantenha `FLASK_DEBUG=0` e `SESSION_COOKIE_SECURE=1`.
5. Se o Railway nao detectar o `Procfile`, defina o Start Command como:

```text
gunicorn wsgi:application --bind 0.0.0.0:$PORT
```

Depois do primeiro deploy, abra o Console do servico web e execute uma vez:

```bash
python init_db.py
```

O Railway injeta `PORT` automaticamente; nao fixe a porta 5000 no ambiente de producao.

## Producao

Use um servidor WSGI, HTTPS, `SESSION_COOKIE_SECURE=1` e um armazenamento compartilhado para o rate limit, como Redis (`RATELIMIT_STORAGE_URI`). Mantenha `FLASK_DEBUG=0`.
