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

// ---- Everything inside the page area that needs wiring up. Runs on the first
// load and again after every in-app page switch (on the new content). ----
function initPage() {
  // Tables on phones: each cell carries its column name (data-label), so
  // style.css can show every row as a card. Rows redrawn by the live refresh
  // are labelled again as they arrive.
  document.querySelectorAll('table.table-fleet').forEach(function (table) {
    const labels = Array.from(table.querySelectorAll('thead th')).map(function (th) { return th.textContent.trim(); });
    const label = function () {
      table.querySelectorAll('tbody tr').forEach(function (tr) {
        Array.from(tr.children).forEach(function (td, i) {
          if (!td.hasAttribute('colspan') && labels[i] && td.dataset.label !== labels[i]) td.dataset.label = labels[i];
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

  // Profile photo upload (Settings page)
  initAvatarControls();

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
      shownPage = location.pathname + location.search;
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
  // Keeps the top-bar name/role/photo — and the Settings form when it has
  // no unsaved edits — in step with changes made in other tabs or devices,
  // and signs the user out if the account is deactivated.
  function setAvatar(imgId, initialId, baseClass, url, initial) {
    const img = document.getElementById(imgId);
    const div = document.getElementById(initialId);
    const current = img || div;
    if (!current) return;
    if (url) {
      if (img) { if (img.getAttribute('src') !== url) img.src = url; return; }
      const el = document.createElement('img');
      el.id = imgId; el.className = baseClass + ' user-avatar-img'; el.src = url; el.alt = 'Profile photo';
      current.replaceWith(el);
    } else {
      if (div) { div.textContent = initial; return; }
      const el = document.createElement('div');
      el.id = initialId; el.className = baseClass; el.textContent = initial;
      current.replaceWith(el);
    }
  }
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
        setAvatar('topbarAvatarImg', 'topbarAvatarInitial', 'user-avatar', me.avatar_url, me.initial);
        if (document.getElementById('avatarPreview')) {
          const preview = document.getElementById('avatarPreview');
          if (me.avatar_url) {
            if (preview.tagName === 'IMG') { if (preview.getAttribute('src') !== me.avatar_url) preview.src = me.avatar_url; }
            else { const im = document.createElement('img'); im.id = 'avatarPreview'; im.className = 'avatar-preview'; im.src = me.avatar_url; im.alt = 'Profile photo'; preview.replaceWith(im); }
            showViewRemoveMenuItems();
          } else {
            if (preview.tagName === 'IMG') { const dv = document.createElement('div'); dv.id = 'avatarPreview'; dv.className = 'avatar-preview'; dv.textContent = me.initial; preview.replaceWith(dv); }
            else preview.textContent = me.initial;
            hideViewRemoveMenuItems();
          }
          syncField('settingsFullName', me.full_name);
          syncField('settingsEmail', me.email);
          const un = document.getElementById('settingsUsername'); if (un) un.value = me.username;
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

// ---- Profile photo (Settings page) ----
function initAvatarControls() {
  const avatarInput = document.getElementById('avatarInput');
  if (!avatarInput) return;
  const uploadPhotoBtn = document.getElementById('uploadPhotoBtn');
  if (uploadPhotoBtn) {
    uploadPhotoBtn.addEventListener('click', function () { avatarInput.click(); });
  }

  avatarInput.addEventListener('change', function () {
    const file = avatarInput.files[0];
    if (file) uploadAvatarFile(file);
    avatarInput.value = '';
  });

  // ---- Take Photo (webcam capture) ----
  const cameraModalEl = document.getElementById('cameraModal');
  const cameraVideo = document.getElementById('cameraVideo');
  const cameraCanvas = document.getElementById('cameraCanvas');
  const cameraError = document.getElementById('cameraError');
  const takePhotoBtn = document.getElementById('takePhotoBtn');
  const capturePhotoBtn = document.getElementById('capturePhotoBtn');
  let cameraStream = null;

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach(function (track) { track.stop(); });
      cameraStream = null;
    }
  }

  if (cameraModalEl && takePhotoBtn) {
    const cameraModal = new bootstrap.Modal(cameraModalEl);

    takePhotoBtn.addEventListener('click', function () {
      cameraError.textContent = '';
      cameraModal.show();
      // Browsers only allow the camera on HTTPS or localhost; over the office
      // network (http://<PC-IP>:5000) mediaDevices does not exist.
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        cameraError.textContent = 'The camera is only available when the system is opened on this computer ' +
          '(http://127.0.0.1:5000) or over HTTPS. Please use "Upload Photo" instead.';
        return;
      }
      navigator.mediaDevices.getUserMedia({ video: true })
        .then(function (stream) {
          cameraStream = stream;
          cameraVideo.srcObject = stream;
        })
        .catch(function () {
          cameraError.textContent = 'Could not access the camera. Check your browser/device permissions.';
        });
    });

    cameraModalEl.addEventListener('hidden.bs.modal', stopCamera);

    capturePhotoBtn.addEventListener('click', function () {
      if (!cameraStream) return;
      cameraCanvas.width = cameraVideo.videoWidth;
      cameraCanvas.height = cameraVideo.videoHeight;
      cameraCanvas.getContext('2d').drawImage(cameraVideo, 0, 0);
      cameraCanvas.toBlob(function (blob) {
        if (!blob) return;
        cameraModal.hide();
        uploadAvatarFile(new File([blob], 'camera-photo.jpg', { type: 'image/jpeg' }));
      }, 'image/jpeg', 0.92);
    });
  }

  // ---- See Profile Picture / Remove Profile Picture (event-delegated: these
  // menu items are only present in the DOM once a photo exists) ----
  const avatarDropdownMenu = document.getElementById('avatarDropdownMenu');
  const viewPhotoModalEl = document.getElementById('viewPhotoModal');
  if (avatarDropdownMenu) {
    avatarDropdownMenu.addEventListener('click', function (e) {
      if (e.target.closest('#viewPhotoBtn')) {
        const preview = document.getElementById('avatarPreview');
        if (!preview || preview.tagName !== 'IMG') return;
        document.getElementById('viewPhotoImg').src = preview.src;
        bootstrap.Modal.getOrCreateInstance(viewPhotoModalEl).show();  // reuse: no stacked backdrops
      } else if (e.target.closest('#removePhotoBtn')) {
        if (!window.confirm('Remove your profile picture?')) return;
        const csrfToken = document.getElementById('avatarCsrfToken').value;
        showLoading('Removing photo...');
        fetch('/settings/photo/remove', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
        })
          .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
          .then(function (result) {
            hideLoading();
            if (!result.ok || !result.data.success) {
              showToast((result.data && result.data.message) || 'Could not remove photo.', 'danger');
              return;
            }
            setAvatarToInitial();
            showToast('Profile photo removed.', 'success');
          })
          .catch(function () {
            hideLoading();
            showToast('Could not remove photo. Please try again.', 'danger');
          });
      }
    });
  }
}

function showViewRemoveMenuItems() {
  const menu = document.getElementById('avatarDropdownMenu');
  if (!menu || document.getElementById('viewPhotoItem')) return;
  menu.insertAdjacentHTML('beforeend',
    '<li id="viewPhotoItem"><button type="button" class="dropdown-item" id="viewPhotoBtn"><i class="fa-regular fa-eye me-2"></i>See Profile Picture</button></li>' +
    '<li id="removePhotoItem"><button type="button" class="dropdown-item text-danger" id="removePhotoBtn"><i class="fa-solid fa-trash me-2"></i>Remove Profile Picture</button></li>'
  );
}

function hideViewRemoveMenuItems() {
  ['viewPhotoItem', 'removePhotoItem'].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
}

function setAvatarToInitial() {
  const initialLetter = (document.querySelector('.user-name') ? document.querySelector('.user-name').textContent.trim().charAt(0) : 'U').toUpperCase();
  [['avatarPreview', 'avatarPreview'], ['topbarAvatarImg', 'topbarAvatarInitial']].forEach(function (pair) {
    const el = document.getElementById(pair[0]);
    if (!el || el.tagName !== 'IMG') return;
    const div = document.createElement('div');
    div.id = pair[1];
    div.className = el.className.replace('user-avatar-img', '').trim();
    div.textContent = initialLetter;
    el.replaceWith(div);
  });
  hideViewRemoveMenuItems();
}

function uploadAvatarFile(file) {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    showToast('Only PNG, JPG, or WEBP images are allowed.', 'danger');
    return;
  }
  if (file.size > 3 * 1024 * 1024) {
    showToast('Image must be smaller than 3 MB.', 'danger');
    return;
  }

  const csrfToken = document.getElementById('avatarCsrfToken').value;
  const formData = new FormData();
  formData.append('photo', file);
  formData.append('csrf_token', csrfToken);

  showLoading('Uploading photo...');
  fetch('/settings/photo', { method: 'POST', body: formData })
    .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
    .then(function (result) {
      hideLoading();
      if (!result.ok || !result.data.success) {
        showToast(result.data.message || 'Could not upload photo.', 'danger');
        return;
      }
      const url = result.data.url;
      ['avatarPreview', 'topbarAvatarImg'].forEach(function (id) {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.tagName === 'IMG') {
          el.src = url;
        } else {
          const img = document.createElement('img');
          img.id = el.id;
          img.className = el.className + ' user-avatar-img';
          img.src = url;
          img.alt = 'Profile photo';
          el.replaceWith(img);
        }
      });
      const initial = document.getElementById('topbarAvatarInitial');
      if (initial) {
        const img = document.createElement('img');
        img.id = 'topbarAvatarImg';
        img.className = 'user-avatar user-avatar-img';
        img.src = url;
        img.alt = 'Profile photo';
        initial.replaceWith(img);
      }
      showViewRemoveMenuItems();
      showToast('Profile photo updated.', 'success');
    })
    .catch(function () {
      hideLoading();
      showToast('Could not upload photo. Please try again.', 'danger');
    });
}

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

// Live clock in the top bar, ticking every second.
(function () {
  const t = document.getElementById('liveClockTime');
  const d = document.getElementById('liveClockDate');
  if (!t || !d) return;
  const timeFmt = new Intl.DateTimeFormat('en-US', { timeZone: PH_TZ, hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
  const dateFmt = new Intl.DateTimeFormat('en-US', { timeZone: PH_TZ, weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  function tick() { const now = new Date(); t.textContent = timeFmt.format(now); d.textContent = dateFmt.format(now); }
  tick();
  shellInterval(tick, 1000);
})();

// "Add" forms start with today's date already filled in (still editable);
// edit forms keep the record's own values.
document.addEventListener('show.bs.modal', function (e) {
  const modal = e.target;
  if (!modal.id || !/^add/i.test(modal.id)) return;
  modal.querySelectorAll('input[type="date"]').forEach(function (el) { if (!el.value) el.value = phToday(); });
});
