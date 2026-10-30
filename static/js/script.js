// ---- Session guard for background requests ----
// When the session ends (logged out, account deactivated, password changed) or
// the user loses access, the server answers a page's polling request with an
// X-Redirect header instead of an HTTP error. Go there once, and hold back the
// response so no page script tries to draw the "error" payload.
(function () {
  const nativeFetch = window.fetch.bind(window);
  let leaving = false;
  window.fetch = function () {
    return nativeFetch.apply(null, arguments).then(function (res) {
      const target = res.headers.get('X-Redirect');
      if (!target) return res;
      if (!leaving) { leaving = true; window.location.href = target; }
      return new Promise(function () {});
    });
  };
})();

// ---- Page timers ----
// Pages switch without a reload (see "In-app page switching" below), so every
// repeating timer a page starts (its 5-second live refresh) is remembered and
// stopped when the user moves to another page. The shell's own timers (bell,
// clock, account sync) use shellInterval and keep running.
const shellInterval = window.setInterval.bind(window);
const pageIntervals = new Set();
window.setInterval = function () {
  const id = shellInterval.apply(null, arguments);
  pageIntervals.add(id);
  return id;
};
function stopPageTimers() {
  pageIntervals.forEach(function (id) { clearInterval(id); });
  pageIntervals.clear();
}

// ---- Light / dark mode (switch in the top bar) ----
// Saved in this browser; templates/_theme_init.html applies it before the page
// is drawn. Charts read their axis colours from chartTheme() when created.
function currentTheme() {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}
function setTheme(theme) {
  const root = document.documentElement;
  root.classList.add('theme-switching');
  if (theme === 'light') root.setAttribute('data-theme', 'light');
  else root.removeAttribute('data-theme');
  root.setAttribute('data-bs-theme', theme);
  try { localStorage.setItem('fleetfuel-theme', theme); } catch (e) {}
  setTimeout(function () { root.classList.remove('theme-switching'); }, 350);
}
window.chartTheme = function () {
  const light = currentTheme() === 'light';
  return {
    light: light,
    text: light ? '#667085' : '#9698a9',
    grid: light ? 'rgba(16, 24, 40, 0.07)' : 'rgba(255, 255, 255, 0.06)',
    // Line colours: charcoal and amber on the light glass, blue and teal on dark.
    line: light ? '#2b251d' : '#2697ff',
    lineFill: light ? 'rgba(43, 37, 29, 0.08)' : 'rgba(38,151,255,0.12)',
    line2: light ? '#c8792b' : '#26e5c5',
    line2Fill: light ? 'rgba(200, 121, 43, 0.12)' : 'rgba(38,229,197,0.12)'
  };
};
// The top-bar switch: knob under the moon = dark, under the sun = light.
function labelThemeToggle() {
  const btn = document.querySelector('[data-theme-toggle]');
  if (!btn) return;
  const dark = currentTheme() === 'dark';
  btn.setAttribute('aria-checked', dark ? 'true' : 'false');
  btn.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
}
document.addEventListener('click', function (e) {
  if (!e.target.closest('[data-theme-toggle]')) return;
  setTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  labelThemeToggle();
});

