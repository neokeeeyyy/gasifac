const API = "/api/gas/v1";

document.addEventListener("DOMContentLoaded", async () => {
  await loadStats();
  setupSearch();
  setupCheckout();
});

async function loadStats() {
  try {
    const res = await fetch(`${API}/estadisticas`);
    const data = await res.json();
    document.getElementById("stat-max").textContent = `$${data.precio_nacional_max.toFixed(2)}/kg`;
    document.getElementById("stat-min").textContent = `$${data.precio_nacional_min.toFixed(2)}/kg`;
    document.getElementById("stat-avg").textContent = `$${data.precio_nacional_promedio.toFixed(2)}/kg`;
  } catch {
    // silently fail on landing
  }
}

function priceCard(m, precio) {
  const kg = precio ? `$${Number(precio.precio_kg).toFixed(2)}` : "—";
  const litro = precio ? `$${Number(precio.precio_litro).toFixed(2)}` : "—";
  const periodo = precio ? `${formatDate(precio.fecha_inicio)} — ${formatDate(precio.fecha_fin)}` : "";
  return `
    <div class="bg-white border border-slate-200 rounded-xl px-5 py-4 mb-3 hover:border-orange-300 hover:shadow-md transition cursor-default">
      <div class="flex items-center justify-between mb-2">
        <div>
          <div class="text-base font-bold text-slate-800">${m.municipio}</div>
          <div class="text-xs text-slate-400">${m.estado}</div>
        </div>
        ${periodo ? `<div class="text-[11px] text-slate-400 bg-slate-100 px-2 py-1 rounded-full">${periodo}</div>` : ""}
      </div>
      <div class="flex gap-3">
        <div class="flex-1 bg-orange-50 rounded-lg px-4 py-3 text-center">
          <div class="text-xs text-orange-600 font-medium mb-1">Precio por Kilo</div>
          <div class="text-xl font-bold text-orange-600">${kg}</div>
        </div>
        <div class="flex-1 bg-blue-50 rounded-lg px-4 py-3 text-center">
          <div class="text-xs text-blue-600 font-medium mb-1">Precio por Litro</div>
          <div class="text-xl font-bold text-blue-600">${litro}</div>
        </div>
      </div>
    </div>`;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-");
  const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];
  return `${parseInt(d)} ${meses[parseInt(m)-1]}`;
}

function setupSearch() {
  const input = document.getElementById("search-input");
  const results = document.getElementById("search-results");
  if (!input || !results) return;

  let debounce;
  input.addEventListener("input", () => {
    clearTimeout(debounce);
    const q = input.value.trim();
    if (q.length < 2) {
      results.innerHTML = "";
      return;
    }
    debounce = setTimeout(async () => {
      results.innerHTML = '<div class="px-4 py-6 text-center text-slate-400 text-sm">Buscando...</div>';
      try {
        const res = await fetch(`${API}/municipios?q=${encodeURIComponent(q)}&limit=10`);
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
      } catch {
        results.innerHTML = '<div class="px-4 py-8 text-center text-red-400 text-sm">Error de conexión</div>';
      }
    }, 300);
  });
}

async function selectMunicipio(id) {
  const res = await fetch(`${API}/precios/${id}`);
  const data = await res.json();
  const results = document.getElementById("search-results");
  results.innerHTML = priceCard(
    { municipio: data.municipio_nombre, estado: data.estado },
    data
  );
}

function setupCheckout() {
  const btn = document.getElementById("checkout-btn");
  if (!btn) return;

  const params = new URLSearchParams(window.location.search);
  if (params.get("success") === "true") {
    btn.textContent = "¡Pago exitoso!";
    btn.disabled = true;
    return;
  }

  btn.addEventListener("click", async () => {
    const email = prompt("Ingresa tu correo electrónico:");
    if (!email) return;
    btn.disabled = true;
    btn.textContent = "Redirigiendo...";

    try {
      const res = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          success_url: window.location.origin + "/gasifac/pricing?success=true",
          cancel_url: window.location.origin + "/gasifac/pricing?cancelled=true",
        }),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch {
      alert("Error al crear la sesión de pago.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Suscribirme ahora";
    }
  });
}
