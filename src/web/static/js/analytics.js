/* Renderização dos gráficos do painel de análise (Chart.js). */

const PALETTE = ["#15c8d4", "#3b82f6", "#f59e0b", "#ef4444", "#22c55e", "#a855f7"];

Chart.defaults.color = "#8a98ad";
Chart.defaults.borderColor = "#243044";
Chart.defaults.font.family = "Inter, sans-serif";

function toEntries(obj) {
  const labels = Object.keys(obj || {});
  const values = labels.map((k) => obj[k]);
  return { labels, values };
}

function doughnut(canvasId, dataObj) {
  const { labels, values } = toEntries(dataObj);
  new Chart(document.getElementById(canvasId), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: PALETTE, borderWidth: 0 }],
    },
    options: { plugins: { legend: { position: "bottom" } }, cutout: "62%" },
  });
}

function bars(canvasId, dataObj, color) {
  const { labels, values } = toEntries(dataObj);
  new Chart(document.getElementById(canvasId), {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: color, borderRadius: 6 }] },
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
        data: values, borderColor: "#15c8d4", backgroundColor: "rgba(21,200,212,.15)",
        fill: true, tension: 0.35, pointRadius: 3,
      }],
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  doughnut("catChart", SUMMARY.by_category);
  doughnut("urgChart", SUMMARY.by_urgency);
  bars("statusChart", SUMMARY.by_status, "#3b82f6");
  line("dayChart", SUMMARY.by_day);
});
