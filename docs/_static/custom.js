(function () {
  function setupBackToTop() {
    const btn = document.createElement('button');
    btn.className = 'xcore-back-to-top';
    btn.title = 'Retour en haut';
    btn.setAttribute('aria-label', 'Retour en haut');
    btn.textContent = '↑';

    btn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    document.body.appendChild(btn);

    function onScroll() {
      if (window.scrollY > 240) {
        btn.classList.add('visible');
      } else {
        btn.classList.remove('visible');
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  function decorateExternalLinks() {
    document.querySelectorAll('.rst-content a[href^="http"]').forEach(function (a) {
      if (!a.href.includes(window.location.hostname)) {
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener noreferrer');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupBackToTop();
    decorateExternalLinks();
  });
})();
