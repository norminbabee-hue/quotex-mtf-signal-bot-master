const demo = { total: 0, wins: 0, losses: 0, ties: 0, winRate: 0, lossRate: 0, winStreak: 0, lossStreak: 0 };

function render(metrics = demo) {
  const values = {
    total: metrics.total,
    wins: metrics.wins,
    losses: metrics.losses,
    ties: metrics.ties,
    winRate: `${Number(metrics.winRate).toFixed(2)}%`,
    lossRate: `${Number(metrics.lossRate).toFixed(2)}%`,
    winStreak: metrics.winStreak,
    lossStreak: metrics.lossStreak,
  };
  for (const [id, value] of Object.entries(values)) document.getElementById(id).textContent = value;
}

document.getElementById('refresh').addEventListener('click', () => {
  // The Python backtest runner will supply real JSON later. Keep the UI deterministic until then.
  render(demo);
});

render();
