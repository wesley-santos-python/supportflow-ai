/* Renderização dos gráficos do painel de análise (Chart.js) — paleta Floatech. */

// Lê os tokens da marca direto do CSS para acompanhar o tema (dark/light).
const css = getComputedStyle(document.documentElement);
const tok = (name, fallback) => css.getPropertyValue(name).trim() || fallback;

const ACCENT = tok("--accent", "#00E5C0");
const DANGER = tok("--danger", "#FF6B6B");
const WARN = tok("--warn", "#F5B544");
const INFO = tok("--info", "#5CC8FF");
const TEAL = "#00B8A9";

// Paleta geral (categorias) — família Floatech, sem azul corporativo.
const PALETTE = [ACCENT, TEAL, WARN, DANGER, INFO, "#AEF8EE"];

// Cores semânticas por rótulo: risco em urgência, progresso em status.
const URGENCY_COLORS = { Alta: DANGER, "Média": WARN, Media: WARN, Baixa: ACCENT };
const STATUS_COLORS = { Pendente: WARN, "Em Andamento": INFO, Resolvido: ACCENT };

Chart.defaults.color = tok("--muted", "#82858B");
Chart.defaults.borderColor = tok("--border", "#1F2024");
Chart.defaults.font.family = "Inter, sans-serif";

function toEntries(obj) {
  const labels = Object.keys(obj || {});
  const values = labels.map((k) => obj[k]);
  return { labels, values };
}

/** Resolve a cor de cada fatia: usa o mapa semântico quando houver, senão a paleta. */
function colorsFor(labels, map) {
  return labels.map((label, i) => (map && map[label]) || PALETTE[i % PALETTE.length]);
}

function doughnut(canvasId, dataObj, map) {
  const { labels, values } = toEntries(dataObj);
  new Chart(document.getElementById(canvasId), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colorsFor(labels, map), borderWidth: 0 }],
    },
    options: { plugins: { legend: { position: "bottom" } }, cutout: "62%" },
  });
}

function bars(canvasId, dataObj, map) {
  const { labels, values } = toEntries(dataObj);
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: colorsFor(labels, map), borderRadius: 6 }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

function line(canvasId, dataObj) {
  const { labels, values } = toEntries(dataObj);
  new Chart(document.getElementById(canvasId), {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: values, borderColor: ACCENT, backgroundColor: "rgba(0,229,192,.15)",
        fill: true, tension: 0.35, pointRadius: 3,
      }],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  doughnut("catChart", SUMMARY.by_category);
  doughnut("urgChart", SUMMARY.by_urgency, URGENCY_COLORS);
  bars("statusChart", SUMMARY.by_status, STATUS_COLORS);
  line("dayChart", SUMMARY.by_day);
});