// ---- Everything inside the page area that needs wiring up. Runs on the first
// load and again after every in-app page switch (on the new content). ----
function initPage() {
  labelThemeToggle();

  // Tables on phones: each cell carries its column name (data-label), so
  // style.css can show every row as a card. Rows redrawn by the live refresh
  // are labelled again as they arrive.
  document.querySelectorAll('table.table-fleet').forEach(function (table) {
    const labels = Array.from(table.querySelectorAll('thead th')).map(function (th) { return th.textContent.trim(); });
    const label = function () {
      table.querySelectorAll('tbody tr').forEach(function (tr) {
        Array.from(tr.children).forEach(function (td, i) {
          if (!td.hasAttribute('colspan') && labels[i] && td.dataset.label !== labels[i]) td.dataset.label = labels[i];
          // A cell with nothing in it (e.g. no actions for this user) is left out of the phone card.
          td.classList.toggle('cell-empty', !td.hasAttribute('colspan') && !td.children.length && !td.textContent.trim());
        });
      });
    };
    label();
    table.querySelectorAll('tbody').forEach(function (body) {
      new MutationObserver(label).observe(body, { childList: true });
    });
  });

  // Shared record modals (Trip / Fuel Records): each page has ONE view/edit
  // modal; when it opens, fill it from the clicked row's data-record JSON and
  // point the form at that record.
  document.querySelectorAll('.modal[data-record-modal]').forEach(function (modal) {
    modal.addEventListener('show.bs.modal', function (e) {
      const row = e.relatedTarget && e.relatedTarget.closest('[data-record]');
      if (!row) return;
      const rec = JSON.parse(row.dataset.record);
      const form = modal.querySelector('form');
      if (form) {
        if (form.dataset.actionTemplate) form.action = form.dataset.actionTemplate.replace('/0/', '/' + rec.id + '/');
        Object.keys(rec).forEach(function (key) {
          const field = form.elements[key];
          if (field && field.type !== 'hidden') field.value = rec[key] === null ? '' : rec[key];
        });
        form.classList.remove('was-validated');
      }
      modal.querySelectorAll('[data-field]').forEach(function (el) {
        const v = rec[el.dataset.field];
        el.textContent = (v === null || v === undefined || v === '') ? (el.dataset.empty || '—') : v + (el.dataset.suffix || '');
      });
    });
  });

  // Flash messages -> Bootstrap toasts
  const flashData = document.getElementById('flashData');
  if (flashData) {
    try {
      const messages = JSON.parse(flashData.dataset.messages);
      messages.forEach(([category, text]) => showToast(text, category));
    } catch (err) { /* no-op */ }
    flashData.remove();  // shown once
  }

  // Password show/hide toggles
  document.querySelectorAll('.password-toggle').forEach(function (icon) {
    const targetId = icon.getAttribute('data-target');
    const input = document.getElementById(targetId);
    if (!input) return;

    icon.addEventListener('click', function () {
      if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
      } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
      }
    });

    // Only show the reveal icon once the field actually has typed content.
    const syncVisibility = function () {
      icon.classList.toggle('d-none', input.value.length === 0);
    };
    syncVisibility();
    input.addEventListener('input', syncVisibility);
  });

  // Global loading overlay on form submit (data-loading attr)
  document.querySelectorAll('form[data-loading]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (form.checkValidity && !form.checkValidity()) return;
      showLoading(form.getAttribute('data-loading') || 'Processing...');
    });
  });

  // Bootstrap client-side validation
  document.querySelectorAll('form.needs-validation').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
        hideLoading();
      }
      form.classList.add('was-validated');
    }, false);
  });

  // Generic table search filter (data-search-input + data-search-table)
  document.querySelectorAll('[data-search-input]').forEach(function (input) {
    const tableId = input.getAttribute('data-search-input');
    const table = document.getElementById(tableId);
    if (!table) return;
    const apply = function () {
      const term = input.value.toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (row) {
        row.style.display = row.innerText.toLowerCase().includes(term) ? '' : 'none';
      });
    };
    input.addEventListener('input', apply);  // typing, pasting and autofill
    input.addEventListener('keyup', apply);
    input.addEventListener('search', apply);
    if (input.value) apply();  // opened with a search already filled in (e.g. a month from the dashboard)
  });

  // Date pickers whose latest allowed day is "today" move on at midnight, since
  // the pages stay open and refresh by themselves.
  const loadedToday = phToday();
  const pickers = Array.prototype.filter.call(document.querySelectorAll('input[type="date"][max]'),
    function (el) { return el.max === loadedToday; });
  if (pickers.length) {
    setInterval(function () {
      const today = phToday();
      pickers.forEach(function (el) { if (el.max !== today) el.max = today; });
    }, 60000);
  }
}

// ---- Phone showing the desktop layout ("Desktop site" is on in the browser) ----
// A phone browser in desktop mode pretends to be a ~980 px wide screen, so the
// screen-size rules pick the desktop layout. On a touch phone in that mode,
// every width rule (ours and Bootstrap's) is re-checked against the phone's
// real width and the page is scaled to fit, so the phone layout is used
// anyway. If a stylesheet cannot be read, a one-line hint is shown instead.
function usePhoneLayoutOnDesktopSite() {
  const touch = navigator.maxTouchPoints > 0 || 'ontouchstart' in window;
  const realWidth = window.screen.width;
  if (!touch || Math.min(window.screen.width, window.screen.height) > 600) return;
  const root = document.documentElement;
  if (!root.classList.contains('force-phone') && window.innerWidth < 900) return;  // normal phone layout already
  const fits = function (text) {  // would this width rule apply at the phone's real width?
    let ok = true;
    text.replace(/\((min|max)-width:\s*([\d.]+)px\)/g, function (_, kind, px) {
      if (kind === 'min' && realWidth < +px) ok = false;
      if (kind === 'max' && realWidth > +px) ok = false;
    });
    return ok;
  };
  let unreadable = false;
  const rewrite = function (rules) {
    Array.prototype.forEach.call(rules, function (rule) {
      if (rule.media && rule.conditionText !== undefined) {
        if (rule._originalMedia === undefined) rule._originalMedia = rule.media.mediaText;
        const text = rule._originalMedia;
        if (/width/.test(text) && !/print/.test(text)) rule.media.mediaText = fits(text) ? 'all' : 'not all';
      }
      if (rule.cssRules) rewrite(rule.cssRules);
    });
  };
  Array.prototype.forEach.call(document.styleSheets, function (sheet) {
    if (!sheet.href || !/bootstrap|style\.css/.test(sheet.href)) return;
    try { rewrite(sheet.cssRules); } catch (e) { unreadable = true; }
  });
  if (unreadable) return showDesktopSiteHint();
  root.classList.add('force-phone');
  const zoom = window.innerWidth / realWidth;
  root.style.zoom = zoom;
  root.style.setProperty('--fp-zoom', zoom);  // full-height layouts divide by it (style.css)
}
function showDesktopSiteHint() {
  let dismissed = false;
  try { dismissed = sessionStorage.getItem('desktopHintClosed') === '1'; } catch (e) { /* storage blocked */ }
  if (dismissed || document.querySelector('.desktop-site-hint')) return;
  const bar = document.createElement('div');
  bar.className = 'desktop-site-hint';
  bar.setAttribute('role', 'note');
  bar.innerHTML = '<span><i class="fa-solid fa-mobile-screen-button"></i> Showing the desktop version. For the phone layout, ' +
    'turn off <strong>"Desktop site"</strong> in your browser menu.</span><button type="button" aria-label="Close">&times;</button>';
  bar.querySelector('button').addEventListener('click', function () {
    bar.remove();
    try { sessionStorage.setItem('desktopHintClosed', '1'); } catch (e) { /* storage blocked */ }
  });
  document.body.prepend(bar);
}
document.addEventListener('DOMContentLoaded', usePhoneLayoutOnDesktopSite);
window.addEventListener('orientationchange', function () { setTimeout(usePhoneLayoutOnDesktopSite, 300); });

