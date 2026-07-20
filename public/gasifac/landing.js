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
      const res = await fetch(`${API}/municipios?q=${encodeURIComponent(q)}&limit=10`);
      const data = await res.json();
      results.innerHTML = data
        .map(
          (m) =>
            `<div class="result-item" onclick="selectMunicipio(${m.id})">
              <strong>${m.municipio}</strong>
              <div class="estado">${m.estado}</div>
            </div>`
        )
        .join("");
    }, 300);
  });
}

async function selectMunicipio(id) {
  const res = await fetch(`${API}/precios/${id}`);
  const data = await res.json();
  const results = document.getElementById("search-results");
  results.innerHTML = `
    <div class="result-item">
      <strong>${data.municipio_nombre} — $${data.precio_kg}/kg</strong>
      <div class="estado">${data.estado} · ${data.fecha_inicio} al ${data.fecha_fin}</div>
    </div>
  `;
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
