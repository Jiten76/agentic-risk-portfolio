// Interaction-matrix runner — re-executes qa/interaction_matrix.json's checks on
// the REAL DOM (round-16 external finding: "88/88 is only as strong as the
// unshipped assertion harness" — this ships the harness).
//
// Run: open a workbench (index.html) or a read (read.html) in a SIZED browser
// window (geometric checks are meaningless at 0×0 — check window.innerWidth
// first), paste this whole file in the console, read the table it prints.
// Every row carries its EVIDENCE (states, geometry, text-hash values), not
// just a verdict.
(function () {
  var rows = [];
  function row(check, pass, evidence) { rows.push({ check: check, pass: !!pass, evidence: evidence }); }
  function djb2(s) { var h = 5381; for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h; }
  if (window.innerWidth < 100) { console.warn('VIEWPORT ' + window.innerWidth + 'px — size the window first; geometric checks need a real viewport.'); return; }
  // round-18: JS errors thrown DURING the driven interactions are themselves a failure
  var jsErrors = [];
  window.addEventListener('error', function (e) { jsErrors.push(String(e.message).slice(0, 120)); });

  var projEl = document.getElementById('projection-source');
  var P = projEl ? JSON.parse(projEl.textContent) : null;

  if (P && P.ia && document.getElementById('spine')) {
    // ── workbench: role × node sweep ──
    var ia = P.ia;
    Object.keys(ia.paths).forEach(function (role) {
      var seen = {};
      ia.paths[role].forEach(function (node) {
        location.hash = 'role=' + role + '&node=' + node;
        window.dispatchEvent(new HashChangeEvent('hashchange'));
        var stateOk = document.body.dataset.role === role && document.body.dataset.iaNode === node;
        var vis = [];
        document.querySelectorAll('[data-node]').forEach(function (s) {
          if (s.getBoundingClientRect().height > 0) vis.push(s.getAttribute('data-node'));
        });
        var scenarioMode = !document.querySelector('[data-node]');
        var onlyNode = scenarioMode || (vis.length > 0 && vis.every(function (v) { return v === node; }));
        var sh = (document.querySelector('.step-header') || {}).textContent || '';
        var nodeDef = ia.nodes.filter(function (n) { return n.id === node; })[0] || {};
        var shOk = sh.length > 40 && sh.toLowerCase().indexOf(String(nodeDef.label || node).toLowerCase().slice(0, 8)) >= 0;
        var txt = '';
        if (scenarioMode) { txt = ((document.querySelector('.obs-title') || {}).textContent || '') + ((document.querySelector('.obs-stage-cap') || {}).textContent || ''); }
        else document.querySelectorAll('[data-node]').forEach(function (s) { if (s.getBoundingClientRect().height > 0) txt += s.textContent; });
        var th = djb2(txt);
        var distinct = !(th in seen); seen[th] = node;
        row(role + '·' + node, stateOk && onlyNode && shOk && distinct,
            { state: document.body.dataset.role + '/' + document.body.dataset.iaNode, visibleNodes: scenarioMode ? 'scenario-mode' : vis.join(','), textHash: th, headerLen: sh.length });
      });
    });
    // role-tiered affordances: leadership hides operator chrome, other roles keep it
    location.hash = 'role=leadership&node=' + ia.paths.leadership[0];
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    function h(sel) { var e = document.querySelector(sel); return e ? e.getBoundingClientRect().height : null; }
    var lh = { kbd: h('.kbd-hint'), verb: h('.verb-btn'), rail: h('.rail') };
    location.hash = 'role=engineering&node=' + ia.paths.engineering[0];
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    var eh = { kbd: h('.kbd-hint'), verb: h('.verb-btn'), rail: h('.rail') };
    var tiered = [lh.kbd, lh.verb, lh.rail].every(function (v) { return v === null || v === 0; });
    var kept = [eh.kbd, eh.verb, eh.rail].some(function (v) { return v > 0; });
    var noChrome = [eh.kbd, eh.verb, eh.rail].every(function (v) { return v === null || v === 0; });
    // apps with no operator chrome for ANY role (hv retired its rail wholesale)
    // pass vacuously — the assertion is "leadership never sees MORE than engineering".
    row('role tiering: leadership hides operator chrome, engineering keeps it',
        tiered && (kept || noChrome),
        { leadership: lh, engineering: eh, vacuous: noChrome && !kept });
    // round-22: the decision edge — leadership CTA (number → docket in one click)
    // + role-switch position preservation. Apps without a .lead-cta in the DOM
    // pass the CTA rows vacuously (the CTA is a rac leadership device).
    var ctaEl = document.querySelector('.lead-cta');
    if (ctaEl) {
      location.hash = 'role=leadership&node=' + ia.paths.leadership[0];
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      var ctaLead = h('.lead-cta') > 0;
      var ctaDollar = /\$[\d.]+[MBK]/.test(ctaEl.textContent);
      ctaEl.click();
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      var ctaRoutes = document.body.dataset.iaNode === 'docket';
      location.hash = 'role=engineering&node=' + ia.paths.engineering[0];
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      var ctaEng = h('.lead-cta');
      row('leadership CTA: visible with $ under leadership, click routes to docket, hidden for engineering',
          ctaLead && ctaDollar && ctaRoutes && (ctaEng === null || ctaEng === 0),
          { leadershipH: ctaLead, dollar: ctaDollar, landedOn: ctaRoutes ? 'docket' : document.body.dataset.iaNode, engineeringH: ctaEng });
    } else {
      row('leadership CTA (no .lead-cta by design on this app)', true, { vacuousCta: true });
    }
    // round-24 (external finding, Claude: interaction-state-dependent rendering
    // defeats every static rendered-ness check): leaves that render only under
    // a filter or selection state get DRIVEN rows — the runner walks the state
    // and asserts the number appears. Apps without these controls pass vacuously.
    var regNode = (ia.paths.audit || ia.paths.basic || []).filter(function (n) { return n === 'regulation'; })[0];
    var tglEl = document.querySelector('[data-target="reg-filter-toggle"]');
    if (regNode && tglEl) {
      location.hash = 'role=audit&node=regulation';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      var regBox = document.querySelector('[data-target="regulation-residual"]');
      var allRegs = (P.regulation_residual || {}).by_regulation || [];
      var styleRow = allRegs.filter(function (r) { return /ILLUSTRATIVE|contractual/.test(r.applicability || ''); })[0];
      var styleUsd = styleRow ? '$' + (styleRow.residual_p95 / 1e6).toFixed(1) + 'M' : null;
      // detect the ROW structurally — a span whose text is EXACTLY the reg_id
      // exists only in the row list. Substring probes false-fired TWICE here
      // (reg_id also lives in the perimeter statuses; the citation also lives
      // in the always-rendered headline) — partial probes, confident wrongness.
      function rowPresent(rid) {
        return Array.prototype.some.call(regBox.querySelectorAll('span'),
          function (s) { return s.textContent.trim() === rid; });
      }
      var defShowsAll = !!styleRow && rowPresent(styleRow.reg_id)
        && regBox.textContent.indexOf(styleUsd) >= 0;
      document.querySelector('[data-target="reg-filter-toggle"]').click();
      var filteredHides = !!styleRow && !rowPresent(styleRow.reg_id);
      document.querySelector('[data-target="reg-filter-toggle"]').click();
      var restored = !!styleRow && rowPresent(styleRow.reg_id);
      row('applicability filter: style-mapped row + its $ render by DEFAULT, hide under binding-only, return on toggle',
          defShowsAll && filteredHides && restored,
          { styleRow: styleRow && styleRow.reg_id, dollar: styleUsd, defShowsAll: defShowsAll, filteredHides: filteredHides, restored: restored });
    } else {
      row('applicability filter (no reg filter on this app by design)', true, { vacuousRegFilter: true });
    }
    var pselEl = document.querySelector('[data-target="perimeter-sel"]');
    if (pselEl) {
      var ppM = (P.regulation_residual || {}).perimeter_profiles || {};
      var profs = ppM.profiles || [];
      var topReg = ((P.regulation_residual || {}).by_regulation || [])[0] || {};
      var perOk = profs.length > 0, perEv = {};
      profs.forEach(function (pr) {
        pselEl = document.querySelector('[data-target="perimeter-sel"]');  // re-render replaces the node
        pselEl.value = pr.profile_id;
        pselEl.dispatchEvent(new Event('change', { bubbles: true }));
        var sum = document.querySelector('[data-target="perimeter-summary"]');
        var box = document.querySelector('[data-target="regulation-residual"]');
        var usd = '$' + (pr.in_perimeter_residual_p95 / 1e6).toFixed(1) + 'M';
        var ok = sum && sum.textContent.indexOf(usd) >= 0;
        // round-26 (external, Claude — MODERATE: state-stale conclusion): the
        // section HEADLINE must re-derive with the selected charter — the
        // charter's own share for non-default states, the portfolio top-regime
        // line when the default state is restored.
        var headOk = pr.profile_id === ppM.default
          ? box.textContent.indexOf(topReg.share_of_portfolio_p95_pct + '%') >= 0
          : (box.textContent.indexOf(pr.share_of_portfolio_p95_pct + '%') >= 0
             && box.textContent.indexOf(pr.label) >= 0);
        perEv[pr.profile_id] = { expect: usd, rendered: !!ok, headlineStateAware: !!headOk };
        perOk = perOk && ok && headOk;
      });
      // restore the default state so later fingerprint-sensitive checks see it
      pselEl = document.querySelector('[data-target="perimeter-sel"]');
      pselEl.value = ppM.default;
      pselEl.dispatchEvent(new Event('change', { bubbles: true }));
      row('perimeter selector: every profile renders ITS in-perimeter $ AND the headline re-derives with the state',
          perOk, perEv);
    } else {
      row('perimeter selector (no perimeter selector on this app by design)', true, { vacuousPerimeter: true });
    }
    // role-switch keeps your place when the node exists on the new path
    var shared = ia.paths.leadership.filter(function (n) { return ia.paths.engineering.indexOf(n) >= 0; })[0];
    if (shared) {
      location.hash = 'role=leadership&node=' + shared;
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      var rsel = document.getElementById('spine-role-sel');
      rsel.value = 'engineering';
      rsel.dispatchEvent(new Event('change', { bubbles: true }));
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      row('role switch preserves the current node when it exists on the new path',
          document.body.dataset.role === 'engineering' && document.body.dataset.iaNode === shared,
          { sharedNode: shared, landed: document.body.dataset.role + '/' + document.body.dataset.iaNode });
    }
    // map + Escape
    document.getElementById('spine-map-btn').click();
    var ov = document.getElementById('ia-map');
    var opened = ov && ov.style.display !== 'none' && ov.getBoundingClientRect().height > 100;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    row('map open → Escape close', opened && ov.style.display === 'none', { openedHeight: opened });
    // read backlink — r43: the read is the workbench's closing chapter now,
    // so the spine link must jump to the story NODE, not a separate page
    var rd = document.querySelector('.spine-read');
    row('spine carries ↞ the read link to the story chapter', rd && rd.getBoundingClientRect().height > 0 && /node=story$/.test(rd.getAttribute('href')), { href: rd && rd.getAttribute('href') });
    // a11y (round-19, class-16 standing gate): step semantics, modal semantics, focus round-trip
    var curPill = document.querySelector('.spine-node[aria-current="step"]');
    row('a11y: active spine pill carries aria-current=step', !!curPill, { pill: curPill && curPill.getAttribute('data-spine') });
    var shEl = document.querySelector('.step-header');
    row('a11y: step header is a polite live region', shEl && shEl.getAttribute('aria-live') === 'polite', { ariaLive: shEl && shEl.getAttribute('aria-live') });
    document.getElementById('spine-map-btn').click();
    var ov2 = document.getElementById('ia-map');
    var modalOk = ov2.getAttribute('role') === 'dialog' && ov2.getAttribute('aria-modal') === 'true';
    var focusIn = document.activeElement && document.activeElement.id === 'ia-map-close';
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    var focusBack = document.activeElement && document.activeElement.id === 'spine-map-btn';
    row('a11y: map is aria-modal dialog; focus enters on open and returns on Escape',
        modalOk && focusIn && focusBack, { modal: modalOk, focusIn: focusIn, focusBack: focusBack });
  } else if (document.getElementById('act-1')) {
    // ── read page: chapters / keys / live hash ──
    // r38: the chapter count is DISCOVERED, not assumed — the journey page is a
    // legitimate one-chapter surface (its stage lives outside the accordion) and
    // the runner must drive what exists, not what it remembers.
    var actIds = [];
    for (var ai = 1; ai <= 9; ai++) if (document.getElementById('act-' + ai)) actIds.push(ai);
    function openStates() {
      return actIds.map(function (i) {
        var a = document.getElementById('act-' + i);
        return a && a.classList.contains('open') && a.querySelector('.act-body').getBoundingClientRect().height > 0 ? 1 : 0;
      }).join('');
    }
    var wantState = function (n) { return actIds.map(function (i) { return i === n ? 1 : 0; }).join(''); };
    actIds.slice().reverse().forEach(function (n) {
      document.querySelector('#act-' + n + ' .act-head').click();
      row('chapter click → ' + n, openStates() === wantState(n), { open: openStates() });
    });
    var keyN = actIds[actIds.length > 1 ? 1 : 0];
    document.dispatchEvent(new KeyboardEvent('keydown', { key: String(keyN), bubbles: true }));
    row('key ' + keyN + ' opens chapter ' + keyN, openStates() === wantState(keyN), { open: openStates() });
    var hashN = actIds[actIds.length - 1];
    location.hash = 'act=' + hashN; window.dispatchEvent(new HashChangeEvent('hashchange'));
    row('#act=' + hashN + ' live hash → chapter ' + hashN, openStates() === wantState(hashN), { open: openStates() });
    var cvAct = actIds.length > 1 ? 2 : 1;
    var cv = document.querySelector('#act-' + cvAct + ' canvas') || document.querySelector('canvas');
    if (cv) row('a canvas device is initialized', cv.width > 10, { canvasWidth: cv.width });
    else row('chapter device present (no canvas by design — CSS device)', !!document.querySelector('#act-' + cvAct + '-body *'), { vacuousCanvas: true });
    var wb = document.querySelector('.masthead .wb-link') || document.querySelector('.masthead a');
    row('masthead carries a navigation link', wb && wb.getBoundingClientRect().height > 0, { href: wb && wb.getAttribute('href') });
    // a11y (round-19): accordion semantics track the open chapter
    var expOk = actIds.every(function (i) {
      var hd = document.querySelector('#act-' + i + ' .act-head');
      var open = document.getElementById('act-' + i).classList.contains('open');
      return hd && hd.getAttribute('aria-expanded') === String(open) && hd.getAttribute('aria-controls') === 'act-' + i + '-body';
    });
    row('a11y: chapter heads carry aria-expanded/aria-controls in sync', expOk, {});
    // round-18 (the atg glob-bug CLASS, gated class-wide): the read must RENDER
    // its own sealed projection — period in the title, and a headline count or
    // dollar from meta/exposure visible in the page text.
    if (P) {
      var period = (P.meta || {}).period || '';
      row('read renders its own projection: period in title', period && document.title.indexOf(period) >= 0, { period: period, title: document.title });
      var probe = null, counts = (P.meta || {}).counts || {};
      if ((P.exposure || {}).portfolio_total) probe = '$' + (P.exposure.portfolio_total.p95_usd / 1e6).toFixed(1) + 'M';
      else if (counts.findings_total) probe = counts.findings_total + ' findings';
      else if (counts.events_total) probe = String(counts.events_total);
      row('read renders its own projection: headline value in page', probe && document.body.textContent.indexOf(probe) >= 0, { probe: probe });
    }
  } else {
    console.warn('Not a grammar surface (no ia spine, no read chapters) — nothing to run.');
    return;
  }

  // universal: the page must never scroll horizontally, and the driven
  // interactions must not have thrown (round-14 mobile class + silent-JS class)
  row('no horizontal document overflow at this viewport',
      document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2,
      { scrollWidth: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth });
  row('zero JS errors during the driven run', jsErrors.length === 0, { errors: jsErrors.slice(0, 5) });
  var fails = rows.filter(function (r) { return !r.pass; });
  console.table(rows.map(function (r) { return { check: r.check, pass: r.pass, evidence: JSON.stringify(r.evidence) }; }));
  console.log((rows.length - fails.length) + '/' + rows.length + ' PASS' + (fails.length ? ' — FAILURES ABOVE' : ''));
  window.__matrixRows = rows;
})();
