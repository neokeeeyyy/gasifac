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
      results.innerHTML = '<div class="px-4 py-8 text-center text-slate-400 text-sm">Escribe al menos 2 caracteres</div>';
      return;
    }
    debounceTimer = setTimeout(() => searchMunicipios(q), 250);
  });
}

function priceCard(m, precio) {
  const kg = precio ? `$${Number(precio.precio_kg).toFixed(2)}` : "—";
  const litro = precio ? `$${Number(precio.precio_litro).toFixed(2)}` : "—";
  return `
    <div class="bg-white border border-slate-200 rounded-xl px-4 py-3 mb-2 hover:border-orange-300 hover:shadow-sm transition">
      <div class="text-sm font-bold text-slate-800">${m.municipio}</div>
      <div class="text-xs text-slate-400 mb-2">${m.estado}</div>
      <div class="flex gap-4">
        <div class="flex-1 bg-orange-50 rounded-lg px-3 py-2 text-center">
          <div class="text-xs text-orange-600 font-medium">Precio / Kilo</div>
          <div class="text-base font-bold text-orange-600">${kg}</div>
        </div>
        <div class="flex-1 bg-blue-50 rounded-lg px-3 py-2 text-center">
          <div class="text-xs text-blue-600 font-medium">Precio / Litro</div>
          <div class="text-base font-bold text-blue-600">${litro}</div>
        </div>
      </div>
    </div>`;
}

async function searchMunicipios(q) {
  const results = document.getElementById("results");
  results.innerHTML = '<div class="px-4 py-6 text-center text-slate-400 text-sm">Buscando...</div>';

  try {
    const res = await fetch(`${API}/municipios?q=${encodeURIComponent(q)}&limit=20`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.length === 0) {
      results.innerHTML = '<div class="px-4 py-8 text-center text-slate-400 text-sm">Sin resultados</div>';
      return;
    }

    const precios = await Promise.all(
      data.map(m =>
        fetch(`${API}/precios/${m.id}`)
          .then(r => r.ok ? r.json() : null)
          .catch(() => null)
      )
    );

    results.innerHTML = data.map((m, i) => priceCard(m, precios[i])).join("");
  } catch (err) {
    results.innerHTML = '<div class="px-4 py-8 text-center text-red-400 text-sm">Error de conexión</div>';
  }
}
