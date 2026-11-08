/* MIRA deck runtime: backgrounds, footers, motif, charts, reveal.js init. */
(() => {
  const C = {
    ink: "#0B1F33", muted: "#64748B", line: "#E2E8F0", teal: "#0D9488", teal300: "#5EEAD4", teal50: "#F0FDFA",
    coral: "#EF6351", coral50: "#FEF2F1", amber: "#F59E0B", amber50: "#FFFBEB", azure: "#0078D4", slate: "#94A3B8",
  };
  const STAGES = ["Why", "MI", "Measure", "MIRA", "Agents", "Demo", "Proof", "Cost", "Impact", "Next"];
  const slides = [...document.querySelectorAll(".reveal .slides > section")];

  // ---------- backgrounds + footer (brand · progress strip · slide number) ----------
  slides.forEach((s, i) => {
    if (s.dataset.bg === "dark") s.setAttribute("data-background-gradient", "linear-gradient(135deg, #061423 0%, #0E2A44 100%)");
    else s.setAttribute("data-background-color", "#F8FAFC");
    if (s.id === "s1" || s.id === "s25") return;
    const now = STAGES.indexOf(s.dataset.progress);
    const strip = now < 0 ? "" : STAGES.map((n, k) => `<span class="${k < now ? "done" : k === now ? "now" : ""}">${n}</span>`).join("");
    const footer = document.createElement("div");
    footer.className = "deck-footer";
    footer.innerHTML = `<span class="brand">MIRA</span><span class="strip">${strip}</span><span class="num">${i + 1} / ${slides.length}</span>`;
    s.querySelector(".frame").appendChild(footer);
  });

  // ---------- signature motif: waveform → bubbles → codes → score ring ----------
  const wave = (amp, wavelength = 160, length = 960) => {
    let d = `M0 60 q${wavelength / 4} ${-amp} ${wavelength / 2} 0`;
    for (let x = wavelength / 2; x < length; x += wavelength / 2) d += ` t${wavelength / 2} 0`;
    return d;
  };
  document.querySelectorAll("[data-motif]").forEach((el) => {
    const r = 46, circ = 2 * Math.PI * r;
    el.classList.add(el.dataset.motif === "small" ? "motif-small" : "motif-large");
    el.innerHTML = `
      <svg class="wave" viewBox="0 0 480 120" width="480" height="120" aria-hidden="true" style="overflow:hidden">
        <path class="w1" d="${wave(42)}"/><path class="w2" d="${wave(26)}"/><path class="w3" d="${wave(12)}"/>
      </svg>
      <span class="ms arrow">arrow_forward</span>
      <div class="mini"><i></i><i></i><i></i></div>
      <span class="ms arrow">arrow_forward</span>
      <div class="codes"><span class="chip">OQ</span><span class="chip">CR</span><span class="chip ct">CT</span></div>
      <span class="ms arrow">arrow_forward</span>
      <svg viewBox="0 0 120 120" width="120" height="120" aria-label="Score 8 of 12">
        <circle cx="60" cy="60" r="${r}" fill="none" stroke="rgba(255,255,255,.15)" stroke-width="10"/>
        <circle cx="60" cy="60" r="${r}" fill="none" stroke="${C.teal300}" stroke-width="10" stroke-linecap="round"
          stroke-dasharray="${(circ * 8) / 12} ${circ}" transform="rotate(-90 60 60)"/>
        <text x="60" y="70" text-anchor="middle" class="ring-txt">8/12</text>
      </svg>`;
  });

  // ---------- charts ----------
  Chart.defaults.font.family = "Inter, 'Segoe UI', sans-serif";
  Chart.defaults.font.size = 20;
  Chart.defaults.color = C.ink;
  Chart.defaults.devicePixelRatio = 2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.enabled = false;
  Chart.defaults.animation.duration = 900;

  const vline = (value, label) => ({
    id: "vline",
    beforeDatasetsDraw(chart) {
      const { ctx, chartArea: a, scales: { x } } = chart;
      const px = x.getPixelForValue(value);
      ctx.save();
      ctx.strokeStyle = C.amber; ctx.lineWidth = 3; ctx.setLineDash([10, 8]);
      ctx.beginPath(); ctx.moveTo(px, a.top - 6); ctx.lineTo(px, a.bottom); ctx.stroke();
      ctx.setLineDash([]); ctx.fillStyle = "#B45309"; ctx.font = "600 18px Inter"; ctx.textAlign = "center"; ctx.textBaseline = "bottom";
      ctx.fillText(label, px, a.top - 10);
      ctx.restore();
    },
  });
  const barValues = (fmt, color = C.ink) => ({
    id: "barValues",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save(); ctx.font = "700 20px Inter"; ctx.textBaseline = "middle"; ctx.textAlign = "left";
      ctx.lineWidth = 6; ctx.strokeStyle = "#fff"; ctx.lineJoin = "round"; ctx.fillStyle = color;
      chart.data.datasets.forEach((ds, di) => {
        chart.getDatasetMeta(di).data.forEach((bar, i) => {
          const t = fmt(ds.data[i]);
          ctx.strokeText(t, bar.x + 10, bar.y); ctx.fillText(t, bar.x + 10, bar.y);
        });
      });
      ctx.restore();
    },
  });

  const charts = {
    s9() {
      const donut = (id, data, colors) => new Chart(document.getElementById(id), {
        type: "doughnut",
        data: { datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
        options: { cutout: "70%", responsive: true, maintainAspectRatio: false },
      });
      donut("chart-sal", [0, 1], [C.teal, C.coral]);
      donut("chart-mia", [5, 1], [C.teal, C.coral]);
    },
    s16() {
      new Chart(document.getElementById("chart-kappa"), {
        type: "bar",
        data: {
          labels: [["Main clinician", "behaviour"], ["Reflection", "none / simple / complex"], ["Client talk", "change / sustain / neutral"], ["Question", "none / open / closed"], ["Clinician", "input type"]],
          datasets: [
            { label: "MIRA (gpt-5.4)", data: [0.86, 0.68, 0.66, 0.77, 0.58], backgroundColor: C.teal, borderRadius: 6, barPercentage: 0.82, categoryPercentage: 0.78 },
            { label: "Human ceiling", data: [0.81, 0.57, 0.58, 0.80, 0.63], backgroundColor: C.slate, borderRadius: 6, barPercentage: 0.82, categoryPercentage: 0.78 },
          ],
        },
        options: {
          indexAxis: "y", responsive: true, maintainAspectRatio: false, layout: { padding: { right: 70, top: 34 } },
          scales: {
            x: { min: 0, max: 1, ticks: { stepSize: 0.2, font: { size: 18 } }, grid: { color: C.line }, title: { display: true, text: "Cohen's κ", font: { size: 18 } } },
            y: { ticks: { font: { size: 20 }, color: C.ink }, grid: { display: false } },
          },
        },
        plugins: [vline(0.6, "0.6 substantial"), barValues((v) => v.toFixed(2))],
      });
    },
    s17() {
      const jitter = (values, x) => {
        const seen = {}, totals = {};
        values.forEach((v) => (totals[v] = (totals[v] || 0) + 1));
        return values.map((v) => {
          const k = (seen[v] = (seen[v] || 0) + 1) - 1;
          return { x: x + (k - (totals[v] - 1) / 2) * 0.07, y: v };
        });
      };
      const high = [2, 4, 4, 5, 5, 6, 6, 7, 7, 7, 7, 7, 8, 8, 9, 9, 12];
      const low = [0, 0, 1, 1, 1, 1, 1, 1, 1, 3];
      const bands = {
        id: "bands",
        beforeDatasetsDraw(chart) {
          const { ctx, chartArea: a, scales: { y } } = chart;
          [[-0.5, 6.5, C.coral50, "Developing", C.coral], [6.5, 9.5, C.amber50, "Basic", "#B45309"], [9.5, 12.5, C.teal50, "Advanced", C.teal]].forEach(([lo, hi, fill, name, color]) => {
            const top = y.getPixelForValue(hi), bottom = y.getPixelForValue(lo);
            ctx.fillStyle = fill; ctx.fillRect(a.left, top, a.right - a.left, bottom - top);
            ctx.fillStyle = color; ctx.font = "700 18px Inter"; ctx.textAlign = "right"; ctx.fillText(name, a.right - 12, top + 26);
          });
        },
        afterDatasetsDraw(chart) {
          const { ctx, scales: { x, y } } = chart;
          [[1, 6.65, C.teal, "mean 6.65"], [2, 1.0, C.coral, "mean 1.0"]].forEach(([cx, m, color, label]) => {
            const py = y.getPixelForValue(m);
            ctx.strokeStyle = C.ink; ctx.lineWidth = 3;
            ctx.beginPath(); ctx.moveTo(x.getPixelForValue(cx - 0.42), py); ctx.lineTo(x.getPixelForValue(cx + 0.42), py); ctx.stroke();
            ctx.fillStyle = C.ink; ctx.font = "600 18px Inter"; ctx.textAlign = "left"; ctx.fillText(label, x.getPixelForValue(cx + 0.45), py + 6);
          });
        },
      };
      new Chart(document.getElementById("chart-auc"), {
        type: "scatter",
        data: {
          datasets: [
            { data: jitter(high, 1), backgroundColor: C.teal, pointRadius: 11, borderColor: "#fff", borderWidth: 2 },
            { data: jitter(low, 2), backgroundColor: C.coral, pointRadius: 11, borderColor: "#fff", borderWidth: 2 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            x: { min: 0.4, max: 2.75, grid: { display: false }, afterBuildTicks: (ax) => (ax.ticks = [{ value: 1 }, { value: 2 }]),
              ticks: { font: { size: 20, weight: "600" }, callback: (v) => (v === 1 ? "Expert-rated high quality" : "Expert-rated low quality") } },
            y: { min: -0.5, max: 12.5, afterBuildTicks: (ax) => (ax.ticks = [0, 2, 4, 6, 8, 10, 12].map((value) => ({ value }))),
              grid: { color: "rgba(11,31,51,.06)" }, title: { display: true, text: "Proficiency points (0–12)", font: { size: 18 } }, ticks: { font: { size: 18 } } },
          },
        },
        plugins: [bands],
      });
    },
    s19() {
      const seg = (label, data, color) => ({ label, data, backgroundColor: color, borderColor: "#fff", borderWidth: 2, barPercentage: 0.62 });
      const totals = { id: "totals", afterDatasetsDraw(chart) {
        const { ctx } = chart, last = chart.getDatasetMeta(chart.data.datasets.length - 1);
        ctx.save(); ctx.font = "700 26px Inter"; ctx.fillStyle = C.ink; ctx.textBaseline = "middle";
        ["≈ $0.09", "≈ $0.08"].forEach((t, i) => ctx.fillText(t, last.data[i].x + 14, last.data[i].y));
        ctx.restore();
      } };
      const segLabels = { id: "segLabels", afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save(); ctx.font = "600 17px Inter"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        chart.data.datasets.forEach((ds, di) => chart.getDatasetMeta(di).data.forEach((bar) => {
          const w = bar.x - bar.base;
          if (w > 150) { ctx.fillStyle = ds.textColor; ctx.fillText(ds.short, bar.base + w / 2, bar.y); }
        }));
        ctx.restore();
      } };
      const ds = [
        { ...seg("CU audio extraction", [0.0187, 0.0212], C.azure), short: "Audio", textColor: "#fff" },
        { ...seg("CU contextualization", [0.0052, 0.0059], "rgba(0,120,212,.7)"), short: "", textColor: "#fff" },
        { ...seg("CU field extraction (gpt-5.4-mini)", [0.0024, 0.0026], "rgba(0,120,212,.4)"), short: "", textColor: "#fff" },
        { ...seg("Coder · gpt-5.4", [0.0266, 0.0107], C.teal), short: "Coder", textColor: "#fff" },
        { ...seg("Supervisor · gpt-5.4", [0.0379, 0.0396], C.teal300), short: "Supervisor", textColor: C.ink },
      ];
      new Chart(document.getElementById("chart-cost"), {
        type: "bar",
        data: { labels: [["Mia", "3.1 min"], ["Sal", "3.5 min"]], datasets: ds },
        options: {
          indexAxis: "y", responsive: true, maintainAspectRatio: false, layout: { padding: { right: 130 } },
          scales: {
            x: { stacked: true, min: 0, max: 0.1, ticks: { callback: (v) => "$" + v.toFixed(2), stepSize: 0.02, font: { size: 18 } }, grid: { color: C.line } },
            y: { stacked: true, ticks: { font: { size: 22, weight: "700" } }, grid: { display: false } },
          },
          plugins: { legend: { display: true, position: "bottom", labels: { boxWidth: 22, boxHeight: 22, padding: 18, font: { size: 18 } } } },
        },
        plugins: [totals, segLabels],
      });
    },
  };

  const built = new Set();
  const build = (section) => {
    const id = section && section.id;
    if (!id || built.has(id) || !charts[id]) return;
    built.add(id);
    charts[id]();
  };

  // ---------- reveal ----------
  Reveal.initialize({
    width: 1920, height: 1080, margin: 0, minScale: 0.1, maxScale: 3,
    hash: true, slideNumber: false, controls: false, progress: true, center: false,
    transition: "fade", transitionSpeed: "fast", backgroundTransition: "fade",
    pdfSeparateFragments: false, pdfMaxPagesPerSlide: 1, plugins: [RevealNotes],
  }).then(() => {
    if (Reveal.isPrintView()) {
      Chart.defaults.animation = false;
      Object.keys(charts).forEach((id) => build(document.getElementById(id)));
    } else {
      build(Reveal.getCurrentSlide());
    }
    document.body.dataset.ready = "1";
  });
  Reveal.on("slidechanged", (e) => build(e.currentSlide));
})();
