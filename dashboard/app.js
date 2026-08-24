const emptyMetrics = { total: 0, wins: 0, losses: 0, ties: 0, winRate: 0, lossRate: 0, winStreak: 0, lossStreak: 0 };

const emptyLive = {
  status: 'WAITING',
  serverTime: null,
  mt5Status: 'OFFLINE',
  lastTick: null,
  nextCandle: null,
  feedAgeSeconds: null,
  signal: null,
  candles: {}
};

function text(id, value = '—') {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}

function renderMetrics(metrics = emptyMetrics) {
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
  Object.entries(values).forEach(([id, value]) => text(id, value));
}

function renderTrades(trades = []) {
  const rows = trades.slice(-50).reverse();
  const tbody = document.getElementById('results');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="muted">No signal data loaded yet.</td></tr>';
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

function renderSignal(signal) {
  if (!signal) {
    text('signalState', 'WAITING');
    text('signalDirection', '—');
    text('signalTarget', '—');
    text('signalPredictionConfidence', '—');
    text('signalActionableConfidence', '—');
    text('signalExpiry', '—');
    text('sourceCandle', '—');
    text('signalNote', 'A prediction will appear only after the target candle is confirmed closed.');
    return;
  }
  text('signalState', signal.direction && signal.direction !== 'NONE' ? 'READY' : 'WAITING');
  text('signalDirection', signal.direction ?? '—');
  text('signalTarget', signal.target_timeframe ? `Next ${signal.target_timeframe}` : 'Next M1');
  text('signalPredictionConfidence', signal.prediction_confidence == null ? '—' : `${Number(signal.prediction_confidence).toFixed(1)}%`);
  text('signalActionableConfidence', signal.actionable_confidence == null ? '—' : `${Number(signal.actionable_confidence).toFixed(1)}%`);
  text('signalExpiry', signal.expiry_minutes == null ? '—' : `${signal.expiry_minutes} min`);
  text('sourceCandle', signal.source_candle_time ?? '—');
  text('signalNote', signal.note ?? 'Prediction is based on confirmed M1/M5/M15 candle data.');
}

function renderTimeframe(tf, candle = {}) {
  const prefix = tf.toLowerCase();
  text(`${prefix}State`, candle.state ?? 'WAITING');
  text(`${prefix}Price`, candle.price ?? '—');
  text(`${prefix}Close`, candle.close ?? '—');
  text(`${prefix}Direction`, candle.direction ?? '—');
  text(`${prefix}Time`, candle.closed_at ?? '—');
}

function renderLive(live = emptyLive) {
  text('overallStatusText', live.status ?? 'WAITING');
  text('serverClock', live.serverTime ?? '—');
  text('mt5Status', live.mt5Status ?? 'OFFLINE');
  text('lastTick', live.lastTick ?? '—');
  text('nextCandle', live.nextCandle ?? '—');
  text('feedAge', live.feedAgeSeconds == null ? '—' : `${live.feedAgeSeconds}s`);
  renderSignal(live.signal);
  renderTimeframe('M1', live.candles?.M1);
  renderTimeframe('M5', live.candles?.M5);
  renderTimeframe('M15', live.candles?.M15);
}

async function loadResults() {
  const pair = document.getElementById('pair').value;
  const timeframe = document.getElementById('timeframe').value;
  try {
    const response = await fetch(`../data/backtest.json?pair=${encodeURIComponent(pair)}&timeframe=${timeframe}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderMetrics(data.metrics || emptyMetrics);
    renderTrades(data.trades || []);
    text('lastUpdated', `Updated ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    console.warn('Backtest JSON is not available yet:', error.message);
    renderMetrics();
    renderTrades();
    text('lastUpdated', 'Waiting for data');
  }

  try {
    const liveResponse = await fetch(`../data/live.json?pair=${encodeURIComponent(pair)}&timeframe=${timeframe}`, { cache: 'no-store' });
    if (!liveResponse.ok) throw new Error(`HTTP ${liveResponse.status}`);
    renderLive(await liveResponse.json());
  } catch (error) {
    renderLive();
  }
}

document.getElementById('refresh').addEventListener('click', loadResults);
document.getElementById('pair').addEventListener('change', loadResults);
document.getElementById('timeframe').addEventListener('change', loadResults);
loadResults();
setInterval(loadResults, 5000);
