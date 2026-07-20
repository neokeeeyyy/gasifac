const API = "/api/gas/v1";
let allPrices = [];
let currentUnit = "kg";

document.addEventListener("DOMContentLoaded", () => {
  setupMenu();
  setupSearch();
  loadEstados();
  loadPrices();
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

function setupSearch() {
  const input = document.getElementById("searchInput");
  const select = document.getElementById("estadoFilter");
  const toggleBtns = document.querySelectorAll(".unit-toggle button");

  let debounce;
  input.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(filterResults, 200);
  });

  select.addEventListener("change", filterResults);

  toggleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      toggleBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentUnit = btn.dataset.unit;
      filterResults();
    });
  });
}

async function loadEstados() {
  try {
    const res = await fetch(`${API}/estados`);
    const estados = await res.json();
    const select = document.getElementById("estadoFilter");
    estados.forEach(e => {
      const opt = document.createElement("option");
      opt.value = e;
      opt.textContent = e;
      select.appendChild(opt);
    });
  } catch {}
}

async function loadPrices() {
  try {
    const res = await fetch(`${API}/precios`);
    allPrices = await res.json();
    filterResults();
  } catch {}
}

function filterResults() {
  const query = document.getElementById("searchInput").value.toLowerCase().trim();
  const estado = document.getElementById("estadoFilter").value;
  const table = document.getElementById("resultsTable");
  const tbody = document.getElementById("resultsBody");
  const header = document.getElementById("resultsHeader");
  const countEl = document.getElementById("resultsCount");
  const empty = document.getElementById("resultsEmpty");

  let filtered = allPrices;

  if (estado) {
    filtered = filtered.filter(p => p.estado === estado);
  }

  if (query) {
    filtered = filtered.filter(p =>
      p.municipio_nombre.toLowerCase().includes(query) ||
      p.estado.toLowerCase().includes(query)
    );
  }

  if (filtered.length === 0 && (query || estado)) {
    table.style.display = "none";
    header.style.display = "none";
    empty.style.display = "block";
    empty.innerHTML = '<i class="fa-solid fa-circle-info" style="font-size:1.2rem;color:var(--border);display:block;margin-bottom:12px;"></i>Sin resultados para esta búsqueda.';
    return;
  }

  if (!query && !estado) {
    table.style.display = "none";
    header.style.display = "none";
    empty.style.display = "block";
    empty.innerHTML = '<i class="fa-solid fa-magnifying-glass" style="font-size:1.4rem;color:var(--border);display:block;margin-bottom:12px;"></i>Escribe el nombre de un municipio o selecciona un estado para comenzar.';
    return;
  }

  empty.style.display = "none";
  table.style.display = "table";
  header.style.display = "flex";
  countEl.textContent = `${filtered.length} resultado${filtered.length !== 1 ? "s" : ""}`;

  tbody.innerHTML = "";
  filtered.forEach(p => {
    const price = currentUnit === "kg" ? p.precio_kg : p.precio_litro;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="municipio-cell">${p.municipio_nombre}</td>
      <td class="estado-cell">${p.estado}</td>
      <td class="price-cell">$${price.toFixed(2)} / ${currentUnit}</td>
    `;
    tbody.appendChild(tr);
  });
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
