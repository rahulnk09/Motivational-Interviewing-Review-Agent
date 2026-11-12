/* MIRA deck v2 runtime: backgrounds, footers, motif, heatmaps, dumbbells, chart, reveal.js init. */
(() => {
  const C = {
    ink: "#0B1F33", muted: "#64748B", line: "#E2E8F0", teal: "#0D9488", teal300: "#5EEAD4", teal50: "#F0FDFA",
    coral: "#EF6351", coral50: "#FEF2F1", amber: "#F59E0B", amber50: "#FFFBEB", azure: "#0078D4", slate: "#94A3B8",
  };
  const STAGES = ["Problem", "MI basics", "Solution", "Demo", "Impact", "Evidence", "Trust"];
  const slides = [...document.querySelectorAll(".reveal .slides > section")];

  // ---------- backgrounds + footer (brand · progress strip · slide number) ----------
  slides.forEach((s, i) => {
    if (s.dataset.bg === "dark") s.setAttribute("data-background-gradient", "linear-gradient(135deg, #061423 0%, #0E2A44 100%)");
    else s.setAttribute("data-background-color", "#F8FAFC");
    if (!s.dataset.progress) return;
    const now = STAGES.indexOf(s.dataset.progress);
    const strip = STAGES.map((n, k) => `<span class="${k < now ? "done" : k === now ? "now" : ""}">${n}</span>`).join("");
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
    el.classList.add("motif");
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

  // ---------- confusion matrices (HTML heatmaps, shaded by row %) ----------
  document.querySelectorAll("table.cm").forEach((t) => {
    const rows = t.dataset.rows.split(","), cols = t.dataset.cols.split(",");
    const vals = t.dataset.values.split(";").map((r) => r.split(",").map(Number));
    let html = `<thead><tr><th class="corner">expert ↓ · MIRA →</th>${cols.map((c) => `<th>${c}</th>`).join("")}<th class="tot">total</th></tr></thead><tbody>`;
    vals.forEach((r, i) => {
      const total = r.reduce((a, b) => a + b, 0);
      html += `<tr><th>${rows[i]}</th>`;
      r.forEach((v, j) => {
        const p = v / total, diag = i === j;
        const bg = diag ? `rgba(13,148,136,${0.12 + 0.88 * p})` : `rgba(239,99,81,${Math.min(0.9, 0.06 + 1.6 * p)})`;
        const fg = (diag ? p > 0.45 : p > 0.3) ? "#fff" : C.ink;
        html += `<td class="${diag ? "diag" : ""}" style="background:${bg};color:${fg}"><b>${v}</b><span>${Math.round(p * 100)}%</span></td>`;
      });
      html += `<td class="tot">${total}</td></tr>`;
    });
    t.innerHTML = html + "</tbody>";
  });

  // ---------- dumbbells: humans (grey) vs MIRA (teal), κ axis 0.3–1.0 ----------
  const LO = 0.3, HI = 1.0, pos = (v) => `${((v - LO) / (HI - LO)) * 100}%`;
  document.querySelectorAll(".dumbbell").forEach((el) => {
    const rows = el.dataset.rows.split(";").map((r) => r.split("|"));
    const ticks = [0.4, 0.6, 0.8, 1.0].map((v) => `<span class="tick" style="left:${pos(v)}">${v.toFixed(1)}</span>`).join("");
    el.innerHTML = rows.map(([label, h, m]) => {
      const hv = Number(h), mv = Number(m), [lab, sub] = label.split(/ (?=none|change)/);
      return `<div class="db-row">
        <div class="db-label"><b>${lab}</b>${sub ? `<span>${sub}</span>` : ""}</div>
        <div class="db-track">
          <span class="db-line" style="left:${pos(Math.min(hv, mv))};width:calc(${pos(Math.max(hv, mv))} - ${pos(Math.min(hv, mv))})"></span>
          <span class="db-dot h" style="left:${pos(hv)}"></span><span class="db-dot m" style="left:${pos(mv)}"></span>
          <span class="db-val h" style="left:${pos(hv)}">${hv.toFixed(2)}</span><span class="db-val m" style="left:${pos(mv)}">${mv.toFixed(2)}</span>
        </div></div>`;
    }).join("") + `<div class="db-axis"><div class="db-label"></div><div class="db-ticks">${ticks}</div></div>`;
  });

  // ---------- charts ----------
  Chart.defaults.font.family = "Inter, 'Segoe UI', sans-serif";
  Chart.defaults.font.size = 20;
  Chart.defaults.color = C.ink;
  Chart.defaults.devicePixelRatio = 2;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.enabled = false;
  Chart.defaults.animation.duration = 900;

  const charts = {
    s13() {
      // Per-session proficiency points: eval/supervisor/gpt-5.4_medium_1d9518c3/transcripts.csv
      const high = [2, 2, 4, 5, 6, 6, 6, 6, 7, 8, 8, 8, 9, 9, 9, 10, 11];
      const low = [0, 0, 0, 1, 1, 1, 1, 2, 2, 3];
      const jitter = (values, y) => {
        const seen = {}, totals = {};
        values.forEach((v) => (totals[v] = (totals[v] || 0) + 1));
        return values.map((v) => {
          const k = (seen[v] = (seen[v] || 0) + 1) - 1;
          return { x: v, y: y + (k - (totals[v] - 1) / 2) * 0.16 };
        });
      };
      const bands = {
        id: "bands",
        beforeDatasetsDraw(chart) {
          const { ctx, chartArea: a, scales: { x } } = chart;
          [[-0.5, 6.5, C.coral50, "Developing 0–6", C.coral], [6.5, 9.5, C.amber50, "Basic 7–9", "#B45309"], [9.5, 12.5, C.teal50, "Advanced 10–12", C.teal]].forEach(([lo, hi, fill, name, color]) => {
            const l = x.getPixelForValue(lo), r = x.getPixelForValue(hi);
            ctx.fillStyle = fill; ctx.fillRect(l, a.top, r - l, a.bottom - a.top);
            ctx.fillStyle = color; ctx.font = "700 18px Inter"; ctx.textAlign = "center"; ctx.fillText(name, (l + r) / 2, a.top + 26);
          });
        },
        afterDatasetsDraw(chart) {
          const { ctx, scales: { x, y } } = chart;
          [[1, 6.82, C.teal, "mean 6.8"], [0, 1.1, C.coral, "mean 1.1"]].forEach(([cy, m, color, label]) => {
            const px = x.getPixelForValue(m), top = y.getPixelForValue(cy + 0.42), bottom = y.getPixelForValue(cy - 0.42);
            ctx.save();
            ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.setLineDash([6, 5]);
            ctx.beginPath(); ctx.moveTo(px, top); ctx.lineTo(px, bottom); ctx.stroke();
            ctx.setLineDash([]); ctx.fillStyle = C.ink; ctx.font = "600 18px Inter"; ctx.textAlign = "left"; ctx.fillText(label, px + 8, top + 4);
            ctx.restore();
          });
        },
      };
      new Chart(document.getElementById("chart-sep"), {
        type: "scatter",
        data: {
          datasets: [
            { data: jitter(high, 1), backgroundColor: C.teal, pointRadius: 13, borderColor: "#fff", borderWidth: 2 },
            { data: jitter(low, 0), backgroundColor: C.coral, pointRadius: 13, borderColor: "#fff", borderWidth: 2 },
          ],
        },
        options: {
          responsive: true, maintainAspectRatio: false, layout: { padding: { top: 10, right: 10 } },
          scales: {
            y: { min: -0.6, max: 1.75, grid: { display: false }, afterBuildTicks: (ax) => (ax.ticks = [{ value: 0 }, { value: 1 }]),
              ticks: { font: { size: 20, weight: "700" }, callback: (v) => (v === 1 ? ["Expert-rated", "good (17)"] : ["Expert-rated", "poor (10)"]) } },
            x: { min: -0.5, max: 12.5, afterBuildTicks: (ax) => (ax.ticks = [0, 2, 4, 6, 8, 10, 12].map((value) => ({ value }))),
              grid: { color: "rgba(11,31,51,.06)" }, title: { display: true, text: "MIRA proficiency points (0–12)", font: { size: 18 } }, ticks: { font: { size: 18 } } },
          },
        },
        plugins: [bands],
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
