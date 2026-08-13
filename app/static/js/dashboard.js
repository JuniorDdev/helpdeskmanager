async function carregarDashboard() {
  try {
    const resposta = await fetch('/api/dashboard', { headers: { Accept: 'application/json' } });
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    const dados = await resposta.json();

    criarGrafico('graficoStatus', dados.chamados_status, ['#4468f2', '#17b6a3', '#f59e0b', '#e05263', '#8290a9']);
    criarGrafico('graficoCategoria', dados.chamados_categoria, ['#17b6a3', '#4468f2', '#f59e0b', '#e05263', '#7b61ff']);
    criarGrafico('graficoMaquinas', dados.maquinas_status, ['#4468f2', '#f59e0b', '#17b6a3', '#e05263']);
  } catch (error) {
    document.querySelectorAll('.chart-card').forEach((card) => {
      card.classList.add('is-unavailable');
      const message = document.createElement('p');
      message.className = 'chart-empty';
      message.textContent = 'Não foi possível carregar os dados agora.';
      card.appendChild(message);
    });
  }
}

function criarGrafico(canvasId, objeto, colors) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  new Chart(el, {
    type: 'doughnut',
    data: {
      labels: Object.keys(objeto),
      datasets: [{ data: Object.values(objeto), backgroundColor: colors, borderWidth: 0, hoverOffset: 5 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, padding: 16, font: { size: 11 } } }
      }
    }
  });
}

document.addEventListener('DOMContentLoaded', carregarDashboard);
