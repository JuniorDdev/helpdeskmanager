(() => {
  const configElement = document.getElementById('agendaConfiguracao');
  if (!configElement) return;

  const disponibilidade = JSON.parse(configElement.dataset.disponibilidade || '{}');
  const alunos = document.getElementById('alunos');
  const turno = document.getElementById('turno');
  const laboratorio = document.getElementById('laboratorio');
  const ilhaCodigo = document.getElementById('ilhaCodigo');
  const orientacao = document.getElementById('orientacaoCapacidade');
  const sugestao = document.getElementById('opcaoSugerida');
  const campoLaboratorio = laboratorio.closest('.col-12');
  const resumoIlha = document.createElement('div');
  resumoIlha.className = 'col-12';
  resumoIlha.hidden = true;
  campoLaboratorio.parentNode.insertBefore(resumoIlha, campoLaboratorio);
  const software = document.getElementById('precisaSoftware');
  const softwareField = document.getElementById('campoSoftwares');
  const softwareText = document.getElementById('softwares');

  software?.addEventListener('change', () => {
    softwareField.classList.toggle('d-none', !software.checked);
    softwareText.required = software.checked;
  });

  function atualizarOpcoes() {
    const quantidade = Number(alunos.value || 0);
    const atual = disponibilidade[turno.value] || { laboratorios_disponiveis: [], ilhas_disponiveis: {} };
    const requerIlha = quantidade >= 33 && quantidade <= 56;
    const ilhaSelecionada = requerIlha && Boolean(ilhaCodigo.value);
    let nomes = [];
    let texto = 'Informe a quantidade para ver as opções.';
    if (quantidade > 0 && quantidade <= 24) {
      nomes = ['Lab 06', 'Lab 07'];
      texto = 'Sugestão: escolha Lab 06 ou Lab 07 disponível neste turno.';
    } else if (quantidade >= 25 && quantidade <= 32) {
      nomes = ['Lab 05', 'Lab 08'];
      texto = 'Sugestão: escolha Lab 05 ou Lab 08 disponível neste turno.';
    } else if (requerIlha) {
      texto = 'Turma grande: selecione uma ilha disponível abaixo.';
    } else if (quantidade > 56) {
      texto = 'A capacidade máxima das ilhas é de 56 alunos.';
    }

    const livres = new Set(atual.laboratorios_disponiveis);
    [...laboratorio.options].forEach((opcao) => {
      const permitida = !requerIlha && nomes.includes(opcao.dataset.nome) && livres.has(Number(opcao.value));
      opcao.hidden = !permitida;
      opcao.disabled = !permitida;
    });
    const primeira = [...laboratorio.options].find((opcao) => !opcao.disabled);
    laboratorio.disabled = requerIlha || !primeira;
    laboratorio.required = !requerIlha;
    campoLaboratorio.hidden = requerIlha;
    if (!requerIlha && primeira) laboratorio.value = primeira.value;
    if (!requerIlha) ilhaCodigo.value = '';

    document.querySelectorAll('[data-ilhas-turno]').forEach((item) => {
      item.classList.toggle('is-active', requerIlha && item.dataset.ilhasTurno === turno.value);
    });
    sugestao.hidden = !requerIlha;
    if (requerIlha) {
      const botoes = Object.entries(atual.ilhas_disponiveis)
        .filter(([, livre]) => livre)
        .map(([codigo]) => `<button type="button" class="btn btn-outline-primary me-2 mb-2" data-ilha-form="${codigo}">${codigo === 'ilha-a' ? 'Ilha A — Labs 05 e 06' : 'Ilha B — Labs 07 e 08'}</button>`);
      sugestao.innerHTML = botoes.join('') || '<div class="alert alert-warning mb-0">Nenhuma ilha está disponível neste turno.</div>';
    } else {
      sugestao.innerHTML = '';
    }
    resumoIlha.hidden = !ilhaSelecionada;
    if (ilhaSelecionada) {
      const nomeIlha = ilhaCodigo.value === 'ilha-a' ? 'Ilha A' : 'Ilha B';
      const labs = ilhaCodigo.value === 'ilha-a' ? 'Labs 05 e 06' : 'Labs 07 e 08';
      resumoIlha.innerHTML = `<div class="alert alert-primary mb-0"><strong>Reserva selecionada: ${nomeIlha} — ${labs}</strong><br><span>Os dois laboratórios serão solicitados juntos, com capacidade para até 56 alunos.</span><div class="mt-2"><button type="button" class="btn btn-sm btn-outline-primary" data-alterar-ilha>Alterar ilha</button></div></div>`;
    } else {
      resumoIlha.innerHTML = '';
    }
    orientacao.textContent = texto;
  }

  function escolherIlha(codigo) {
    ilhaCodigo.value = codigo;
    atualizarOpcoes();
    orientacao.textContent = `${codigo === 'ilha-a' ? 'Ilha A (Labs 05 e 06)' : 'Ilha B (Labs 07 e 08)'} selecionada.`;
    document.getElementById('formulario-agendamento').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  alunos.addEventListener('input', atualizarOpcoes);
  turno.addEventListener('change', atualizarOpcoes);
  document.getElementById('data').addEventListener('change', (evento) => {
    if (evento.target.value) window.location = `${configElement.dataset.urlBase}?data=${evento.target.value}`;
  });
  document.addEventListener('click', (evento) => {
    if (evento.target.closest('[data-alterar-ilha]')) {
      ilhaCodigo.value = '';
      atualizarOpcoes();
      sugestao.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    const escolha = evento.target.closest('[data-ilha-choice],[data-ilha-form]');
    if (!escolha) return;
    const quantidade = Number(alunos.value || 0);
    if (quantidade < 33 || quantidade > 56) {
      orientacao.textContent = 'Informe entre 33 e 56 alunos para selecionar uma ilha.';
      alunos.focus();
      return;
    }
    if (escolha.dataset.turno) turno.value = escolha.dataset.turno;
    escolherIlha(escolha.dataset.ilhaChoice || escolha.dataset.ilhaForm);
  });
  document.querySelectorAll('[data-lab-choice]').forEach((botao) => {
    botao.addEventListener('click', () => {
      turno.value = botao.dataset.turno;
      atualizarOpcoes();
      laboratorio.value = botao.dataset.labChoice;
      document.getElementById('formulario-agendamento').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
  atualizarOpcoes();
})();