document.addEventListener('DOMContentLoaded', function () {
  // ---- Loading bar for page changes ----
  const progress = document.getElementById('pageProgress');
  let navTimer = null;
  const startNav = function () {
    if (!progress) return;
    progress.classList.add('is-loading');
    clearTimeout(navTimer);
    navTimer = setTimeout(endNav, 10000);  // safety net: never leave it running
  };
  const endNav = function () {
    clearTimeout(navTimer);
    if (progress) progress.classList.remove('is-loading');
  };
  document.addEventListener('submit', function (e) {
    if (!e.defaultPrevented) startNav();
  });
  // Back/forward restores a page from cache: hide the bar again.
  window.addEventListener('pageshow', endNav);

  // ---- In-app page switching (like a single-page app) ----
  // A click on a link inside the system swaps only the page area: the sidebar,
  // top bar, bell and clock stay as they are, the chosen menu item lights up
  // at once, and pages are fetched ahead while the pointer rests on a link.
  // Anything unusual (file downloads, the login page, errors) falls back to a
  // normal page load.
  const main = document.querySelector('main.content-area');
  const pageScripts = document.getElementById('pageScripts');
  if (main && pageScripts && window.DOMParser && history.pushState) {
    const pageCache = new Map();  // url -> { promise, at }
    const loadedScripts = new Set(Array.from(document.scripts).filter(function (s) { return s.src; }).map(function (s) { return s.src; }));
    let navToken = 0;

    const pageUrl = function (a, e) {
      if (!a || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return null;
      if (a.target === '_blank' || a.hasAttribute('download') || a.dataset.bsToggle || a.dataset.noSwap !== undefined) return null;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return null;
      if (a.origin !== location.origin) return null;
      if (/export|\.csv$|^\/(static|api)\/|^\/logout/i.test(a.pathname)) return null;  // files and actions, not pages
      if (a.pathname === location.pathname && a.search === location.search && a.hash) return null;
      return a.href.split('#')[0];
    };

    const fetchPage = function (url) {
      const hit = pageCache.get(url);
      if (hit && Date.now() - hit.at < 15000) return hit.promise;
      const promise = fetch(url, { headers: { 'Accept': 'text/html' }, credentials: 'same-origin' })
        .then(function (res) {
          return res.text().then(function (html) {
            return { url: res.url, html: html, type: res.headers.get('Content-Type') || '' };
          });
        });
      pageCache.set(url, { promise: promise, at: Date.now() });
      promise.catch(function () { pageCache.delete(url); });
      return promise;
    };

    const loadScript = function (src) {
      if (loadedScripts.has(src)) return Promise.resolve();
      return new Promise(function (resolve) {
        const s = document.createElement('script');
        s.src = src;
        s.onload = s.onerror = function () { loadedScripts.add(src); resolve(); };
        document.head.appendChild(s);
      });
    };

    const swapPage = function (doc, newMain, finalUrl, push) {
      // Leave the old page: stop its timers, charts and any open dialog.
      stopPageTimers();
      window.refreshBeforePrint = undefined;
      if (window.Chart && Chart.instances) Object.values(Chart.instances).forEach(function (c) { c.destroy(); });
      document.querySelectorAll('.modal.show').forEach(function (m) {
        const inst = window.bootstrap && bootstrap.Modal.getInstance(m);
        if (inst) inst.hide();
      });
      document.querySelectorAll('.modal-backdrop').forEach(function (b) { b.remove(); });
      document.body.classList.remove('modal-open');
      document.body.style.removeProperty('overflow');
      document.body.style.removeProperty('padding-right');

      if (push) history.pushState(null, '', finalUrl);
      else history.replaceState(null, '', finalUrl);
      document.title = doc.title;
      const h1 = document.querySelector('.topbar-title h1');
      const newH1 = doc.querySelector('.topbar-title h1');
      if (h1 && newH1) h1.textContent = newH1.textContent;
      const nav = document.querySelector('.sidebar-nav');
      const newNav = doc.querySelector('.sidebar-nav');
      if (nav && newNav) nav.innerHTML = newNav.innerHTML;  // active item and badges

      const newScripts = Array.from(newMain.querySelectorAll('script'));
      const extra = doc.getElementById('pageScripts');
      if (extra) newScripts.push.apply(newScripts, Array.from(extra.querySelectorAll('script')));
      newMain.querySelectorAll('script').forEach(function (s) { s.remove(); });
      main.innerHTML = newMain.innerHTML;
      pageScripts.innerHTML = '';
      window.scrollTo(0, 0);

      // Run the new page's scripts in their own scope (so a page can be opened
      // again without "already declared" errors), after any library it needs.
      const externals = newScripts.filter(function (s) { return s.src; });
      const inline = newScripts.filter(function (s) { return !s.src && (!s.type || /javascript/.test(s.type)); })
        .map(function (s) { return s.textContent; }).join('\n;\n');
      return externals.reduce(function (p, s) { return p.then(function () { return loadScript(s.src); }); }, Promise.resolve())
        .then(function () {
          if (inline.trim()) {
            const el = document.createElement('script');
            el.textContent = '(function () {\n' + inline + '\n})();';
            pageScripts.appendChild(el);
          }
          initPage();
        });
    };

    const navigate = function (url, push) {
      const token = ++navToken;
      startNav();
      const slow = setTimeout(function () { if (token === navToken) main.classList.add('is-switching'); }, 150);
      // Safety net: if the page has not arrived in 8 seconds, load it the normal way.
      const stuck = setTimeout(function () { if (token === navToken) { pageCache.delete(url); window.location.href = url; } }, 8000);
      fetchPage(url)
        .then(function (r) {
          pageCache.delete(url);  // used once: the next visit gets fresh data
          if (token !== navToken) return;
          if (!/text\/html/i.test(r.type)) { window.location.href = url; return; }
          const doc = new DOMParser().parseFromString(r.html, 'text/html');
          const newMain = doc.querySelector('main.content-area');
          if (!newMain || !doc.getElementById('pageScripts')) { window.location.href = r.url; return; }  // e.g. the login page
          return swapPage(doc, newMain, r.url, push);
        })
        .catch(function () { if (token === navToken) window.location.href = url; })
        .then(function () {
          clearTimeout(slow); clearTimeout(stuck);
          if (token === navToken) { main.classList.remove('is-switching'); endNav(); }
        });
    };
    window.navigateTo = function (url) { navigate(new URL(url, location.href).href, true); };

    // Light up the chosen menu item and show its name in the top bar at once.
    const markNav = function (navLink) {
      if (!navLink) return;
      document.querySelectorAll('.sidebar-nav .nav-link.active').forEach(function (l) { l.classList.remove('active'); });
      navLink.classList.add('active');
      const label = navLink.querySelector('span');
      const h1 = document.querySelector('.topbar-title h1');
      if (label && h1) h1.textContent = label.textContent;
    };

    document.addEventListener('click', function (e) {
      const a = e.target.closest('a[href]');
      const url = pageUrl(a, e);
      if (!url) return;
      e.preventDefault();
      markNav(a.closest('.sidebar-nav .nav-link'));
      const sb = document.getElementById('sidebar');
      if (sb) sb.classList.remove('open');  // phones: close the menu right away
      // Close any open dropdown (e.g. the bell) so it doesn't stay over the new page.
      document.querySelectorAll('[data-bs-toggle="dropdown"].show').forEach(function (t) {
        const dd = window.bootstrap && bootstrap.Dropdown.getInstance(t);
        if (dd) dd.hide();
      });
      navigate(url, true);
    });

    // Fetch a page ahead while the pointer rests on its link (or a finger touches it).
    let hoverTimer = null;
    const prefetch = function (e) {
      const a = e.target.closest && e.target.closest('a[href]');
      const url = a && pageUrl(a, { defaultPrevented: false, button: 0 });
      if (!url || url === location.href.split('#')[0]) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(function () { fetchPage(url).catch(function () {}); }, e.type === 'touchstart' ? 0 : 80);
    };
    document.addEventListener('mouseover', prefetch);
    document.addEventListener('touchstart', prefetch, { passive: true });
    document.addEventListener('mouseout', function () { clearTimeout(hoverTimer); });

    // Back / Forward: show that page in place (a change of #hash alone is ignored).
    let shownPage = location.pathname + location.search;
    const origPushState = history.pushState.bind(history);
    const origReplaceState = history.replaceState.bind(history);
    history.pushState = function (s, t, u) { origPushState(s, t, u); shownPage = location.pathname + location.search; };
    history.replaceState = function (s, t, u) { origReplaceState(s, t, u); shownPage = location.pathname + location.search; };
    window.addEventListener('popstate', function () {
      if (location.pathname + location.search === shownPage) return;
      const samePath = location.pathname === shownPage.split('?')[0];
      shownPage = location.pathname + location.search;
      // Same page, other ?page= or ?q= (e.g. Trip Records): the page may show it in
      // place, without a reload or a jump to the top.
      if (samePath && !document.dispatchEvent(new Event('pagestate', { cancelable: true }))) return;
      markNav(Array.from(document.querySelectorAll('.sidebar-nav .nav-link')).find(function (l) { return l.pathname === location.pathname; }));
      navigate(location.href, false);
    });
  } else {
    // No in-app switching (older browser): still show the loading bar on clicks.
    document.addEventListener('click', function (e) {
      const a = e.target.closest('a[href]');
      if (!a || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey ||
          a.target === '_blank' || a.hasAttribute('download') || a.getAttribute('href').startsWith('#') ||
          a.origin !== location.origin || a.dataset.bsToggle || /export|\.csv$/i.test(a.pathname)) return;
      startNav();
    });
  }

  // ---- Sidebar toggle (mobile) ----
  const sidebar = document.getElementById('sidebar');
  const toggleBtn = document.getElementById('sidebarToggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });
    document.addEventListener('click', function (e) {
      if (window.innerWidth <= 991 && sidebar.classList.contains('open')) {
        if (!sidebar.contains(e.target) && e.target !== toggleBtn && !toggleBtn.contains(e.target)) {
          sidebar.classList.remove('open');
        }
      }
    });
  }

  // ---- Notifications bell (real time): badge refreshes every 5s; staff get a
  // toast when a fuel request is approved/rejected, admins when a new request arrives.
  const notifBtn = document.getElementById('notifBtn');
  const notifList = document.getElementById('notifList');
  if (notifBtn && notifList) {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    let knownKeys = null;  // items already seen by this page (no toast for them)
    function setDot(count) {
      let dot = document.getElementById('notifDot');
      if (count > 0) {
        if (!dot) { dot = document.createElement('span'); dot.className = 'notif-dot'; dot.id = 'notifDot'; notifBtn.appendChild(dot); }
        dot.textContent = count;
      } else if (dot) { dot.remove(); }
    }
    const clearAllBtn = document.getElementById('notifClearAll');
    function renderList(items) {
      if (clearAllBtn) clearAllBtn.hidden = !items.length;
      if (!items.length) { notifList.innerHTML = '<div class="notif-empty text-muted small">No notifications right now.</div>'; return; }
      notifList.innerHTML = items.map(function (n) {
        const tone = n.status === 'rejected' ? 'bad' : (n.kind === 'decision' ? 'good' : 'info');
        return '<div class="notif-row" data-key="' + escapeHtml(n.key) + '">' +
          '<a class="notif-item notif-' + tone + (n.new ? ' is-new' : '') + '" href="' + escapeHtml(n.url) + '">' +
          '<div class="notif-item-icon"><i class="fa-solid ' + escapeHtml(n.icon) + '"></i></div>' +
          '<div><div class="notif-item-text">' + escapeHtml(n.text) + '</div>' +
          '<div class="notif-item-sub">' + escapeHtml(n.sub) + (n.time ? ' · ' + escapeHtml(n.time) : '') + '</div></div></a>' +
          '<button type="button" class="notif-remove" title="Remove this notification" aria-label="Remove notification">' +
          '<i class="fa-solid fa-xmark"></i></button></div>';
      }).join('');
    }
    // Remove one notification (x) or all of them; saved on the server, so it stays
    // removed after a reload and disappears from this user's other tabs/devices too.
    function applyNotifData(data) {
      if (!data) return;
      setDot(data.count);
      renderList(data.notifications);
      knownKeys = data.notifications.map(function (n) { return n.kind + ':' + n.id + ':' + (n.status || ''); });
    }
    function dismiss(path, body) {
      return fetch(path, { method: 'POST', body: body,
        headers: { 'Accept': 'application/json', 'X-CSRFToken': csrfMeta ? csrfMeta.content : '' } })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(applyNotifData)
        .catch(function () { pollNotifications(false); });
    }
    notifList.addEventListener('click', function (e) {
      const btn = e.target.closest('.notif-remove');
      if (!btn) return;
      e.preventDefault(); e.stopPropagation();
      const row = btn.closest('.notif-row');
      const body = new URLSearchParams({ key: row.dataset.key });
      row.classList.add('is-removing');
      setTimeout(function () { row.remove(); if (!notifList.querySelector('.notif-row')) renderList([]); }, 150);
      const dot = document.getElementById('notifDot');
      if (dot) setDot(Math.max((parseInt(dot.textContent, 10) || 1) - 1, 0));
      dismiss('/api/notifications/dismiss', body);
    });
    if (clearAllBtn) clearAllBtn.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      renderList([]); setDot(0);
      dismiss('/api/notifications/dismiss-all');
    });
    function pollNotifications(showToasts) {
      return fetch('/api/notifications', { headers: { 'Accept': 'application/json' } })
        .then(function (res) { return res.ok ? res.json() : null; })
        .then(function (data) {
          if (!data) return;
          setDot(data.count);
          renderList(data.notifications);
          // Sidebar counters (admin): pending fuel requests and pending sign-ups, on every page.
          [['pendingReqBadge', data.pending_requests], ['pendingBadge', data.pending_accounts]].forEach(function (b) {
            const el = document.getElementById(b[0]);
            if (el && b[1] !== undefined) { el.textContent = b[1]; el.hidden = !b[1]; }
          });
          const keys = data.notifications.map(function (n) { return n.kind + ':' + n.id + ':' + (n.status || ''); });
          if (knownKeys && showToasts) {
            data.notifications.forEach(function (n) {
              const key = n.kind + ':' + n.id + ':' + (n.status || '');
              if (knownKeys.indexOf(key) === -1 && typeof showToast === 'function') {
                showToast(n.text + (n.sub ? ' — ' + n.sub : ''), n.status === 'rejected' ? 'danger' : (n.kind === 'request' ? 'info' : 'success'));
              }
            });
          }
          knownKeys = keys;
        })
        .catch(function () { /* offline: retry on the next tick */ });
    }
    pollNotifications(false);
    shellInterval(function () { if (!document.hidden) pollNotifications(true); }, 5000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) pollNotifications(true); });
    notifBtn.addEventListener('shown.bs.dropdown', function () {
      pollNotifications(false).then(function () {
        // Opening the bell marks approvals/rejections as read.
        fetch('/api/notifications/seen', { method: 'POST', headers: { 'X-CSRFToken': csrfMeta ? csrfMeta.content : '' } })
          .then(function () { return pollNotifications(false); });
      });
    });
  }

  // ---- Print buttons (data-print): always print the latest data ----
  // Pages with live data define window.refreshBeforePrint(); the button waits
  // for it, then prints. Other pages reload with ?print=1 (fresh from the
  // server) and print as soon as they have loaded.
  function stampPrintTime() {
    const el = document.getElementById('printTime');
    if (el) el.textContent = new Date().toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'short' });
  }
  window.addEventListener('beforeprint', stampPrintTime);
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-print]');
    if (!btn) return;
    e.preventDefault();
    if (typeof window.refreshBeforePrint === 'function') {
      btn.disabled = true;
      const timeout = new Promise(function (resolve) { setTimeout(resolve, 6000); });
      Promise.race([Promise.resolve(window.refreshBeforePrint()).catch(function () {}), timeout])
        .then(function () { return new Promise(function (r) { setTimeout(r, 300); }); })  // let the DOM paint
        .then(function () { btn.disabled = false; stampPrintTime(); window.print(); });
    } else {
      const url = new URL(window.location.href);
      url.searchParams.set('print', '1');
      window.location.href = url.toString();
    }
  });
  if (new URLSearchParams(window.location.search).get('print') === '1') {
    const clean = new URL(window.location.href);
    clean.searchParams.delete('print');
    history.replaceState(null, '', clean.toString());
    window.addEventListener('load', function () {
      setTimeout(function () { stampPrintTime(); window.print(); }, 600);
    });
  }

  // ---- Real-time account sync (every page) ----
  // Keeps the top-bar name/role — and the Settings form when it has
  // no unsaved edits — in step with changes made in other tabs or devices,
  // and signs the user out if the account is deactivated.
  function syncField(id, value) {
    const el = document.getElementById(id);
    if (!el || document.activeElement === el) return;
    // Only overwrite fields the user hasn't edited.
    if (el.dataset.original === undefined || el.value === el.dataset.original) {
      el.value = value;
      el.dataset.original = value;
    }
  }
  function syncAccount() {
    if (document.hidden) return;
    fetch('/api/me', { headers: { 'Accept': 'application/json' } })
      .then(function (res) {
        if (res.status === 401) { window.location.href = '/login'; return null; }
        return res.ok ? res.json() : null;
      })
      .then(function (me) {
        if (!me) return;
        document.querySelectorAll('.user-name').forEach(function (el) { el.textContent = me.full_name; });
        document.querySelectorAll('.user-role').forEach(function (el) { el.textContent = me.role; });
        const initial = document.getElementById('topbarAvatarInitial');
        if (initial) initial.textContent = me.initial;
        if (document.getElementById('settingsFullName')) {
          syncField('settingsFullName', me.full_name);
          syncField('settingsPosition', me.role);
          syncField('settingsEmail', me.email);
          syncField('settingsUsername', me.username);
        }
      })
      .catch(function () { /* offline: try again on the next tick */ });
  }
  if (document.querySelector('.user-chip')) {
    shellInterval(syncAccount, 5000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) syncAccount(); });
  }

  initPage();
});

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

