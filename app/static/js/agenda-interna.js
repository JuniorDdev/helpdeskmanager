(() => {
  const config = document.getElementById('agendaInternaConfiguracao');
  if (!config) return;
  const disponibilidade = JSON.parse(config.dataset.disponibilidade || '{}');
  const alunos = document.getElementById('reservaAlunos');
  const turno = document.getElementById('reservaTurno');
  const laboratorio = document.getElementById('reservaLaboratorio');
  const campoLaboratorio = document.getElementById('campoReservaLaboratorio');
  const ilhaCodigo = document.getElementById('reservaIlhaCodigo');
  const opcoesIlha = document.getElementById('opcoesIlhaInterna');
  const orientacao = document.getElementById('orientacaoReservaInterna');
  const data = document.getElementById('reservaData');
  if (!alunos || !turno || !laboratorio) return;

  function atualizar() {
    const quantidade = Number(alunos.value || 0);
    const atual = disponibilidade[turno.value] || { laboratorios_disponiveis: [], ilhas_disponiveis: {} };
    const requerIlha = quantidade >= 33 && quantidade <= 56;
    const prioridade = quantidade <= 24 ? ['Lab 06', 'Lab 07'] : ['Lab 05', 'Lab 08'];
    const livres = new Set(atual.laboratorios_disponiveis);
    [...laboratorio.options].forEach((opcao) => {
      const nome = opcao.textContent.trim().split(' ').slice(0, 2).join(' ');
      const permitido = !requerIlha && livres.has(Number(opcao.value)) && (
        quantidade === 0 || prioridade.includes(nome)
      );
      opcao.hidden = !permitido;
      opcao.disabled = !permitido;
    });
    const primeiro = [...laboratorio.options].find((opcao) => !opcao.disabled);
    campoLaboratorio.hidden = requerIlha;
    laboratorio.disabled = requerIlha || !primeiro;
    laboratorio.required = !requerIlha;
    if (!requerIlha && primeiro) laboratorio.value = primeiro.value;
    if (!requerIlha) ilhaCodigo.value = '';
    opcoesIlha.hidden = !requerIlha;
    if (requerIlha) {
      const opcoes = Object.entries(atual.ilhas_disponiveis).filter(([, livre]) => livre).map(([codigo]) => `<button type="button" class="btn btn-outline-primary me-2 mb-2" data-ilha-interna="${codigo}">${codigo === 'ilha-a' ? 'Ilha A — Labs 05 e 06' : 'Ilha B — Labs 07 e 08'}</button>`);
      opcoesIlha.innerHTML = opcoes.join('') || '<div class="alert alert-warning mb-0">Nenhuma ilha está disponível neste turno.</div>';
      orientacao.textContent = 'Turma grande: selecione uma ilha disponível.';
    } else if (quantidade > 0 && quantidade <= 24) orientacao.textContent = 'Sugestão: Lab 06 ou Lab 07 disponível neste turno.';
    else if (quantidade >= 25 && quantidade <= 32) orientacao.textContent = 'Sugestão: Lab 05 ou Lab 08 disponível neste turno.';
    else orientacao.textContent = quantidade > 56 ? 'A capacidade máxima por ilha é 56 alunos.' : 'Informe a quantidade para filtrar as opções.';
  }

  alunos.addEventListener('input', atualizar);
  turno.addEventListener('change', atualizar);
  data.addEventListener('change', () => { if (data.value) window.location = `${config.dataset.urlBase}?data=${data.value}`; });
  document.addEventListener('click', (evento) => {
    const escolha = evento.target.closest('[data-ilha-interna]');
    if (!escolha) return;
    ilhaCodigo.value = escolha.dataset.ilhaInterna;
    orientacao.textContent = `${escolha.textContent.trim()} selecionada para a reserva interna.`;
  });
  atualizar();
})();
