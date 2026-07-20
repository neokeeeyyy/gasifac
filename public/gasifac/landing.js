const API = "/api/gas/v1";

document.addEventListener("DOMContentLoaded", () => {
  setupMenu();
  loadStats();
  loadInfo();
});

function setupMenu() {
  const toggle = document.getElementById("menuToggle");
  const links = document.getElementById("navLinks");
  if (!toggle || !links) return;
  toggle.addEventListener("click", () => links.classList.toggle("active"));
  links.querySelectorAll("a").forEach(a =>
    a.addEventListener("click", () => links.classList.remove("active"))
  );
}

async function loadStats() {
  try {
    const res = await fetch(`${API}/estadisticas`);
    const data = await res.json();
    setText("stat-max", `$${data.precio_nacional_max.toFixed(2)}/kg`);
    setText("stat-min", `$${data.precio_nacional_min.toFixed(2)}/kg`);
    setText("stat-avg", `$${data.precio_nacional_promedio.toFixed(2)}/kg`);
  } catch {}
}

async function loadInfo() {
  try {
    const [statusRes, statesRes] = await Promise.all([
      fetch(`${API}/processing-status`),
      fetch(`${API}/estados`)
    ]);
    const status = await statusRes.json();
    const states = await statesRes.json();

    if (status.periodo_inicio && status.periodo_fin) {
      const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
      const [y1, m1, d1] = status.periodo_inicio.split("-");
      const [y2, m2, d2] = status.periodo_fin.split("-");
      setText("info-periodo", `${parseInt(d1)} ${meses[parseInt(m1)-1]} — ${parseInt(d2)} ${meses[parseInt(m2)-1]}`);
    }
    setText("info-municipios", status.registros_insertados?.toLocaleString() || "—");
    setText("info-estados", states.length || "—");
  } catch {}
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
