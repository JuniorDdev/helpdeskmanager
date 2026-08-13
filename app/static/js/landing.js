document.addEventListener('DOMContentLoaded', () => {
  const animated = document.querySelectorAll('.feature-card, .flow-step, .landing-cta');
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
