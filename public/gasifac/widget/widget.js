const API = "/api/gas/v1";

document.addEventListener("DOMContentLoaded", loadPeriodo);

async function loadPeriodo() {
  try {
    const res = await fetch(`${API}/processing-status`);
    const data = await res.json();
    if (data.periodo_inicio && data.periodo_fin) {
      const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
      const [y1, m1, d1] = data.periodo_inicio.split("-");
      const [y2, m2, d2] = data.periodo_fin.split("-");
      document.getElementById("periodo").textContent =
        `${parseInt(d1)} ${meses[parseInt(m1)-1]} — ${parseInt(d2)} ${meses[parseInt(m2)-1]} ${y1}`;
    } else {
      document.getElementById("periodo").textContent = "Sin datos";
    }
  } catch {
    document.getElementById("periodo").textContent = "Sin datos";
  }
}
