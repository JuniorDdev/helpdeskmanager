from datetime import datetime, timedelta


def calculate_sla(chamado, regras):
    regra = regras.get(chamado.prioridade)
    if not regra or not chamado.aberto_em:
        return None

    agora = datetime.now()
    prazo_resposta = chamado.aberto_em + timedelta(minutes=regra.tempo_resposta_minutos)
    prazo_resolucao = chamado.aberto_em + timedelta(minutes=regra.tempo_resolucao_minutos)
    resposta_referencia = chamado.iniciado_em or agora
    resolucao_referencia = chamado.finalizado_em or agora

    resposta_violada = resposta_referencia > prazo_resposta
    resolucao_violada = resolucao_referencia > prazo_resolucao
    if resposta_violada or resolucao_violada:
        return {"label": "SLA violado", "class": "danger", "deadline": prazo_resolucao}

    total = max(regra.tempo_resolucao_minutos * 60, 1)
    decorrido = max((agora - chamado.aberto_em).total_seconds(), 0)
    if chamado.status not in {"finalizado", "cancelado"} and decorrido / total >= 0.8:
        return {"label": "SLA em risco", "class": "warning", "deadline": prazo_resolucao}
    return {"label": "Dentro do SLA", "class": "success", "deadline": prazo_resolucao}
