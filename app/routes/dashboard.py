from datetime import date, datetime, time, timedelta

from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required
from sqlalchemy import case, func

from app.models import AgendamentoLaboratorio, Chamado, Estoque, Manutencao, Maquina, Recado
from app.utils.authz import SUPPORT_ROLES


dashboard_bp = Blueprint("dashboard", __name__)


def visible_queries():
    if current_user.perfil in SUPPORT_ROLES:
        chamados = Chamado.query
        maquinas = Maquina.query
        manutencoes = Manutencao.query
    else:
        chamados = Chamado.query.filter_by(usuario_id=current_user.id)
        maquinas = Maquina.query.filter_by(usuario_responsavel_id=current_user.id)
        manutencoes = Manutencao.query.filter(Manutencao.id.is_(None))

    if current_user.perfil in {"admin", "tecnico", "almoxarife"}:
        estoque = Estoque.query
    else:
        estoque = Estoque.query.filter(Estoque.id.is_(None))
    return chamados, maquinas, estoque, manutencoes


@dashboard_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("landing/index.html")

    chamados, maquinas_query, estoque_query, manutencoes_query = visible_queries()
    total_chamados = chamados.count()
    abertos = chamados.filter(Chamado.status.in_(["aberto", "em_andamento", "aguardando_peca"])).count()
    maquinas = maquinas_query.count()
    estoque_baixo = estoque_query.filter(Estoque.quantidade <= Estoque.estoque_minimo).count()
    manutencoes = manutencoes_query.count()
    hoje = date.today()
    inicio_dia = datetime.combine(hoje, time.min)
    fim_dia = inicio_dia + timedelta(days=1)
    agenda_hoje = (
        AgendamentoLaboratorio.query.filter(
            AgendamentoLaboratorio.status == "agendado",
            AgendamentoLaboratorio.inicio < fim_dia,
            AgendamentoLaboratorio.fim > inicio_dia,
        )
        .order_by(AgendamentoLaboratorio.inicio)
        .limit(5)
        .all()
    )
    recados_hoje = (
        Recado.query.filter(Recado.data_inicio <= hoje, Recado.data_fim >= hoje)
        .order_by(
            case(
                (Recado.prioridade == "urgente", 0),
                (Recado.prioridade == "importante", 1),
                else_=2,
            ),
            Recado.criado_em.desc(),
        )
        .limit(3)
        .all()
    )
    return render_template(
        "dashboard/index.html",
        total_chamados=total_chamados,
        abertos=abertos,
        maquinas=maquinas,
        estoque_baixo=estoque_baixo,
        manutencoes=manutencoes,
        agenda_hoje=agenda_hoje,
        recados_hoje=recados_hoje,
    )


@dashboard_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    chamados, maquinas, _estoque, _manutencoes = visible_queries()
    chamados_status = dict(
        chamados.with_entities(Chamado.status, func.count(Chamado.id)).group_by(Chamado.status).all()
    )
    chamados_categoria = dict(
        chamados.with_entities(Chamado.categoria, func.count(Chamado.id)).group_by(Chamado.categoria).all()
    )
    maquinas_status = dict(
        maquinas.with_entities(Maquina.status, func.count(Maquina.id)).group_by(Maquina.status).all()
    )
    return jsonify(
        chamados_status=chamados_status,
        chamados_categoria=chamados_categoria,
        maquinas_status=maquinas_status,
    )
