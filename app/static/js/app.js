document.addEventListener('DOMContentLoaded', () => {
  let installPrompt;
  const installBanner = document.getElementById('pwaInstallPrompt');
  const installButton = document.getElementById('pwaInstallButton');
  const dismissInstall = document.getElementById('pwaInstallDismiss');

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installBanner && !localStorage.getItem('pwa-install-dismissed')) installBanner.hidden = false;
  });
  installButton?.addEventListener('click', async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    if (installBanner) installBanner.hidden = true;
  });
  dismissInstall?.addEventListener('click', () => {
    localStorage.setItem('pwa-install-dismissed', '1');
    if (installBanner) installBanner.hidden = true;
  });
  window.addEventListener('appinstalled', () => {
    if (installBanner) installBanner.hidden = true;
    localStorage.removeItem('pwa-install-dismissed');
  });
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js'));
  }

  const sidebar = document.getElementById('appSidebar');
  const brandToggle = document.getElementById('brandToggle');
  const menuToggle = document.getElementById('menuToggle');
  const backdrop = document.getElementById('sidebarBackdrop');

  const closeMenu = () => {
    if (!sidebar || !menuToggle || !backdrop) return;
    sidebar.classList.remove('is-open');
    backdrop.classList.remove('is-visible');
    menuToggle.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('menu-open');
  };

  if (sidebar && menuToggle && backdrop) {
    menuToggle.addEventListener('click', () => {
      const open = sidebar.classList.toggle('is-open');
      backdrop.classList.toggle('is-visible', open);
      menuToggle.setAttribute('aria-expanded', String(open));
      document.body.classList.toggle('menu-open', open);
    });
    backdrop.addEventListener('click', closeMenu);
    window.addEventListener('resize', () => {
      if (window.innerWidth > 991) closeMenu();
    });
  }
  brandToggle?.addEventListener('click', () => document.body.classList.toggle('sidebar-collapsed'));

  const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
  const sidebarLinks = [...document.querySelectorAll('.sidebar-link')];
  const exactLink = sidebarLinks.find((link) => {
    const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '') || '/';
    return linkPath === currentPath;
  });
  sidebarLinks.forEach((link) => {
    const linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '') || '/';
    const active = exactLink ? link === exactLink : (linkPath !== '/' && currentPath.startsWith(`${linkPath}/`));
    link.classList.toggle('is-active', active);
    if (active) link.setAttribute('aria-current', 'page');
    link.addEventListener('click', closeMenu);
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll('.alert').forEach((alert) => {
    window.setTimeout(() => {
      alert.classList.add('fade');
      window.setTimeout(() => alert.remove(), 250);
    }, 5200);
  });
});
