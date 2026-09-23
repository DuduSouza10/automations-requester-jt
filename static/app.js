(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  // ---------------------------------------------------------------------------
  // UI helpers — delegated events keep working after live DOM synchronization.
  // ---------------------------------------------------------------------------
  function activateTab(name, updateHash = false) {
    const links = $$('[data-tab-link]');
    const sections = $$('[data-tab-section]');
    if (!links.length || !sections.length) return;
    links.forEach(a => a.classList.toggle('active', a.dataset.tabLink === name));
    sections.forEach(s => s.classList.toggle('active', s.dataset.tabSection === name));
    if (updateHash) history.replaceState(null, '', `#${name}`);
  }

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
    if (!$('.modal.open')) document.body.classList.remove('modal-open');
    if (modal.id && location.hash === `#${modal.id}`) {
      history.replaceState(null, '', `${location.pathname}${location.search}`);
    }
    setTimeout(applyPendingLiveRegions, 0);
  }

  document.addEventListener('click', e => {
    const toastClose = e.target.closest('.toast-close');
    if (toastClose) {
      toastClose.closest('.toast')?.remove();
      return;
    }

    const tabLink = e.target.closest('[data-tab-link]');
    if (tabLink) {
      e.preventDefault();
      const name = tabLink.dataset.tabLink;
      activateTab(name, true);
      window.scrollTo({ top: $('.section-tabs')?.offsetTop - 18 || 0, behavior: 'smooth' });
      return;
    }

    const modalOpen = e.target.closest('[data-modal-open]');
    if (modalOpen) {
      e.preventDefault();
      openModal(modalOpen.dataset.modalOpen);
      return;
    }

    const modalClose = e.target.closest('[data-modal-close]');
    if (modalClose) {
      closeModal(modalClose.closest('.modal'));
      return;
    }

    const collapseToggle = e.target.closest('[data-collapse-toggle]');
    if (collapseToggle) {
      const panel = document.getElementById(collapseToggle.dataset.collapseToggle);
      panel?.classList.toggle('open');
      return;
    }

    const passwordToggle = e.target.closest('[data-password-toggle]');
    if (passwordToggle) {
      const input = document.getElementById(passwordToggle.dataset.passwordToggle);
      if (!input) return;
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      passwordToggle.textContent = visible ? 'Mostrar' : 'Ocultar';
    }
  });

  document.addEventListener('change', e => {
    const input = e.target.closest('.multi-upload input[type="file"][multiple]');
    if (!input) return;
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
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal($('.modal.open'));
  });

  setTimeout(() => $$('.toast').forEach(el => el.classList.add('toast-hide')), 5500);

  const initialHash = location.hash.replace('#', '');
  if (initialHash && $$('[data-tab-link]').some(a => a.dataset.tabLink === initialHash)) {
    activateTab(initialHash);
  }
  if (initialHash && document.getElementById(initialHash)?.classList.contains('modal')) {
    openModal(initialHash);
  }

  // Admin sidebar active item follows scroll. Section roots are intentionally not
  // replaced by live sync, so one observer is enough for the whole page lifetime.
  const adminLinks = $$('.admin-nav a[href^="#"]:not([data-modal-open])');
  if (adminLinks.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      const visible = entries
        .filter(entry => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      adminLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === `#${visible.target.id}`));
    }, { rootMargin: '-20% 0px -65% 0px', threshold: [0, .2, .5] });

    adminLinks.forEach(a => {
      const section = document.querySelector(a.getAttribute('href'));
      if (section) observer.observe(section);
    });
  }

  // ---------------------------------------------------------------------------
  // Live synchronization.
  // The browser checks a tiny database fingerprint and only downloads the page
  // when something really changed. Dynamic regions are swapped in place, so the
  // active tab, scroll position and the request form stay untouched.
  // ---------------------------------------------------------------------------
  const pageMode = $('.admin-shell') ? 'admin' : ($('.public-shell') ? 'public' : null);
  let appliedToken = null;
  let pendingToken = null;
  let pendingDocument = null;
  let polling = false;
  let pollTimer = null;
  let pollInterval = 1200;

  function regionIsBusy(region) {
    if (!region) return false;

    // Keep text/file input safe while someone is actively editing it.
    const active = document.activeElement;
    if (active && region.contains(active) && ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName)) {
      return true;
    }

    // Never destroy an open action modal or an expanded delivery editor.
    if (region.matches('#notifications-modal')) return false;
    if ($('.modal.open', region)) return true;
    if ($('.collapse-panel.open', region)) return true;

    return false;
  }

  function copyLiveRegion(current, source, token) {
    const wasNotificationOpen = current.id === 'notifications-modal' && current.classList.contains('open');
    const notificationScroll = current.id === 'notifications-modal'
      ? $('.notification-modal-scroll', current)?.scrollTop || 0
      : 0;

    const replacement = document.importNode(source, true);
    replacement.dataset.liveToken = token;

    if (wasNotificationOpen) {
      replacement.classList.add('open');
      replacement.setAttribute('aria-hidden', 'false');
    }

    current.replaceWith(replacement);

    if (wasNotificationOpen) {
      document.body.classList.add('modal-open');
      const scrollBox = $('.notification-modal-scroll', replacement);
      if (scrollBox) scrollBox.scrollTop = notificationScroll;
    }
  }

  function applyPendingLiveRegions() {
    if (!pendingDocument || !pendingToken) return;

    let deferred = false;
    const currentRegions = $$('[data-live-region]');

    currentRegions.forEach(current => {
      if (current.dataset.liveToken === pendingToken) return;
      if (regionIsBusy(current)) {
        deferred = true;
        return;
      }

      const key = current.dataset.liveRegion;
      const source = pendingDocument.querySelector(`[data-live-region="${key}"]`);
      if (!source) return;
      copyLiveRegion(current, source, pendingToken);
    });

    // Re-check because replacements changed the node references above.
    const stillPending = $$('[data-live-region]').some(region => region.dataset.liveToken !== pendingToken);
    if (!deferred && !stillPending) {
      appliedToken = pendingToken;
      pendingToken = null;
      pendingDocument = null;
    }
  }

  async function downloadFreshPage(token) {
    const separator = location.search ? '&' : '?';
    const pageUrl = `${location.pathname}${location.search}${separator}_live=${Date.now()}`;
    const response = await fetch(pageUrl, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'same-origin',
      headers: { 'X-Live-Sync': '1' },
    });

    if (pageMode === 'admin' && response.redirected && response.url.includes('/admin/login')) {
      location.assign(response.url);
      return;
    }
    if (!response.ok) throw new Error(`Live page HTTP ${response.status}`);

    const html = await response.text();
    pendingDocument = new DOMParser().parseFromString(html, 'text/html');
    pendingToken = token;
    applyPendingLiveRegions();
  }

  async function pollLiveState() {
    if (!pageMode || polling || document.visibilityState === 'hidden') return;
    polling = true;

    try {
      const response = await fetch('/api/live-state', {
        method: 'GET',
        cache: 'no-store',
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      });
      if (!response.ok) throw new Error(`Live state HTTP ${response.status}`);

      const state = await response.json();
      if (Number.isFinite(state.interval_ms)) {
        pollInterval = Math.max(800, Math.min(5000, state.interval_ms));
      }
      const token = pageMode === 'admin' ? state.admin_token : state.public_token;
      if (!token) return;

      if (appliedToken === null) {
        appliedToken = token;
        return;
      }

      // If a newer snapshot is already downloaded, try applying any region that
      // was temporarily protected because the user was editing it.
      if (pendingToken === token && pendingDocument) {
        applyPendingLiveRegions();
        return;
      }

      if (token !== appliedToken) {
        await downloadFreshPage(token);
      }
    } catch (error) {
      // A temporary network/Railway hiccup must never break the page. The next
      // cycle retries automatically.
      console.debug('Live sync aguardando reconexão:', error);
    } finally {
      polling = false;
      clearTimeout(pollTimer);
      pollTimer = setTimeout(pollLiveState, pollInterval);
    }
  }

  if (pageMode) {
    pollLiveState();
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        clearTimeout(pollTimer);
        pollLiveState();
      }
    });
    document.addEventListener('focusout', () => setTimeout(applyPendingLiveRegions, 0));
  }
})();
