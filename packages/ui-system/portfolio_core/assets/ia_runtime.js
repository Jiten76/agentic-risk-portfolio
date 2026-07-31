/* ia_runtime — the platform grammar, shared (spec reviews/ia_stage_a_role_spine.md v2.2).
 * Spine (role drop-down + one-line node pills + map overlay + copy-link),
 * step header with panel-at-a-time sub-walker, hash router (#role=X&node=Y),
 * canonical mode (&canonical expands everything — the C26 comparison state).
 * Activates ONLY when the embedded projection carries an `ia` block.
 * NO DOM reordering; roles re-sequence, never re-value. */
(function () {
  'use strict';
  var projScript = document.getElementById('projection-source');
  if (!projScript) return;
  var P = {};
  try { P = JSON.parse(projScript.textContent || '{}'); } catch (e) { return; }
  var IA = P.ia;
  if (!IA || !document.getElementById('spine')) return;
  var IA_NODES = {}; (IA.nodes || []).forEach(function (n) { IA_NODES[n.id] = n; });
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
  function iaHash() {
    var h = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
      var q = kv.split('='); if (q[0]) h[q[0]] = decodeURIComponent(q[1] || '');
    });
    return h;
  }
  function iaState() {
    var h = iaHash();
    var role = (IA.paths && IA.paths[h.role]) ? h.role : (IA.default_role || 'basic');
    var path = IA.paths[role] || [];
    var node = (h.node && IA_NODES[h.node]) ? h.node : path[0];
    return { role: role, node: node, path: path, canonical: ('canonical' in h) };
  }
  function iaGo(role, node) { location.hash = 'role=' + role + (node ? '&node=' + node : ''); }
  function actName(id) {
    var a = (IA.acts || []).filter(function (x) { return x.id === id; })[0];
    return a ? a.name : id;
  }
  function renderSpine(st) {
    var el = document.getElementById('spine');
    var html = '<label class="spine-role">viewing as <select id="spine-role-sel" aria-label="Choose your lens">'
      + Object.keys(IA.paths).map(function (r) {
          return '<option value="' + r + '"' + (r === st.role ? ' selected' : '') + '>' + r + '</option>';
        }).join('')
      + '</select></label>';
    st.path.forEach(function (nid, i) {
      var n = IA_NODES[nid]; if (!n) return;
      html += '<button type="button" class="spine-node" data-spine="' + nid + '" aria-pressed="' + (nid === st.node) + '"' + (nid === st.node ? ' aria-current="step"' : '') + ' title="' + esc(n.beat + ' · ' + actName(n.act) + ' — ' + (n.headline || '')) + '">'
        + '<span class="spine-num">' + (i + 1) + '</span><span class="spine-label">' + esc(n.label) + '</span></button>';
    });
    html += '<button type="button" class="spine-map-btn" id="spine-map-btn" aria-haspopup="dialog" title="the whole argument, mapped">map ⌘</button>'
      + '<button type="button" class="spine-copy" id="spine-copy" title="copy a fully-qualified link to this view">⧉ link</button>'
      ;  // r43: the read pages folded into the workbenches — no separate page to link
    el.innerHTML = html;
    document.getElementById('spine-role-sel').addEventListener('change', function () {
      // round-22: position survives a role switch when the node exists on the
      // new path (re-sequence, don't reset); otherwise the new path's start.
      var cur = iaState().node;
      iaGo(this.value, (IA.paths[this.value] || []).indexOf(cur) >= 0 ? cur : null);
    });
    el.querySelectorAll('.spine-node').forEach(function (b) {
      b.addEventListener('click', function () { iaGo(st.role, b.dataset.spine); });
    });
    document.getElementById('spine-map-btn').addEventListener('click', function () { openIaMap(iaState(), true); });
    document.getElementById('spine-copy').addEventListener('click', function () {
      var url = location.origin + location.pathname + '#role=' + st.role + '&node=' + st.node;
      // r53 (external review): clipboard write can be DENIED (headless, enterprise
      // policy) — an unhandled rejection is a page error; fall back to a prompt
      // the user can copy from, and never let the denial escape.
      var fallback = function () { try { window.prompt('copy the link:', url); } catch (e) { } };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).catch(fallback);
      } else { fallback(); }
    });
  }
  function openIaMap(st, show) {
    var ov = document.getElementById('ia-map');
    if (!ov) {
      ov = document.createElement('div'); ov.id = 'ia-map'; ov.className = 'ia-map';
      ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-label', 'Argument map'); ov.setAttribute('aria-modal', 'true');
      document.body.appendChild(ov);
    }
    var beats = [];
    (IA.nodes || []).forEach(function (n) { if (beats.indexOf(n.beat) < 0) beats.push(n.beat); });
    var html = '<div class="ia-map-inner"><div class="ia-map-head"><span><b>the argument, mapped</b> — ' + esc(IA.thesis || '') + '</span>'
      + '<button id="ia-map-close" type="button">close ✕</button></div>';
    beats.forEach(function (b) {
      html += '<div class="ia-map-beat"><span>' + esc(b) + '</span>';
      (IA.nodes || []).forEach(function (n) {
        if (n.beat !== b) return;
        var onPath = st.path.indexOf(n.id) >= 0;
        html += '<button type="button" class="ia-map-node' + (onPath ? ' on-path' : '') + (n.id === st.node ? ' here' : '') + '" data-mapnode="' + n.id + '">'
          + '<b>' + esc(n.label) + '</b><span>' + esc(n.headline || '') + '</span></button>';
      });
      html += '</div>';
    });
    html += '<div class="ia-map-acts">the acts live on: '
      + (IA.acts || []).map(function (a) { return '<span><b>' + esc(a.name) + '</b> — ' + esc(a.desc) + '</span>'; }).join(' · ')
      + '</div></div>';
    ov.innerHTML = html; ov.style.display = show ? 'flex' : 'none';
    function closeMap() {
      ov.style.display = 'none';
      var mb = document.getElementById('spine-map-btn');
      if (mb) mb.focus();
    }
    document.getElementById('ia-map-close').addEventListener('click', closeMap);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && ov.style.display !== 'none') closeMap();
    });
    if (show) { var cb = document.getElementById('ia-map-close'); if (cb) cb.focus(); }
    ov.querySelectorAll('.ia-map-node').forEach(function (b) {
      b.addEventListener('click', function () { ov.style.display = 'none'; iaGo(st.role, b.dataset.mapnode); });
    });
  }
  var subIdx = 0, subNode = null;
  function subUnits(nodeId) {
    var secs = Array.prototype.slice.call(document.querySelectorAll('[data-node="' + nodeId + '"]'));
    // multi-section node (rac-style): the section is the walk unit.
    if (secs.length !== 1) return { mode: 'section', units: secs, secs: secs };
    // single-section node (atg-style): walk the section's panel children.
    var kids = Array.prototype.slice.call(secs[0].children).filter(function (el) {
      return el.hasAttribute('data-target') || el.querySelector('[data-target]');
    });
    if (kids.length < 2) return { mode: 'section', units: secs, secs: secs };
    return { mode: 'child', units: kids, secs: secs };
  }
  function applySub(st) {
    if (st.canonical) return;
    if (subNode !== st.node) { subNode = st.node; subIdx = 0; }
    var su = subUnits(st.node);
    var secs = su.units;
    if (subIdx >= secs.length) subIdx = 0;
    if (su.mode === 'section') {
      secs.forEach(function (s, i) { s.classList.toggle('sub-on', i === subIdx); });
    } else {
      su.secs[0].classList.add('sub-on');
      secs.forEach(function (s, i) { s.classList.toggle('sub-hide', i !== subIdx); });
    }
    var sw = document.getElementById('sub-walker');
    if (!sw) return;
    if (secs.length < 2) { sw.style.display = 'none'; return; }
    sw.style.display = '';
    var cur = secs[subIdx];
    var tgt = cur.querySelector('[data-target]');
    var cap = (tgt && (IA.headlines || {})[tgt.getAttribute('data-target')]) ||
      (cur.querySelector('.atg-panel-eyebrow, .section-eyebrow') ? cur.querySelector('.atg-panel-eyebrow, .section-eyebrow').textContent : '');
    sw.innerHTML = '<button type="button" class="sub-btn" id="sub-prev">◂</button>'
      + '<span class="sub-count">PANEL ' + (subIdx + 1) + ' / ' + secs.length + '</span>'
      + '<span class="sub-cap">' + esc(cap) + '</span>'
      + '<button type="button" class="sub-btn" id="sub-next">▸</button>';
    document.getElementById('sub-prev').addEventListener('click', function () {
      if (subIdx > 0) { subIdx--; applySub(iaState()); }
      else { var i2 = st.path.indexOf(st.node); if (i2 > 0) { subIdx = 0; iaGo(st.role, st.path[i2 - 1]); } }
    });
    document.getElementById('sub-next').addEventListener('click', function () {
      if (subIdx < secs.length - 1) { subIdx++; applySub(iaState()); }
      else { var i2 = st.path.indexOf(st.node); if (i2 < st.path.length - 1) { subIdx = 0; iaGo(st.role, st.path[i2 + 1]); } }
    });
  }
  function renderStepHeader(st) {
    var sh = document.getElementById('step-header');
    if (!sh) {
      sh = document.createElement('div');
      sh.id = 'step-header'; sh.className = 'step-header';
      sh.setAttribute('aria-live', 'polite');
      var first = document.querySelector('[data-node]') ||
        document.querySelector('main.panel section, .workspace section');
      if (!first) return;
      first.parentNode.insertBefore(sh, first);
    }
    var n = IA_NODES[st.node] || {};
    var i = st.path.indexOf(st.node);
    var prev = i > 0 ? IA_NODES[st.path[i - 1]] : null;
    var next = i >= 0 && i < st.path.length - 1 ? IA_NODES[st.path[i + 1]] : null;
    sh.innerHTML = '<div class="step-kicker">step ' + (i + 1) + ' of ' + st.path.length + ' · ' + esc(n.beat || '') + ' · ' + esc(actName(n.act || '')) + '</div>'
      + '<div class="step-row"><h2 class="step-title">' + esc(n.label || '') + '</h2>'
      + '<span class="step-nav">'
      + (prev ? '<button type="button" class="step-btn" data-step="' + st.path[i - 1] + '">◂ ' + esc(prev.label) + '</button>' : '')
      + (next ? '<button type="button" class="step-btn" data-step="' + st.path[i + 1] + '">' + esc(next.label) + ' ▸</button>' : '')
      + '</span></div>'
      + '<p class="step-headline">' + esc(n.headline || '') + '</p>'
      + '<div class="sub-walker" id="sub-walker"></div>';
    sh.querySelectorAll('.step-btn').forEach(function (b) {
      b.addEventListener('click', function () { iaGo(st.role, b.dataset.step); });
    });
  }
  var iaBooted = false;
  function scrollToStep() {
    var doScroll = function () {
      var s = document.getElementById('step-header');
      if (!s) return;
      var y = s.getBoundingClientRect().top + window.scrollY - 84;
      window.scrollTo(0, Math.max(0, y));
    };
    doScroll();
    setTimeout(doScroll, 80);
  }
  function applyIa() {
    var st = iaState();
    document.body.dataset.role = st.role;
    document.body.dataset.iaNode = st.node || '';
    var n = IA_NODES[st.node] || {};
    if (n.act) document.body.dataset.act = n.act;
    if (st.canonical) document.body.setAttribute('data-canonical', '1');
    else document.body.removeAttribute('data-canonical');
    document.querySelectorAll('[data-node]').forEach(function (s) {
      s.classList.toggle('node-on', st.canonical || s.getAttribute('data-node') === st.node);
    });
    renderStepHeader(st);
    applySub(st);
    renderSpine(st);
    // scenario mode (hv): no [data-node] sections — the node IS the domain;
    // hand selection to the domain renderer (same hook the rail used)
    if (!document.querySelector('[data-node]') && window.PortfolioDomain && window.PortfolioDomain.onDomainChange) {
      window.PortfolioDomain.onDomainChange(st.node);
    }
    if ((iaBooted || iaHash().node) && !st.canonical) scrollToStep();
    iaBooted = true;
  }
  openIaMap(iaState(), false);  // acts legend always in the DOM (C26f)
  window.addEventListener('hashchange', applyIa);
  applyIa();
})();
