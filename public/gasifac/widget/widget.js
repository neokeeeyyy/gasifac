const API = "/api/gas/v1";
let debounceTimer;

document.addEventListener("DOMContentLoaded", () => {
  loadPeriodo();
  setupSearch();
});

async function loadPeriodo() {
  try {
    const res = await fetch(`${API}/processing-status`);
    const data = await res.json();
    if (data.periodo_inicio && data.periodo_fin) {
      const inicio = formatDate(data.periodo_inicio);
      const fin = formatDate(data.periodo_fin);
      document.getElementById("periodo").textContent = `${inicio} — ${fin}`;
    } else {
      document.getElementById("periodo").textContent = "Sin datos";
    }
  } catch {
    document.getElementById("periodo").textContent = "Sin datos";
  }
}

function formatDate(dateStr) {
  const [y, m, d] = dateStr.split("-");
  const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
  return `${parseInt(d)} ${meses[parseInt(m)-1]}`;
}

function setupSearch() {
  const input = document.getElementById("search");
  const results = document.getElementById("results");

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) {
      results.innerHTML = '<div class="px-3 py-8 text-center text-slate-400 text-sm">Escribe al menos 2 caracteres</div>';
      return;
    }
    debounceTimer = setTimeout(() => searchMunicipios(q), 250);
  });
}

async function searchMunicipios(q) {
  const results = document.getElementById("results");
  results.innerHTML = '<div class="px-3 py-6 text-center text-slate-400 text-sm">Buscando...</div>';

  try {
    const res = await fetch(`${API}/municipios?q=${encodeURIComponent(q)}&limit=20`);
    const data = await res.json();
    if (data.length === 0) {
      results.innerHTML = '<div class="px-3 py-8 text-center text-slate-400 text-sm">Sin resultados</div>';
      return;
    }
    results.innerHTML = "";
    for (const m of data) {
      try {
        const precioRes = await fetch(`${API}/precios/${m.id}`);
        const precio = await precioRes.json();
        results.innerHTML += `
          <div class="flex items-center justify-between px-3 py-3 hover:bg-slate-50 rounded-xl transition cursor-default">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-slate-800 truncate">${m.municipio}</div>
              <div class="text-xs text-slate-400">${m.estado}</div>
            </div>
            <div class="text-right ml-3 flex-shrink-0">
              <div class="text-base font-bold text-orange-500">$${precio.precio_kg}</div>
              <div class="text-[10px] text-slate-400">por kg</div>
            </div>
          </div>`;
      } catch {
        results.innerHTML += `
          <div class="flex items-center justify-between px-3 py-3 hover:bg-slate-50 rounded-xl transition cursor-default">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-slate-800 truncate">${m.municipio}</div>
              <div class="text-xs text-slate-400">${m.estado}</div>
            </div>
            <div class="text-right ml-3 flex-shrink-0">
              <div class="text-base font-bold text-slate-300">—</div>
            </div>
          </div>`;
      }
    }
  } catch {
    results.innerHTML = '<div class="px-3 py-8 text-center text-red-400 text-sm">Error de conexión</div>';
  }
}
