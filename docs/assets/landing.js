document.addEventListener('DOMContentLoaded', () => {
  const menuButton = document.querySelector('.menu-toggle');
  const navigation = document.querySelector('#siteNav');
  const appUrl = (document.documentElement.dataset.appUrl || '').replace(/\/$/, '');
  const notice = document.querySelector('#appNotice');

  document.querySelector('#currentYear').textContent = String(new Date().getFullYear());

  menuButton?.addEventListener('click', () => {
    const isOpen = navigation.classList.toggle('is-open');
    menuButton.setAttribute('aria-expanded', String(isOpen));
  });

  navigation?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      navigation.classList.remove('is-open');
      menuButton?.setAttribute('aria-expanded', 'false');
    });
  });

  document.querySelectorAll('.app-link').forEach((link) => {
    if (appUrl) {
      link.href = `${appUrl}/login`;
      return;
    }
    link.addEventListener('click', (event) => {
      event.preventDefault();
      document.querySelector('#appNotice').hidden = false;
      document.querySelector('#appNotice').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });

  const animated = document.querySelectorAll('.feature-card, .flow-step, .access-cta');
  if (!animated.length || !('IntersectionObserver' in window)) return;
  animated.forEach((element) => element.classList.add('reveal-ready'));
  const observer = new IntersectionObserver((entries, currentObserver) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      currentObserver.unobserve(entry.target);
    });
  }, { threshold: 0.12 });
  animated.forEach((element) => observer.observe(element));
});
