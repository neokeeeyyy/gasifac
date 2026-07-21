function injectNavbar(active) {
  var links = [
    { label: "Inicio", href: "/gasifac/", key: "inicio" },
    { label: "Herramientas", href: "/gasifac/herramientas", key: "herramientas" },
    { label: "Comprar", href: "/gasifac/comprar", key: "comprar" },
    { label: "Nosotros", href: "/gasifac/nosotros", key: "nosotros" },
    { label: "Soporte", href: "/gasifac/soporte", key: "soporte" },
    { label: "FAQ", href: "/gasifac/faq", key: "faq" },
    { label: "Sugerencias", href: "/gasifac/sugerencias", key: "sugerencias" },
    { label: "Cuenta", href: "/gasifac/cuenta", key: "cuenta" }
  ];

  var linksHtml = links.map(function(l) {
    var cls = l.key === active ? ' class="active"' : '';
    return '<li><a href="' + l.href + '"' + cls + '>' + l.label + '</a></li>';
  }).join("");

  var html =
    '<header class="navbar">' +
      '<div class="nav-container">' +
        '<a href="/gasifac/" class="logo">' +
          '<i class="fa-solid fa-fire"></i>' +
          '<span>GASIFAC</span>' +
        '</a>' +
        '<button class="menu-toggle" id="menuToggle" aria-label="Menu">' +
          '<span></span><span></span><span></span>' +
        '</button>' +
        '<ul class="nav-links" id="navLinks">' + linksHtml + '</ul>' +
      '</div>' +
    '</header>';

  document.body.insertAdjacentHTML("afterbegin", html);
  setupMenu();
}

function injectFooter() {
  var html =
    '<footer class="footer">' +
      '<div class="container">' +
        '<p>&copy; 2026 <a href="https://neokey.dev" target="_blank">neokey</a>. Todos los derechos reservados.</p>' +
      '</div>' +
    '</footer>';

  document.body.insertAdjacentHTML("beforeend", html);
}

function setupMenu() {
  var toggle = document.getElementById("menuToggle");
  var links = document.getElementById("navLinks");
  if (!toggle || !links) return;
  toggle.addEventListener("click", function() { links.classList.toggle("active"); });
  links.querySelectorAll("a").forEach(function(a) {
    a.addEventListener("click", function() { links.classList.remove("active"); });
  });
}
