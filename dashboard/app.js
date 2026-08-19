const emptyMetrics = { total: 0, wins: 0, losses: 0, ties: 0, winRate: 0, lossRate: 0, winStreak: 0, lossStreak: 0 };

function render(data = { metrics: emptyMetrics, trades: [] }) {
  const metrics = data.metrics || emptyMetrics;
  const values = {
    total: metrics.total ?? 0,
    wins: metrics.wins ?? 0,
    losses: metrics.losses ?? 0,
    ties: metrics.ties ?? 0,
    winRate: `${Number(metrics.winRate ?? 0).toFixed(2)}%`,
    lossRate: `${Number(metrics.lossRate ?? 0).toFixed(2)}%`,
    winStreak: metrics.winStreak ?? 0,
    lossStreak: metrics.lossStreak ?? 0,
  };
  for (const [id, value] of Object.entries(values)) document.getElementById(id).textContent = value;

  const rows = (data.trades || []).slice(-50).reverse();
  const tbody = document.getElementById('results');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="muted">No backtest data loaded yet.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((trade) => `
    <tr>
      <td>${escapeHtml(trade.time ?? '')}</td>
      <td>${escapeHtml(trade.pair ?? '')}</td>
      <td>${escapeHtml(trade.direction ?? '')}</td>
      <td>${escapeHtml(trade.expiry ?? '')}</td>
      <td>${escapeHtml(trade.confidence ?? '')}</td>
      <td>${escapeHtml(trade.outcome ?? '')}</td>
    </tr>`).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

async function loadResults() {
  try {
    const response = await fetch('../data/backtest.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    console.warn('Backtest JSON is not available yet:', error.message);
    render();
  }
}

document.getElementById('refresh').addEventListener('click', loadResults);
loadResults();