function showToast(message, category) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const colorMap = { success: 'text-bg-success', danger: 'text-bg-danger', error: 'text-bg-danger', warning: 'text-bg-warning', info: 'text-bg-primary' };
  const cls = colorMap[category] || 'text-bg-primary';
  const el = document.createElement('div');
  el.className = `toast align-items-center ${cls} border-0`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `<div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(el);
  const toast = new bootstrap.Toast(el, { delay: 4500 });
  toast.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

function showLoading(message) {
  let overlay = document.getElementById('globalSpinner');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'globalSpinner';
    overlay.className = 'spinner-overlay';
    overlay.innerHTML = `<div class="spinner-box">
        <div class="spinner-border" role="status"></div>
        <p id="globalSpinnerText">Processing...</p>
      </div>`;
    document.body.appendChild(overlay);
  }
  document.getElementById('globalSpinnerText').textContent = message;
  overlay.classList.add('active');
}

function hideLoading() {
  const overlay = document.getElementById('globalSpinner');
  if (overlay) overlay.classList.remove('active');
}

function confirmDelete(message) {
  return window.confirm(message || 'Are you sure you want to delete this record? This action cannot be undone.');
}

// ---------------------------------------------------------------------------
// Dates and times: always Philippine time (Asia/Manila), whatever time zone the
// viewer's device uses, matching the server and database.
// ---------------------------------------------------------------------------
const PH_TZ = 'Asia/Manila';
function phToday() {   // YYYY-MM-DD
  return new Intl.DateTimeFormat('en-CA', { timeZone: PH_TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

// "Add" forms start with today's date already filled in (still editable);
// edit forms keep the record's own values.
document.addEventListener('show.bs.modal', function (e) {
  const modal = e.target;
  if (!modal.id || !/^add/i.test(modal.id)) return;
  modal.querySelectorAll('input[type="date"]').forEach(function (el) { if (!el.value) el.value = phToday(); });
});

// ---------------------------------------------------------------------------
// Login <-> Sign Up switch. Leaving: the form fades out, the two glass shards
// light up, slip into the cut corners and glide to the middle, where they join
// as one mark. Arriving: the other page opens on that mark (its head hides the
// form first with auth-arriving), the card grows or shrinks from the old
// page's size to its own, then the halves split back to the corners and the
// form comes in row by row.
// ---------------------------------------------------------------------------
(function () {
  const frame = document.querySelector('.auth-frame');
  if (!frame) return;
  const card = frame.querySelector('.login-card');
  const root = document.documentElement;
  const calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SIZE_KEY = 'fleetfuel-auth-size';
  const later = function (ms, fn) { setTimeout(fn, ms); };

  // Two lights running around the card's edge, cut corners included. They are
  // moved with transform-only keyframes (head on the outline, tail turned along
  // it), so the browser never redraws the card for them. Rebuilt when the card
  // changes size, keeping each light where it was.
  const beamLights = Array.from(frame.querySelectorAll('.card-beam .beam'));
  let beamRuns = [], beamTimer = null;
  function runBeams() {
    if (!beamLights.length || calm || !card.animate) return;
    const w = card.offsetWidth, h = card.offsetHeight, e = 0.5;
    const c = parseFloat(getComputedStyle(card).getPropertyValue('--cut')) || 30;
    const pts = [[c, e], [w - e, e], [w - e, h - c], [w - c, h - e], [e, h - e], [e, c], [c, e]];
    // Keep the lights on the edge: right after a corner a tail would otherwise
    // stick out past it. The clip is the card's shape grown by o px.
    const o = 3, d = o * 0.414;
    beamLights[0].parentNode.style.clipPath = 'polygon(' + [[c - d, -o], [w + o, -o], [w + o, h - c + d], [w - c + d, h + o], [-o, h + o], [-o, c - d]]
      .map(function (p) { return p[0].toFixed(1) + 'px ' + p[1].toFixed(1) + 'px'; }).join(',') + ')';
    let total = 0, last = null;
    const segs = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      let angle = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
      if (last !== null) while (angle - last < -180) angle += 360;  // keep turning the same way round
      segs.push({ a: a, b: b, len: len, at: total, angle: angle });
      total += len;
      last = angle;
    }
    const done = beamRuns.map(function (r) { return r.currentTime || 0; });
    beamRuns.forEach(function (r) { r.cancel(); });
    beamRuns = beamLights.map(function (el, n) {
      const bw = el.offsetWidth, frames = [];
      const at = function (sg, d) { return [sg.a[0] + (sg.b[0] - sg.a[0]) * d / sg.len, sg.a[1] + (sg.b[1] - sg.a[1]) * d / sg.len]; };
      const key = function (offset, p, angle) {
        frames.push({ offset: offset / total, transform: 'translate(' + (p[0] - bw).toFixed(1) + 'px,' + (p[1] - 1).toFixed(1) + 'px) rotate(' + angle.toFixed(1) + 'deg)' });
      };
      // Along each side the light keeps that side's angle; it turns only in
      // the first few px after a corner.
      segs.forEach(function (sg, i) {
        const turn = Math.min(8, sg.len / 3);
        key(sg.at, sg.a, i === 0 ? sg.angle : segs[i - 1].angle);
        key(sg.at + turn, at(sg, turn), sg.angle);
        if (i === segs.length - 1) key(total, sg.b, sg.angle);
      });
      const run = el.animate(frames, { duration: 7000, iterations: Infinity, easing: 'linear' });
      run.currentTime = done[n] != null ? done[n] : n * 3500;
      return run;
    });
  }
  function beamSpeed(rate) { beamRuns.forEach(function (r) { r.playbackRate = rate; }); }
  runBeams();
  if (window.ResizeObserver) new ResizeObserver(function () { clearTimeout(beamTimer); beamTimer = setTimeout(runBeams, 120); }).observe(card);

  function leave(href) {
    if (calm) { location.href = href; return; }
    try {
      sessionStorage.setItem('fleetfuel-auth-switch', '1');
      sessionStorage.setItem(SIZE_KEY, JSON.stringify({ w: frame.offsetWidth, h: card.offsetHeight }));
    } catch (e) {}
    Array.from(card.children).forEach(function (el, i) { el.style.transitionDelay = (i * 35) + 'ms'; });
    frame.classList.add('is-leaving', 'shards-lit', 'shards-in');
    beamSpeed(3);
    later(380, function () { frame.classList.add('shards-center'); });
    later(880, function () { frame.classList.add('shards-pulse'); });
    later(1000, function () { location.href = href; });
  }

  // Card size: start at the previous page's size and ease into this one's.
  function morphFromPrevious() {
    let old = null;
    try { old = JSON.parse(sessionStorage.getItem(SIZE_KEY) || 'null'); sessionStorage.removeItem(SIZE_KEY); } catch (e) {}
    if (!old) return;
    const w = frame.offsetWidth, h = card.offsetHeight;
    if (Math.abs(old.w - w) < 2 && Math.abs(old.h - h) < 2) return;
    frame.style.maxWidth = old.w + 'px';
    card.style.height = old.h + 'px';
    void card.offsetWidth;
    const ease = '0.5s cubic-bezier(0.65, 0, 0.35, 1)';
    frame.style.transition = 'max-width ' + ease;
    card.style.transition = 'height ' + ease;
    later(60, function () { frame.style.maxWidth = w + 'px'; card.style.height = h + 'px'; });
    later(650, function () { frame.style.maxWidth = frame.style.transition = card.style.height = card.style.transition = ''; });
  }

  function arrive() {
    if (!root.classList.contains('auth-arriving')) return;
    const rows = Array.from(card.children);
    frame.classList.add('no-anim', 'shards-lit', 'shards-in', 'shards-center', 'is-leaving');
    beamSpeed(3);
    later(1000, function () { beamSpeed(1); });
    void frame.offsetWidth;  // the mark is already in the middle; no slide in
    frame.classList.remove('no-anim');
    root.classList.remove('auth-arriving');
    morphFromPrevious();
    later(560, function () { frame.classList.remove('shards-center'); });            // split to the cut corners
    later(980, function () { frame.classList.remove('shards-in', 'shards-lit'); });  // back outside, plain glass
    later(900, function () {
      rows.forEach(function (el, i) { el.style.transitionDelay = (i * 60) + 'ms'; });
      frame.classList.remove('is-leaving');
    });
    later(1900, function () { rows.forEach(function (el) { el.style.transitionDelay = ''; }); });
  }

  document.addEventListener('click', function (e) {
    const a = e.target.closest('.auth-switch a[href]');
    if (!a || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    if (frame.classList.contains('is-leaving')) return;  // already switching
    leave(a.href);
  });

  // Back button after a switch: show the form again instead of the empty card.
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) frame.classList.remove('is-leaving', 'shards-lit', 'shards-in', 'shards-center', 'shards-pulse');
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', arrive);
  else arrive();
})();
