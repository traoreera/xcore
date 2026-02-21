/**
 * xcore Documentation – Custom JavaScript
 * Améliorations UX de la documentation Sphinx
 */

(function () {
  "use strict";

  // ── Copier le code au clic ───────────────────────────────────────────────
  function addCopyButtons() {
    const blocks = document.querySelectorAll("div.highlight pre");

    blocks.forEach(function (block) {
      // Éviter les doublons
      if (block.parentElement.querySelector(".copy-btn")) return;

      const btn = document.createElement("button");
      btn.className = "copy-btn";
      btn.title = "Copier le code";
      btn.setAttribute("aria-label", "Copier le code");
      btn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        + '<rect x="9" y="9" width="13" height="13" rx="2"/>'
        + '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
        + '</svg>';

      btn.addEventListener("click", function () {
        const code = block.innerText;
        navigator.clipboard.writeText(code).then(function () {
          btn.innerHTML =
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2">'
            + '<polyline points="20 6 9 17 4 12"/>'
            + '</svg>';
          setTimeout(function () {
            btn.innerHTML =
              '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
              + '<rect x="9" y="9" width="13" height="13" rx="2"/>'
              + '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
              + '</svg>';
          }, 2000);
        });
      });

      // Injecter le bouton dans le conteneur highlight
      const wrapper = block.parentElement;
      wrapper.style.position = "relative";
      wrapper.appendChild(btn);
    });
  }

  // ── Style du bouton copier ───────────────────────────────────────────────
  function injectCopyButtonStyles() {
    const style = document.createElement("style");
    style.textContent = `
      .copy-btn {
        position: absolute;
        top: 0.5em;
        right: 0.5em;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 4px;
        padding: 0.3em 0.4em;
        cursor: pointer;
        color: #aaa;
        line-height: 1;
        transition: background 0.2s, color 0.2s;
      }
      .copy-btn:hover {
        background: rgba(255,255,255,0.18);
        color: #fff;
      }
    `;
    document.head.appendChild(style);
  }

  // ── Lecture estimée ───────────────────────────────────────────────────────
  function addReadingTime() {
    const content = document.querySelector(".wy-nav-content article");
    if (!content) return;

    const text = content.innerText || "";
    const words = text.trim().split(/\s+/).length;
    const minutes = Math.max(1, Math.round(words / 200));

    const header = document.querySelector("h1");
    if (!header) return;

    const badge = document.createElement("span");
    badge.className = "reading-time";
    badge.style.cssText =
      "font-size:0.75em;color:#888;font-weight:400;"
      + "margin-left:0.8em;vertical-align:middle;";
    badge.textContent = `⏱ ${minutes} min de lecture`;
    header.appendChild(badge);
  }

  // ── Surligner la section active dans la sidebar ───────────────────────────
  function highlightActiveToc() {
    const headings = document.querySelectorAll(
      ".wy-nav-content h2, .wy-nav-content h3"
    );
    const tocLinks = document.querySelectorAll(".wy-menu-vertical a");

    if (!headings.length || !tocLinks.length) return;

    const observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute("id");
            tocLinks.forEach(function (link) {
              link.classList.remove("toc-active");
              if (link.getAttribute("href") === "#" + id) {
                link.classList.add("toc-active");
              }
            });
          }
        });
      },
      { rootMargin: "0px 0px -70% 0px" }
    );

    headings.forEach(function (h) {
      if (h.id) observer.observe(h);
    });
  }

  // ── Bouton "Retour en haut" ───────────────────────────────────────────────
  function addBackToTop() {
    const btn = document.createElement("button");
    btn.id = "back-to-top";
    btn.title = "Retour en haut";
    btn.setAttribute("aria-label", "Retour en haut de page");
    btn.innerHTML =
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">'
      + '<polyline points="18 15 12 9 6 15"/>'
      + '</svg>';

    const style = document.createElement("style");
    style.textContent = `
      #back-to-top {
        position: fixed;
        bottom: 2em;
        right: 2em;
        background: #e94560;
        color: #fff;
        border: none;
        border-radius: 50%;
        width: 42px;
        height: 42px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        opacity: 0;
        transform: translateY(10px);
        transition: opacity 0.3s, transform 0.3s;
        box-shadow: 0 2px 12px rgba(233,69,96,0.35);
        z-index: 999;
      }
      #back-to-top.visible {
        opacity: 1;
        transform: translateY(0);
      }
      #back-to-top:hover {
        background: #c73652;
      }
    `;
    document.head.appendChild(style);
    document.body.appendChild(btn);

    window.addEventListener("scroll", function () {
      btn.classList.toggle("visible", window.scrollY > 400);
    });

    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // ── Ouvrir les liens externes dans un nouvel onglet ───────────────────────
  function externalLinksNewTab() {
    const links = document.querySelectorAll(".wy-nav-content a[href]");
    links.forEach(function (link) {
      const href = link.getAttribute("href");
      if (href && href.startsWith("http") && !href.includes(window.location.hostname)) {
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
      }
    });
  }

  // ── Initialisation ────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    injectCopyButtonStyles();
    addCopyButtons();
    addReadingTime();
    highlightActiveToc();
    addBackToTop();
    externalLinksNewTab();

    console.log(
      "%c xcore docs ",
      "background:#e94560;color:#fff;font-weight:bold;border-radius:3px;padding:2px 6px",
      "— Documentation chargée ✓"
    );
  });
})();