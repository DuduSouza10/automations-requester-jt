(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  // Toasts
  $$('.toast-close').forEach(btn => btn.addEventListener('click', () => btn.closest('.toast')?.remove()));
  setTimeout(() => $$('.toast').forEach(el => el.classList.add('toast-hide')), 5500);

  // Public tabs: hash-aware, single-section navigation.
  const links = $$('[data-tab-link]');
  const sections = $$('[data-tab-section]');
  function activateTab(name, updateHash = false) {
    if (!links.length || !sections.length) return;
    links.forEach(a => a.classList.toggle('active', a.dataset.tabLink === name));
    sections.forEach(s => s.classList.toggle('active', s.dataset.tabSection === name));
    if (updateHash) history.replaceState(null, '', `#${name}`);
  }
  links.forEach(link => link.addEventListener('click', e => {
    e.preventDefault();
    const name = link.dataset.tabLink;
    activateTab(name, true);
    window.scrollTo({ top: $('.section-tabs')?.offsetTop - 18 || 0, behavior: 'smooth' });
  }));
  const initialHash = location.hash.replace('#', '');
  if (initialHash && links.some(a => a.dataset.tabLink === initialHash)) activateTab(initialHash);

  // Modals
  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    setTimeout(() => $('textarea, input', modal)?.focus(), 120);
  }
  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    if (modal.id && location.hash === `#${modal.id}`) {
      history.replaceState(null, '', `${location.pathname}${location.search}`);
    }
  }
  $$('[data-modal-open]').forEach(btn => btn.addEventListener('click', e => {
    e.preventDefault();
    openModal(btn.dataset.modalOpen);
  }));
  $$('[data-modal-close]').forEach(btn => btn.addEventListener('click', () => closeModal(btn.closest('.modal'))));
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal($('.modal.open'));
  });

  // Reopen a modal after a server-side action redirects back to its hash.
  const hashModalId = location.hash.replace('#', '');
  if (hashModalId && document.getElementById(hashModalId)?.classList.contains('modal')) {
    openModal(hashModalId);
  }

  // Collapsible editor panels
  $$('[data-collapse-toggle]').forEach(btn => btn.addEventListener('click', () => {
    const panel = document.getElementById(btn.dataset.collapseToggle);
    panel?.classList.toggle('open');
  }));

  // Multiple request attachments: show what was selected.
  $$('.multi-upload input[type="file"][multiple]').forEach(input => input.addEventListener('change', () => {
    const box = input.closest('.multi-upload');
    const title = $('.multi-upload-copy strong', box);
    const hint = $('.multi-upload-copy small', box);
    const files = [...input.files];
    if (!files.length) {
      if (title) title.textContent = 'Anexar documentos';
      if (hint) hint.textContent = 'Você pode selecionar vários arquivos de uma vez.';
      return;
    }
    if (title) title.textContent = files.length === 1 ? files[0].name : `${files.length} arquivos selecionados`;
    if (hint) {
      const names = files.slice(0, 3).map(file => file.name).join(' · ');
      hint.textContent = files.length > 3 ? `${names} · +${files.length - 3}` : names;
    }
  }));

  // Password visibility
  $$('[data-password-toggle]').forEach(btn => btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.passwordToggle);
    if (!input) return;
    const visible = input.type === 'text';
    input.type = visible ? 'password' : 'text';
    btn.textContent = visible ? 'Mostrar' : 'Ocultar';
  }));

  // Admin sidebar active item follows scroll.
  const adminLinks = $$('.admin-nav a[href^="#"]');
  if (adminLinks.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(e => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      adminLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === `#${visible.target.id}`));
    }, { rootMargin: '-20% 0px -65% 0px', threshold: [0, .2, .5] });
    adminLinks.forEach(a => {
      const section = document.querySelector(a.getAttribute('href'));
      if (section) observer.observe(section);
    });
  }
})();
