async function carregarDashboard() {
  const resposta = await fetch('/api/dashboard');
  const dados = await resposta.json();

  criarGrafico('graficoStatus', 'Chamados por Status', dados.chamados_status);
  criarGrafico('graficoCategoria', 'Chamados por Categoria', dados.chamados_categoria);
  criarGrafico('graficoMaquinas', 'Máquinas por Status', dados.maquinas_status);
}

function criarGrafico(canvasId, titulo, objeto) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  new Chart(el, {
    type: 'bar',
    data: {
      labels: Object.keys(objeto),
      datasets: [{ label: titulo, data: Object.values(objeto) }]
    },
    options: { responsive: true, plugins: { legend: { display: false } } }
  });
}

document.addEventListener('DOMContentLoaded', carregarDashboard);
