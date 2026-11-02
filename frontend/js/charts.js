/*
 * Chart.js helpers with one consistent style:
 * single blue series, hairline solid gridlines, 4px rounded bar ends,
 * 2px lines, hover tooltips. Each chart shows one measure, so no legend box.
 */
const Charts = (() => {
  const SERIES = "#2a78d6";
  const SERIES_FILL = "rgba(42, 120, 214, 0.10)";
  const GRID = "#e8edf3";
  const AXIS_TEXT = "#64748b";
  const instances = {};

  if (window.Chart) {
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = AXIS_TEXT;
    Chart.defaults.plugins.legend.display = false;
    Object.assign(Chart.defaults.plugins.tooltip, {
      backgroundColor: "#0f172a", padding: 10, cornerRadius: 8,
      titleFont: { weight: "600" }, displayColors: false,
    });
  }

  function render(id, config) {
    if (instances[id]) instances[id].destroy();
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    instances[id] = new Chart(canvas, config);
    return instances[id];
  }

  function grid() {
    return { color: GRID, lineWidth: 1, drawTicks: false };
  }

  /** Bar chart. opts: { horizontal, max, stepSize, tooltip(value) } */
  function bar(id, labels, values, opts = {}) {
    const valueAxis = {
      beginAtZero: true, grid: grid(), border: { display: false },
      ticks: { precision: 0, padding: 8, stepSize: opts.stepSize },
      max: opts.max,
    };
    const categoryAxis = { grid: { display: false }, border: { color: GRID }, ticks: { padding: 6 } };
    return render(id, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          data: values, backgroundColor: SERIES, hoverBackgroundColor: "#1d4ed8",
          borderRadius: 4, borderSkipped: "start", maxBarThickness: 34, categoryPercentage: 0.7,
        }],
      },
      options: {
        indexAxis: opts.horizontal ? "y" : "x",
        maintainAspectRatio: false,
        animation: opts.animation === false ? false : undefined,
        scales: opts.horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => opts.tooltip ? opts.tooltip(ctx.raw) : String(ctx.raw),
            },
          },
        },
      },
    });
  }

  /** Line chart for a time series (one value per day). */
  function line(id, labels, values, opts = {}) {
    return render(id, {
      type: "line",
      data: {
        labels,
        datasets: [{
          data: values, borderColor: SERIES, backgroundColor: SERIES_FILL, fill: true,
          // "monotone" keeps the smoothed curve from dipping below 0 between days
          borderWidth: 2, cubicInterpolationMode: "monotone", pointRadius: values.length <= 14 ? 3 : 0,
          pointHoverRadius: 5, pointBackgroundColor: SERIES, pointBorderColor: "#fff", pointBorderWidth: 2,
        }],
      },
      options: {
        maintainAspectRatio: false,
        animation: opts.animation === false ? false : undefined,
        interaction: { mode: "index", intersect: false },   // hover anywhere above a day
        scales: {
          x: { grid: { display: false }, border: { color: GRID }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
          y: { beginAtZero: true, grid: grid(), border: { display: false }, ticks: { precision: 0, padding: 8 } },
        },
        plugins: {
          tooltip: { callbacks: { label: (ctx) => `${ctx.raw} submission${ctx.raw === 1 ? "" : "s"}` } },
        },
      },
    });
  }

  /** Short category names so axis labels fit on small screens. */
  function shortCategory(c) {
    return ({
      "Faculty and Teaching": "Faculty",
      "Events and Workshops": "Events",
      "Overall College Experience": "Overall",
    })[c] || c;
  }

  function dayLabel(iso) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }

  /** Plain HTML table version of a chart (accessibility / exact numbers). */
  function table(containerId, headers, rows) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<table class="table table-sm mb-0"><thead><tr>${headers.map((h) => `<th>${UI.esc(h)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${UI.esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  return { bar, line, table, shortCategory, dayLabel };
})();
