const API = "/api/gas/v1";
let debounceTimer;

document.addEventListener("DOMContentLoaded", () => {
  loadPeriodo();
  setupSearch();
});

async function loadPeriodo() {
  try {
    const res = await fetch(`${API}/periodo`);
    const data = await res.json();
    document.getElementById("periodo").textContent =
      `${data.fecha_inicio} — ${data.fecha_fin}`;
  } catch {
    document.getElementById("periodo").textContent = "Sin datos";
  }
}

function setupSearch() {
  const input = document.getElementById("search");
  const results = document.getElementById("results");

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) {
      results.innerHTML = '<div class="empty">Escribe al menos 2 caracteres</div>';
      return;
    }
    debounceTimer = setTimeout(() => searchMunicipios(q), 250);
  });
}

async function searchMunicipios(q) {
  const results = document.getElementById("results");
  results.innerHTML = '<div class="empty">Buscando...</div>';

  try {
    const res = await fetch(`${API}/municipios?q=${encodeURIComponent(q)}&limit=20`);
    const data = await res.json();
    if (data.length === 0) {
      results.innerHTML = '<div class="empty">Sin resultados</div>';
      return;
    }
    results.innerHTML = "";
    for (const m of data) {
      try {
        const precioRes = await fetch(`${API}/precios/${m.id}`);
        const precio = await precioRes.json();
        results.innerHTML += `
          <div class="result">
            <div class="result-info">
              <div class="result-name">${m.municipio}</div>
              <div class="result-state">${m.estado}</div>
            </div>
            <div class="result-price">$${precio.precio_kg}<small>/kg</small></div>
          </div>`;
      } catch {
        results.innerHTML += `
          <div class="result">
            <div class="result-info">
              <div class="result-name">${m.municipio}</div>
              <div class="result-state">${m.estado}</div>
            </div>
            <div class="result-price">—</div>
          </div>`;
      }
    }
  } catch {
    results.innerHTML = '<div class="empty">Error de conexión</div>';
  }
}
