/* hypervelocity-risk-sim — domain render functions (render-from-data).
 *
 * Registers window.PortfolioDomain with the shared runtime. Owns ONLY the
 * hypervelocity surfaces: the scenario rail, the persistent scenario hero, and the
 * OBSERVATORY — an animated incident-flow graph driven by the projection's real
 * per-event telemetry. Every value is read from the embedded projection via ctx
 * (d.events / d.kris_fired / d.comparison) — no hardcoded telemetry literal, so
 * first paint cannot drift.
 */
(function () {
  "use strict";

  function build(ctx) {
    var P = ctx.PROJECTION || {};
    var meta = P.meta || {};
    var domains = P.domains || {};
    var ids = meta.domain_ids || Object.keys(domains);
    var current = ids[0];

    var esc = ctx.esc;

    // ── provenance-aware value helpers ──
    function val(w) { return (w && typeof w === "object" && "value" in w) ? w.value : w; }
    function status(w) { return (w && w.provenance && w.provenance.source_status) || ""; }
    var PROV_SHORT = {
      real_query_synthesized_data: "counted", illustrative: "illustrative",
      published_standard: "standard", derived: "derived", absent: "absent"
    };
    function badge(s) {
      return s ? '<span class="prov-badge" data-prov="' + esc(s) + '">' + esc(PROV_SHORT[s] || s) + "</span>" : "";
    }

    // Platform context — the world these scenarios live on (illustrative
    // global-fintech archetype from projection.meta.platform_context). Defined at
    // build() scope so every render function can use it. (Round-10 fix: this was
    // originally defined inside makeObservatory while called from observatoryHtml —
    // a ReferenceError that killed the observatory render; caught by external
    // review actually RENDERING the page, the exact lesson of the QA round.)
    function platformContextLine() {
      var pc = (P.meta || {}).platform_context;
      if (!pc || !pc.facts) return "";
      return '<div class="obs-scope" style="opacity:.8" title="' + esc((pc.facts || []).join("  ·  ") + "\n\n" + (pc.note || "")) + '">'
        + "<b>Platform:</b> " + esc(pc.facts[1] || "") + " · " + esc(pc.facts[4] || "")
        + ' <span style="opacity:.7">(hover for full context · illustrative archetype)</span></div>';
    }

    // ── scenario rail (hydrated from meta.domain_ids) ──
    function renderRail() {
      var html = ids.map(function (id) {
        var d = domains[id] || {};
        var ev = val(d.event_count);
        return '<div class="rail-item" data-domain="' + esc(id) + '" role="tab" aria-pressed="' + (id === current ? "true" : "false") + '">'
          + '<span class="rail-text"><span class="rail-name">' + esc(d.label || id) + "</span>"
          + '<span class="rail-id">' + esc(d.hv_id || "") + " · " + esc(ev) + " events</span></span>"
          + '<span class="rail-badge" data-rag="' + esc(d.overall_rag || "watch") + '">' + esc(ev) + "</span>"
          + "</div>";
      }).join("");
      ctx.setTarget("rail-scenarios", html);
    }

    // ── scenario hero (persistent across acts) ──
    function heroGap(d) {
      var r = (d.comparison || {}).regimes || {};
      var t = (r.traditional || {}).metrics || {}, s = (r.risk_as_code || {}).metrics || {};
      var key = ("evidence_ready_min" in t) ? "evidence_ready_min" : "detection_time_min";
      var label = key === "evidence_ready_min" ? "evidence-ready" : "detection";
      if (!(key in t) || !(key in s)) return "";
      return label + " " + esc(val(t[key])) + "m <span class='hero-arrow'>→</span> " + esc(val(s[key])) + "m";
    }
    function renderHero(d) {
      var gap = heroGap(d);
      var html = '<div class="hv-hero" data-posture="' + esc(d.overall_rag || "critical") + '">'
        + '<div class="hv-hero-top"><span class="hv-hero-id">' + esc(d.hv_id || "") + "</span>"
        + '<span class="hv-hero-name">' + esc(d.label || d.name || current) + "</span>"
        + '<span class="hv-hero-posture">' + esc((d.overall_rag || "critical").toUpperCase()) + "</span></div>"
        + (gap ? '<div class="hv-hero-gap"><span class="hv-hero-gap-label">the gap · </span>' + gap + " " + badge("illustrative") + "</div>" : "")
        + '<div class="hv-hero-sub">' + esc(d.name || "") + " · seed " + esc(meta.run_seed) + " · reproducible"
        + (d.stream_chip ? ' · <span class="hv-chip" title="the chip grammar: realness · cardinality · window · generator — every observatory value derives from this stream">'
            + esc(d.stream_chip.realness) + " · " + esc(d.stream_chip.events) + " events · "
            + esc(d.stream_chip.window_s) + "s · " + esc(d.stream_chip.telemetry_fields) + " fields · gen:"
            + esc(d.stream_chip.gen) + "</span>" : "")
        + "</div>"
        + "</div>";
      ctx.setTarget("scenario-hero", html);
    }

    // ── regime-gap helper (reused from the old timeline act) ──
    function metricOf(d, reg, key) {
      var mm = (((d.comparison || {}).regimes || {})[reg] || {}).metrics || {};
      return (key in mm) ? val(mm[key]) : null;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // OBSERVATORY · an animated incident-flow graph, render-from-data.
    //
    // Ported faithfully from docs/_proto_incident_flow.html (approved design). The
    // prototype's synthetic `D` series is replaced by per-field arrays built from
    // d.events with forward-fill; every node value, KPI tile, KRI badge, escalation
    // rung, regime gap and evidence row derives from the projection.
    // ═══════════════════════════════════════════════════════════════════════════

    // Per-scenario topology, keyed by domain_id. Each defines:
    //   kpis   : [{field, label}] header tiles (fields read off d.events)
    //   nodes  : positioned graph nodes; `field` binds a telemetry series, `unit`/`fmt`
    //            format the value, `sev` classifies severity, `note` phase-notes.
    //   edges  : [from, to, field, kind] — kind ∈ flow|mon|blind; the flow edge's ECG
    //            rides the TARGET node's field (the star signal per topology).
    //   ghost  : the unobservable leg (dashed blind edge, "no signal").
    //   scope  : the header scope line.
    //   title  : the header incident name (from d.label at render time).
    var TOPO = {
      identity_outage: {
        scope: "monitors the technical signal — auth failure rate, lockouts, responder access — as the identity plane fails. The customer-harm and regulatory calls are owned by the incident commander, not this view.",
        kpis: [
          { field: "auth_failure_rate_pct", label: "auth failures", unit: "%", fmt: "one", sev: "err" },
          { field: "customers_locked_out", label: "locked out", unit: "", fmt: "int", sev: "lag" },
          { field: "support_queue_depth", label: "support queue", unit: "", fmt: "int" }
        ],
        // shape: a WALL at the front door — the lock bar rises with counted
        // lockouts; the responder leg runs dark because THEY are locked out too
        // (the recursion, drawn: workforce SSO shares the failed plane).
        cap: "the shape: a wall at the front door — the bar rises with counted lockouts; the responder leg runs dark (locked out with the customers) · ECG = live telemetry · particles = event flow · ghost = unobservable leg",
        nodes: [
          { id: "customers", x: 8, y: 30, nm: "Customers", sl: "login · sessions", field: "auth_attempts_per_sec", unit: " att/s", fmt: "int" },
          { id: "idp", x: 36, y: 26, nm: "Identity plane", sl: "authN · tokens", field: "auth_failure_rate_pct", unit: "% failing", fmt: "one", sev: "err", kris: true },
          { id: "svcs", x: 68, y: 30, nm: "Accounts & funds", sl: "sessions gated here", field: "customers_locked_out", unit: " locked out", fmt: "int", sev: "lag" },
          { id: "resp", x: 40, y: 82, nm: "Response", sl: "SRE · break-glass", sev: "resp" }
        ],
        ghost: { id: "ghost", x: 84, y: 70, nm: "Workforce SSO", sl: "responders · locked out with you", from: "idp" },
        edges: [
          ["customers", "idp", "auth_failure_rate_pct", "flow"],
          ["idp", "svcs", "customers_locked_out", "flow"],
          ["idp", "ghost", null, "blind"],
          ["idp", "resp", null, "mon"],
          ["svcs", "resp", null, "mon"]
        ],
        notes: {
          customers: { build_up: "retry pressure", cascade: "locked out", recovery: "re-auth surge" },
          idp: { build_up: "token issuance failing", cascade: "plane down", recovery: "fallback path live" },
          svcs: { build_up: "sessions expiring", cascade: "inaccessible", recovery: "reopening" },
          resp: { build_up: "paged out-of-band", cascade: "break-glass in", recovery: "audit-ready" }
        }
      },
      kafka_lag_storm: {
        scope: "monitors the technical signal — throughput, backlog, error rate — as the incident moves through the stack. The customer-impact call is owned by the incident commander, not this view.",
        kpis: [
          { field: "producer_rate_mps", label: "throughput", unit: " msg/s", fmt: "int" },
          { field: "lag_messages", label: "consumer lag", unit: "", fmt: "int", sev: "lag" },
          { field: "downstream_error_rate", label: "error rate", unit: "%", fmt: "one", sev: "err" }
        ],
        // shape: a flat pipeline that BACKS UP — wide bus→consumer gap holds the
        // canvas backlog tank (fill = counted lag_messages at the scrub tick).
        cap: "the shape: a pipeline that backs up — the tank fills with the counted backlog · ECG = live telemetry · particles = event flow · dashed = monitor feedback · ghost = unobservable leg",
        nodes: [
          { id: "producer", x: 8, y: 24, nm: "Producer", sl: "payment-events", field: "producer_rate_mps", unit: " msg/s", fmt: "int" },
          { id: "bus", x: 27, y: 20, nm: "Event Bus", sl: "topic · backlog", field: "lag_messages", unit: " lag", fmt: "int", sev: "lag", kris: true },
          { id: "consumer", x: 64, y: 20, nm: "Consumer", sl: "payment-processor", field: "consumer_rate_mps", unit: " msg/s", fmt: "int", sev: "cons" },
          { id: "down", x: 84, y: 24, nm: "Downstream", sl: "payments", field: "downstream_error_rate", unit: "% errors", fmt: "one", sev: "err" },
          { id: "resp", x: 45, y: 83, nm: "Response", sl: "SRE · instrumented", sev: "resp" }
        ],
        ghost: { id: "ghost", x: 90, y: 54, nm: "Partner settlement", sl: "rail · unobservable", from: "down" },
        edges: [
          ["producer", "bus", "lag_messages", "flow"],
          ["bus", "consumer", "lag_messages", "flow"],
          ["consumer", "down", "downstream_error_rate", "flow"],
          ["down", "ghost", null, "blind"],
          ["bus", "resp", null, "mon"],
          ["consumer", "resp", null, "mon"]
        ],
        notes: {
          bus: { build_up: "filling", cascade: "peak", recovery: "draining" },
          consumer: { build_up: "slowing", cascade: "stalled", recovery: "catching up" },
          down: { build_up: "nominal", cascade: "SLO violation", recovery: "recovering" },
          resp: { build_up: "thresholds live", cascade: "alert fires", recovery: "resolved" },
          producer: { build_up: "steady", cascade: "steady", recovery: "steady" }
        }
      },
      deployment_cascade: {
        scope: "monitors the technical signal — error rate, dropped requests, MTTR — as a bad release cascades through the services. The customer-impact call is owned by the incident commander, not this view.",
        kpis: [
          { field: "error_rate_pct", label: "error rate", unit: "%", fmt: "one", sev: "err" },
          { field: "requests_dropped", label: "dropped", unit: "", fmt: "int", sev: "drop" },
          { field: "mttr_minutes", label: "MTTR", unit: "m", fmt: "one" }
        ],
        // shape: a descending BLAST DIAGONAL — change high-left, damage falling to
        // low-right; the canvas cone from Service widens with counted err%/dropped.
        cap: "the shape: a blast diagonal — the cone widens with counted error % and dropped requests · ECG = live telemetry · particles = event flow · dashed = monitor feedback · ghost = unobservable leg",
        nodes: [
          { id: "change", x: 11, y: 12, nm: "Change", sl: "deploy", staticVal: "deploy", field: "__deploy__" },
          { id: "svc", x: 37, y: 34, nm: "Service", sl: "order-router", field: "error_rate_pct", unit: "% errors", fmt: "one", sev: "err", kris: true },
          { id: "down", x: 63, y: 58, nm: "Downstream", sl: "services", field: "requests_dropped", unit: " dropped", fmt: "int", sev: "drop" },
          { id: "resp", x: 13, y: 78, nm: "Response", sl: "SRE · instrumented", sev: "resp" }
        ],
        ghost: { id: "ghost", x: 87, y: 80, nm: "Customer orders", sl: "client-side · unobservable", from: "down" },
        edges: [
          ["change", "svc", "error_rate_pct", "flow"],
          ["svc", "down", "requests_dropped", "flow"],
          ["down", "ghost", null, "blind"],
          ["svc", "resp", null, "mon"],
          ["down", "resp", null, "mon"]
        ],
        notes: {
          change: { build_up: "shipped", cascade: "cascading", recovery: "rolled back" },
          svc: { build_up: "healthy", cascade: "erroring", recovery: "recovering" },
          down: { build_up: "nominal", cascade: "blast radius", recovery: "draining" },
          resp: { build_up: "thresholds live", cascade: "alert fires", recovery: "resolved" }
        }
      },
      velocity_surge: {
        scope: "monitors the technical signal — throughput, surge ratio, blocked transactions — as a velocity surge hits the fraud control. The compliance / customer call is owned by the reviewer, not this view.",
        kpis: [
          { field: "transactions_per_sec", label: "throughput", unit: " tps", fmt: "int" },
          { field: "surge_ratio", label: "surge ratio", unit: "×", fmt: "one", sev: "critical" },
          { field: "transactions_blocked", label: "blocked", unit: "", fmt: "int", sev: "blocked" }
        ],
        // shape: a Y-FORK at the control — settled leg runs dark up to the partner
        // banks (the unobservable ghost IS the settled branch); blocked branch drops
        // low-right and thickens with counted transactions_blocked behind the gate.
        cap: "the shape: a fork at the control — the blocked branch thickens with every counted block; the settled leg runs dark · ECG = live telemetry · particles = event flow · ghost = unobservable leg",
        nodes: [
          { id: "inflow", x: 8, y: 40, nm: "Inflow", sl: "payments · txns", field: "transactions_per_sec", unit: " tps", fmt: "int" },
          { id: "ctrl", x: 34, y: 40, nm: "Velocity control", sl: "fraud checkpoint", field: "surge_ratio", unit: "× baseline", fmt: "one", sev: "critical", kris: true },
          { id: "out", x: 66, y: 66, nm: "Outcome", sl: "blocked vs settled", field: "transactions_blocked", unit: " blocked", fmt: "int", sev: "blocked" },
          { id: "resp", x: 34, y: 82, nm: "Response", sl: "SRE · instrumented", sev: "resp" }
        ],
        ghost: { id: "ghost", x: 82, y: 14, nm: "Partner banks", sl: "settlement · unobservable", from: "ctrl" },
        edges: [
          ["inflow", "ctrl", "surge_ratio", "flow"],
          ["ctrl", "out", "transactions_blocked", "flow"],
          ["ctrl", "ghost", null, "blind"],
          ["ctrl", "resp", null, "mon"],
          ["out", "resp", null, "mon"]
        ],
        notes: {
          inflow: { build_up: "~baseline", cascade: "surge", recovery: "elevated" },
          ctrl: { build_up: "over baseline", cascade: "surge detected", recovery: "easing" },
          out: { build_up: "clear", cascade: "control holding", recovery: "clearing" },
          resp: { build_up: "thresholds live", cascade: "alert fires", recovery: "resolved" }
        }
      }
    };

    // Severity classifiers (per the approved thresholds). All read a numeric value.
    var SEV = {
      lag: function (v) { return v > 4000 ? "critical" : v > 2000 ? "watch" : "normal"; },
      err: function (v) { return v > 8 ? "critical" : v > 5 ? "watch" : "normal"; },
      cons: function (v) { return v < 945 ? "critical" : v < 985 ? "watch" : "normal"; },
      drop: function (v) { return v > 1000 ? "critical" : v > 0 ? "watch" : "normal"; },
      critical: function (v) { return v > 5 ? "critical" : v > 2 ? "watch" : "normal"; },
      blocked: function (v) { return v > 0 ? "watch" : "normal"; }
    };

    // Build a forward-filled numeric series for `field` over the event array. Nulls /
    // missing keys carry the last seen value forward (0 until the first real reading).
    function fieldSeries(events, field) {
      var out = [], last = 0;
      for (var i = 0; i < events.length; i++) {
        var v = events[i][field];
        if (v === null || v === undefined || v === "" || isNaN(+v)) { out.push(last); }
        else { last = +v; out.push(last); }
      }
      return out;
    }

    function fmtInt(v) { return Math.round(v).toLocaleString(); }
    function fmtOne(v) { return (Math.round(v * 10) / 10).toString(); }
    function fmtVal(v, kind) { return kind === "one" ? fmtOne(v) : fmtInt(v); }
    function phaseAt(events, i) {
      var e = events[Math.max(0, Math.min(events.length - 1, i))];
      return (e && e.phase) || "build_up";
    }
    function firstIdxOfPhase(events, ph) {
      for (var i = 0; i < events.length; i++) if (events[i].phase === ph) return i;
      return -1;
    }
    // the "peak" moment lands on the max-value event of the star field within a phase
    // (so "cascade peak" jumps to the actual peak, e.g. the ~11.85M-message lag crest — not cascade-start)
    function peakIdxInPhase(events, field, ph) {
      var mi = -1, mv = -Infinity;
      for (var i = 0; i < events.length; i++) {
        if (events[i].phase !== ph) continue;
        var v = field ? events[i][field] : null;
        if (v != null && v > mv) { mv = v; mi = i; }
      }
      return mi >= 0 ? mi : firstIdxOfPhase(events, ph);
    }
    // friendly labels for the seeded telemetry that rides each flow edge (edge callouts)
    var FIELD_LBL = { producer_rate_mps: "throughput", lag_messages: "consumer lag", consumer_rate_mps: "consumer rate", downstream_error_rate: "error rate", error_rate_pct: "error rate", requests_dropped: "requests dropped", transactions_per_sec: "txn rate", surge_ratio: "velocity ×", transactions_blocked: "blocked" };
    // KRI badge severity by phase — the primary KRI goes critical in cascade; others milder.
    function kriSevAt(role, ph) {
      var primary = role === "primary";
      if (ph === "cascade") return primary ? "critical" : "watch";
      if (ph === "recovery") return primary ? "evid" : "normal";
      return primary ? "watch" : "normal"; // build_up
    }
    function kriText(s) { return s === "critical" ? "critical" : s === "watch" ? "elevated" : s === "evid" ? "caught" : "normal"; }

    // ── observatory HTML (structure ported from the prototype) ──
    function observatoryHtml(d) {
      var topo = TOPO[d.domain_id] || TOPO.kafka_lag_storm;
      var kpiTiles = topo.kpis.map(function (k, i) {
        return '<div class="obs-kpi"><div class="obs-kpi-n" data-kpi="' + i + '">—</div>'
          + '<div class="obs-kpi-l">' + esc(k.label) + "</div></div>";
      }).join("");
      // signals-real KPI: count fields that resolve on the first event vs the ghost leg
      var nodeHtml = topo.nodes.map(function (n) {
        return '<div class="obs-node" id="obs_n_' + esc(n.id) + '" style="left:' + n.x + "%;top:" + n.y + '%"></div>';
      }).join("");
      var ghost = topo.ghost;
      var ghostHtml = '<div class="obs-node obs-ghost" id="obs_n_' + esc(ghost.id) + '" style="left:' + ghost.x + "%;top:" + ghost.y + '%">'
        + '<div class="obs-nm">' + esc(ghost.nm) + '</div><div class="obs-sl">' + esc(ghost.sl) + "</div>"
        + '<div class="obs-mv">no signal</div><div class="obs-st">unobservable leg · dark</div></div>';

      return ''
        + '<div class="obs">'
        + '  <div class="obs-top">'
        + '    <div class="obs-top-l">'
        + '      <div class="obs-eyebrow">Incident Flow Observatory · simulated · seeded</div>'
        + '      <div class="obs-title">' + esc(d.hv_id || "") + " · " + esc(d.label || "") + "</div>"
        + '      <div class="obs-scope"><b>Scope:</b> ' + esc(topo.scope) + "</div>"
        + platformContextLine()
        + "    </div>"
        + '    <div class="obs-kpis">' + kpiTiles + "</div>"
        + "  </div>"
        + '  <div class="obs-tl">'
        + '    <button class="obs-play" data-obs="play">▶ play</button>'
        + '    <span class="obs-moments"></span>'
        + '    <input type="range" class="obs-scrub" data-obs="scrub" aria-label="Scrub the incident timeline" min="0" max="0" value="0">'
        + '    <div class="obs-spd"><button data-spd="0.25" class="on">1×</button><button data-spd="1">4×</button></div>'
        + '    <button class="obs-tour" data-obs="tour">◇ tour</button>'
        + '    <span class="obs-clk" data-obs="clk"></span>'
        + "  </div>"
        + '  <div class="obs-dash">'
        + '    <div class="obs-card">'
        + '      <h3>Canonical <b>KRIs</b> exercised</h3>'
        + '      <div data-obs="kris"></div>'
        + '      <div class="obs-prov" data-obs="prov"></div>'
        + '      <div class="obs-legend"><span><i class="obs-i-normal"></i>normal</span><span><i class="obs-i-watch"></i>elevated</span><span><i class="obs-i-critical"></i>critical</span></div>'
        + "    </div>"
        + '    <div class="obs-stage-wrap">'
        + '      <div class="obs-stage" data-obs="stage">'
        + '        <canvas data-obs="cv"></canvas>'
        + nodeHtml
        + ghostHtml
        + '        <div class="obs-stage-cap">' + esc(topo.cap || "ECG = live telemetry on the edge · particles = event flow · dashed = monitor feedback · ghost = unobservable leg") + "</div>"
        + '        <div class="obs-tour-ov" data-obs="tourov" role="dialog" aria-label="Incident tour"></div>'
        + "      </div>"
        + "    </div>"
        + '    <div class="obs-card">'
        + '      <h3>Escalation &amp; <b>response</b></h3>'
        + '      <div class="obs-esc" data-obs="esc"></div>'
        + '      <div class="obs-gap" data-obs="gap"></div>'
        + "    </div>"
        + "  </div>"
        + '  <div class="obs-card obs-evid-wrap">'
        + '    <h3>Evidence · <b>event log</b> (seeded, reproducible — every row traces to the projection)</h3>'
        + '    <table class="obs-evid"><thead><tr><th>t</th><th>phase</th><th>component</th><th>signal</th><th>reading</th><th>severity</th></tr></thead><tbody data-obs="evid"></tbody></table>'
        + "  </div>"
        + "</div>";
    }

    // ── the observatory engine (canvas + controls), one instance per scenario ──
    var obs = null; // current running instance (destroyed + rebuilt on scenario change)

    function makeObservatory(d) {
      var topo = TOPO[d.domain_id] || TOPO.kafka_lag_storm;
      var events = (d.events || []).filter(function (e) { return e.t_seconds != null; });
      if (!events.length) return null;
      var N = events.length;

      var root = document.querySelector('[data-target="observatory"] .obs');
      if (!root) return null;
      function q(sel) { return root.querySelector(sel); }
      function qa(sel) { return root.querySelectorAll(sel); }

      // ── per-field series (forward-filled) ──
      var series = {};
      topo.nodes.forEach(function (n) { if (n.field && n.field !== "__deploy__" && !(n.field in series)) series[n.field] = fieldSeries(events, n.field); });
      topo.kpis.forEach(function (k) { if (k.field && !(k.field in series)) series[k.field] = fieldSeries(events, k.field); });
      topo.edges.forEach(function (e) { if (e[2] && !(e[2] in series)) series[e[2]] = fieldSeries(events, e[2]); });

      // per-flow-edge ECG ceiling = the field's peak (real, from data)
      var fieldMax = {};
      Object.keys(series).forEach(function (f) { fieldMax[f] = Math.max.apply(null, series[f].concat([1])); });

      // ── named moments (from data): precursor + recovery = phase start; cascade = the PEAK event ──
      var starNode = (topo.nodes || []).filter(function (n) { return n.kris; })[0];
      var starField = starNode ? starNode.field : null;
      var moments = [];
      ["build_up", "cascade", "recovery"].forEach(function (ph, i) {
        var idx = ph === "cascade" ? peakIdxInPhase(events, starField, "cascade") : firstIdxOfPhase(events, ph);
        if (idx >= 0) moments.push({ i: idx, lbl: ph === "build_up" ? "precursor" : ph === "cascade" ? "cascade peak" : "recovery", hot: ph === "cascade" });
      });

      // ── severity for a node at index i ──
      function nodeSev(n, i) {
        if (n.sev === "resp") { var p = phaseAt(events, i); return p === "cascade" ? "watch" : p === "recovery" ? "evidence" : "normal"; }
        if (!n.field || n.field === "__deploy__" || !SEV[n.sev]) return "normal";
        return SEV[n.sev]((series[n.field] || [])[i] || 0);
      }
      function nodeVal(n, i) {
        if (n.field === "__deploy__") return n.staticVal || "deploy";
        if (!n.field) {
          if (n.sev === "resp") {
            var p = phaseAt(events, i);
            var tds = metricOf(d, "risk_as_code", "detection_time_min");
            var tvs = metricOf(d, "risk_as_code", "evidence_ready_min");
            return p === "cascade" ? ("detect @ " + tds + "m") : p === "recovery" ? ("audit-ready " + tvs + "m") : "monitoring";
          }
          return "";
        }
        return fmtVal((series[n.field] || [])[i] || 0, n.fmt) + (n.unit || "");
      }
      function nodeNote(n, i) {
        var p = phaseAt(events, i);
        var m = topo.notes[n.id];
        return (m && m[p]) || "";
      }

      // KRI badges on the flagged node (from d.kris_fired)
      var kris = (d.kris_fired || []);
      var nodeKriBadges = kris.slice(0, 2).map(function (k) { return k.id; });

      function renderNodes(i) {
        topo.nodes.forEach(function (n) {
          var el = q("#obs_n_" + n.id);
          if (!el) return;
          var sev = nodeSev(n, i);
          el.setAttribute("data-sev", sev);
          var kb = (n.kris ? nodeKriBadges.map(function (b) { return '<span class="obs-kb">' + esc(b) + "</span>"; }).join("") : "");
          el.innerHTML = '<div class="obs-nm">' + esc(n.nm) + '</div><div class="obs-sl">' + esc(n.sl) + "</div>"
            + '<div class="obs-mv">' + esc(nodeVal(n, i)) + '</div><div class="obs-st">' + esc(nodeNote(n, i)) + "</div>" + kb;
        });
      }

      function renderKpis(i) {
        topo.kpis.forEach(function (k, ki) {
          var el = q('[data-kpi="' + ki + '"]'); if (!el) return;
          var v = (series[k.field] || [])[i] || 0;
          el.textContent = fmtVal(v, k.fmt) + (k.unit || "");
          if (k.sev && SEV[k.sev]) {
            var s = SEV[k.sev](v);
            el.className = "obs-kpi-n obs-sev-" + s;
          }
        });
      }

      function renderKris(i) {
        var p = phaseAt(events, i);
        var html = kris.map(function (k) {
          var s = kriSevAt(k.role, p);
          var cl = s === "critical" ? "critical" : s === "watch" ? "watch" : s === "evid" ? "evid" : "normal";
          return '<div class="obs-kri" data-sev="' + s + '"><div class="obs-kri-top"><span class="obs-kri-id">' + esc(k.id)
            + '</span><span class="obs-badge ' + cl + '">' + kriText(s) + "</span></div>"
            + '<div class="obs-kri-nm">' + esc(k.name) + "</div>"
            + '<div class="obs-kri-role">' + esc((k.role || "").toUpperCase()) + "</div></div>";
        }).join("");
        q('[data-obs="kris"]').innerHTML = html;
      }

      // Escalation ladder: rungs light up by phase level (build_up=1, cascade=3, recovery=2).
      var ESC = [
        { c: "g", lv: "GREEN · monitoring", who: "SRE on-call watches telemetry" },
        { c: "y", lv: "YELLOW · alerted", who: "on-call paged; threshold crossed" },
        { c: "r", lv: "RED · escalated", who: "eng lead + incident commander" },
        { c: "c", lv: "CRITICAL · war room", who: "leadership notified; customer-impact review" }
      ];
      function renderEsc(i) {
        var p = phaseAt(events, i), lvl = p === "cascade" ? 3 : p === "recovery" ? 2 : 1;
        q('[data-obs="esc"]').innerHTML = ESC.map(function (r, j) {
          return '<div class="obs-rung ' + r.c + (j + 1 <= lvl ? " on" : "") + '"><div class="obs-rung-lv">' + esc(r.lv)
            + '</div><div class="obs-rung-who">' + esc(r.who) + "</div></div>";
        }).join("");
      }


      // Regime gap — from metricOf(d, ...) (the projection's comparison metrics)
      function renderGap() {
        var inst = metricOf(d, "risk_as_code", "detection_time_min");
        var hand = metricOf(d, "traditional", "detection_time_min");
        var closes = (inst != null && hand != null) ? Math.max(0, hand - inst) : null;
        q('[data-obs="gap"]').innerHTML =
          '<div class="obs-gap-row"><span class="obs-gap-k">time-to-detect</span></div>'
          + '<div class="obs-gap-row"><span class="obs-inst">◆ instrumented</span><span class="obs-inst">' + esc(inst == null ? "—" : inst + " min") + "</span></div>"
          + '<div class="obs-gap-row"><span class="obs-hand">◆ by hand (checklist)</span><span class="obs-hand">' + esc(hand == null ? "—" : hand + " min") + "</span></div>"
          + '<div class="obs-gap-row obs-gap-total"><span class="obs-gap-k">the gap it closes</span><span class="obs-gap-c">' + esc(closes == null ? "—" : closes + " min earlier") + "</span></div>"
          + " " + badge("illustrative")
          + warRoom();
      }

      // War-room timelines — the PEOPLE inside the gap (round-8 depth pass).
      // From d.comparison.regimes[*].response_timeline (illustrative narrative;
      // minute marks consistent with the same response metrics shown above).
      // Progressive disclosure — the graph stays the hero.
      function warRoom() {
        var regs = (d.comparison || {}).regimes || {};
        var out = "";
        [["traditional", "by hand — the 3am version"], ["risk_as_code", "instrumented — same incident"]].forEach(function (pair) {
          var tl = (regs[pair[0]] || {}).response_timeline;
          if (!tl || !tl.entries || !tl.entries.length) return;
          out += '<details style="margin-top:8px"><summary style="cursor:pointer; font-size:11px; color:var(--text-mut)">war room · ' + esc(pair[1]) + " (" + tl.entries.length + " moments)</summary>";
          tl.entries.forEach(function (e) {
            out += '<div style="display:flex; gap:8px; margin:5px 0; font-size:11px; line-height:1.5">'
              + '<span style="font-family:var(--font-mono); color:var(--text-faint); flex:0 0 34px">+' + esc(String(e.t_min)) + "m</span>"
              + '<span style="color:var(--text); flex:0 0 148px">' + esc(e.actor) + "</span>"
              + '<span style="color:var(--text-mut); flex:1">' + esc(e.action) + "</span></div>";
          });
          out += '<div style="font-size:10px; color:var(--text-faint); margin-top:4px">' + esc(tl.note || "") + "</div></details>";
        });
        return out;
      }

      // Evidence log — ~6-8 representative rows built from d.events (from data).
      // Picks the first build-up watch, the cascade peak, the peak error/secondary,
      // an SRE detection marker, and recovery/audit-ready markers — all real readings.
      function buildEvidence() {
        var rows = [];
        function tstr(sec) { return sec >= 120 ? ("t+" + Math.round(sec / 60) + "m") : ("t+" + sec + "s"); }
        var starField = topo.edges.filter(function (e) { return e[3] === "flow"; }).map(function (e) { return e[2]; })[1] || topo.kpis[1].field;
        var starLabel = (topo.kpis.filter(function (k) { return k.field === starField; })[0] || topo.kpis[1]).label;
        var starFmt = (topo.kpis.filter(function (k) { return k.field === starField; })[0] || topo.kpis[1]).fmt;
        var starSev = (topo.kpis.filter(function (k) { return k.field === starField; })[0] || {}).sev;
        var starNode = topo.nodes.filter(function (n) { return n.field === starField; })[0] || {};
        var compNm = starNode.nm || "Event Bus";
        // build-up first watch on the star signal
        var s = series[starField] || [];
        for (var i = 0; i < N; i++) {
          if (events[i].phase === "build_up" && starSev && SEV[starSev] && SEV[starSev](s[i]) !== "normal") {
            rows.push([tstr(events[i].t_seconds), "build_up", compNm, starLabel, fmtVal(s[i], starFmt), SEV[starSev](s[i])]); break;
          }
        }
        // cascade peak on the star signal
        var pkI = -1, pkV = -1;
        for (var j = 0; j < N; j++) { if (events[j].phase === "cascade" && s[j] > pkV) { pkV = s[j]; pkI = j; } }
        if (pkI >= 0) rows.push([tstr(events[pkI].t_seconds), "cascade", compNm, starLabel, fmtVal(s[pkI], starFmt), starSev && SEV[starSev] ? SEV[starSev](s[pkI]) : "critical"]);
        // cascade peak on a secondary field (last flow edge target / a KPI with severity)
        var sec = topo.kpis.filter(function (k) { return k.field !== starField && k.sev; })[0];
        if (sec) {
          var ss = series[sec.field] || [], spI = -1, spV = -1;
          for (var k2 = 0; k2 < N; k2++) { if (events[k2].phase === "cascade" && ss[k2] > spV) { spV = ss[k2]; spI = k2; } }
          var secNode = topo.nodes.filter(function (n) { return n.field === sec.field; })[0] || {};
          if (spI >= 0) rows.push([tstr(events[spI].t_seconds), "cascade", secNode.nm || sec.label, sec.label, fmtVal(ss[spI], sec.fmt), sec.sev && SEV[sec.sev] ? SEV[sec.sev](ss[spI]) : "watch"]);
        }
        // detection marker (SRE · instrumented, from the regime metric)
        var casI = firstIdxOfPhase(events, "cascade");
        var tds = metricOf(d, "risk_as_code", "detection_time_min");
        if (casI >= 0) rows.push([tstr(events[casI].t_seconds), "cascade", "Response", "detection", "alert @ " + tds + "m", "watch"]);
        // recovery draining on the star signal
        var recI = firstIdxOfPhase(events, "recovery");
        if (recI >= 0 && recI < N) rows.push([tstr(events[recI].t_seconds), "recovery", compNm, starLabel, fmtVal(s[recI], starFmt), starSev && SEV[starSev] ? SEV[starSev](s[recI]) : "watch"]);
        // audit-ready marker
        var tvs = metricOf(d, "risk_as_code", "evidence_ready_min");
        var lastRec = events[N - 1];
        if (lastRec && lastRec.phase === "recovery") rows.push([tstr(lastRec.t_seconds), "recovery", "Response", "evidence", "audit-ready " + tvs + "m", "evidence"]);
        return rows;
      }
      var EVID = buildEvidence();
      var SEVC = { normal: "var(--normal)", watch: "var(--watch)", critical: "var(--critical)", evidence: "var(--evid)" };
      function renderEvid(i) {
        var p = phaseAt(events, i);
        q('[data-obs="evid"]').innerHTML = EVID.map(function (r) {
          var dim = r[1] !== p;
          return '<tr style="opacity:' + (dim ? .4 : 1) + '"><td class="c">' + esc(r[0]) + "</td><td>" + esc(r[1].replace("_", "-"))
            + '</td><td class="c">' + esc(r[2]) + "</td><td>" + esc(r[3]) + '</td><td class="c">' + esc(r[4]) + "</td>"
            + '<td><span class="obs-sev-dot" style="background:' + SEVC[r[5]] + '"></span>' + esc(r[5]) + "</td></tr>";
        }).join("");
      }

      // signals-real provenance line (real fields vs the 1 unobservable ghost leg)
      var realFields = topo.nodes.filter(function (n) { return n.field && n.field !== "__deploy__"; }).length;
      function renderProv() {
        q('[data-obs="prov"]').innerHTML = 'signals: <b>' + realFields + '/' + (realFields + 1) + ' seeded ✓</b> · '
          + '<span class="obs-dark">1 leg unobservable (partner/customer rail — blind spot, shown ghosted)</span>. '
          + 'Byte-reproducible under the seed; the ECG on each edge rides the seeded event series.';
      }

      // ── moments buttons (built from data) ──
      q(".obs-moments").innerHTML = moments.map(function (m) {
        return '<button class="obs-mom' + (m.hot ? " hot" : "") + '" data-idx="' + m.i + '">' + esc(m.lbl) + "</button>";
      }).join("");
      var scrub = q('[data-obs="scrub"]');
      scrub.max = N - 1;

      // default index → cascade peak if present, else middle
      var casStart = firstIdxOfPhase(events, "cascade");
      var idx = casStart >= 0 ? Math.min(N - 1, casStart + 2) : Math.floor(N / 2);
      var playing = false, speed = 0.25, animT = 0, last = 0, raf = null, ptimer = null;

      function panels(i) {
        i = Math.max(0, Math.min(N - 1, Math.floor(i)));
        renderNodes(i); renderKpis(i); renderKris(i); renderEsc(i); renderEvid(i);
        q('[data-obs="clk"]').textContent = "t " + i + "/" + (N - 1) + " · " + phaseAt(events, i).replace("_", "-");
        scrub.value = i;
        qa(".obs-mom").forEach(function (b) { b.classList.toggle("on", Math.abs(+b.dataset.idx - i) < 3); });
      }

      // ── canvas graph ──
      var stage = q('[data-obs="stage"]'), cv = q('[data-obs="cv"]'), g = cv.getContext("2d");
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var pts = {}, parts = [];
      function cvv(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
      var CH = { normal: cvv("--normal"), watch: cvv("--watch"), critical: cvv("--critical"), evidence: cvv("--evid"), cool: cvv("--cool"), cyan: cvv("--cyan") };
      function rgba(hex, a) { var h = (hex || "#888888").replace("#", ""); if (h.length < 6) h = "888888"; return "rgba(" + parseInt(h.slice(0, 2), 16) + "," + parseInt(h.slice(2, 4), 16) + "," + parseInt(h.slice(4, 6), 16) + "," + a + ")"; }

      var nodeById = {};
      topo.nodes.forEach(function (n) { nodeById[n.id] = n; });
      var allIds = topo.nodes.map(function (n) { return n.id; }).concat([topo.ghost.id]);

      function centers() {
        var sr = stage.getBoundingClientRect();
        allIds.forEach(function (k) {
          var el = q("#obs_n_" + k); if (!el) return;
          var r = el.getBoundingClientRect();
          pts[k] = { x: r.left - sr.left + r.width / 2, y: r.top - sr.top + r.height / 2, w: r.width, h: r.height };
        });
        cv.width = sr.width * dpr; cv.height = sr.height * dpr; cv.style.width = sr.width + "px"; cv.style.height = sr.height + "px";
        g.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      function bd(a, b) { var dx = b.x - a.x, dy = b.y - a.y, hw = a.w / 2 + 3, hh = a.h / 2 + 3, sx = dx ? hw / Math.abs(dx) : 1e9, sy = dy ? hh / Math.abs(dy) : 1e9, s = Math.min(sx, sy); return { x: a.x + dx * s, y: a.y + dy * s }; }
      function cpOf(a, b, l) { var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1; return { x: mx + (-dy / len) * l, y: my + (dx / len) * l }; }
      function geom(e) { var a = pts[e[0]], b = pts[e[1]]; if (!a || !b) return null; var a2 = bd(a, b), b2 = bd(b, a); return { a: a2, b: b2, cp: cpOf(a2, b2, e[3] === "mon" ? 40 : e[3] === "blind" ? 0 : -24) }; }
      function bez(a, cp, b, t) { var mt = 1 - t; return { x: mt * mt * a.x + 2 * mt * t * cp.x + t * t * b.x, y: mt * mt * a.y + 2 * mt * t * cp.y + t * t * b.y }; }
      function tan(a, cp, b, t) { var mt = 1 - t; return { x: 2 * (mt * (cp.x - a.x) + t * (b.x - cp.x)), y: 2 * (mt * (cp.y - a.y) + t * (b.y - cp.y)) }; }
      function seed() { parts = []; topo.edges.forEach(function (e, ei) { if (e[3] === "blind") return; var n = e[3] === "mon" ? 9 : 24; for (var i = 0; i < n; i++) parts.push({ e: ei, t: Math.random(), spd: .09 + Math.random() * .09 }); }); }
      function reduced() { return window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches; }
      function paused() { return document.body.classList.contains("anim-paused") || reduced(); }

      function drawECG(e) {
        var G = geom(e); if (!G) return;
        var i = Math.floor(idx), WIN = 26, s = Math.max(0, i - WIN), win = [], sf = series[e[2]] || [];
        for (var k = s; k <= i; k++) win.push(sf[k] || 0);
        var amp = 27 * (Math.min(stage.clientWidth, stage.clientHeight) / 620);
        var mx = fieldMax[e[2]] || 1;
        g.beginPath(); var ok = false;
        for (var j = 0; j < win.length; j++) {
          var t = win.length > 1 ? j / (win.length - 1) : 0;
          var p = bez(G.a, G.cp, G.b, t), tn = tan(G.a, G.cp, G.b, t), dl = Math.hypot(tn.x, tn.y) || 1, px = -tn.y / dl, py = tn.x / dl;
          var norm = win[j] / mx, disp = (norm - .28) * amp;
          var wx = p.x + px * disp, wy = p.y + py * disp;
          if (!ok) { g.moveTo(wx, wy); ok = true; } else g.lineTo(wx, wy);
        }
        var cur = win[win.length - 1] || 0, inten = Math.min(1, cur / mx);
        var r2 = Math.round(103 + inten * (224 - 103)), g2 = Math.round(194 - inten * 107), b2 = Math.round(212 - inten * 133);
        g.strokeStyle = "rgba(" + r2 + "," + g2 + "," + b2 + ",.78)"; g.lineWidth = 2.4; g.stroke();
      }

      // ── per-scenario signature layer: three different failure SHAPES, all driven
      //    by counted series at the scrub tick. kafka = a backlog tank that fills,
      //    deploy = a blast cone that widens, velocity = a fork whose blocked branch
      //    thickens behind a closing gate. Drawn first each frame (the canvas floor),
      //    so edges / ECG / particles ride on top.
      function sigLabel(txt, x, y, col) {
        g.font = "600 9px ui-monospace, SFMono-Regular, monospace"; g.textAlign = "center";
        g.shadowColor = "rgba(0,0,0,.92)"; g.shadowBlur = 4; g.fillStyle = col;
        g.fillText(txt, Math.max(80, Math.min(stage.clientWidth - 80, x)), Math.max(11, Math.min(stage.clientHeight - 6, y)));
        g.shadowBlur = 0;
      }
      function sigTank(i) {
        var a = pts.bus, b = pts.consumer; if (!a || !b) return;
        var s = series.lag_messages || [], lag = s[i] || 0, mx = fieldMax.lag_messages || 1, f = Math.min(1, lag / mx);
        var cx = (a.x + b.x) / 2, W = Math.max(64, (b.x - a.x) - a.w - 26), H = Math.min(96, stage.clientHeight * .22);
        var y0 = Math.max(a.y, b.y) + 26, y1 = y0 + H, x0 = cx - W / 2, x1 = cx + W / 2;
        var sev = SEV.lag(lag), col = CH[sev] || CH.cool;
        var fh = Math.max(2, H * f);
        var grd = g.createLinearGradient(0, y1 - fh, 0, y1);
        grd.addColorStop(0, rgba(col, .34)); grd.addColorStop(1, rgba(col, .08));
        g.fillStyle = grd; g.fillRect(x0 + 2, y1 - fh, W - 4, fh - 1);
        // liquid surface (wobbles while animating)
        g.strokeStyle = rgba(col, .85); g.lineWidth = 1.6; g.beginPath();
        for (var k2 = 0; k2 <= 22; k2++) { var t = k2 / 22, wx = x0 + 2 + t * (W - 4), wy = y1 - fh + Math.sin(animT * 2.3 + t * 9.5) * 1.7; k2 ? g.lineTo(wx, wy) : g.moveTo(wx, wy); }
        g.stroke();
        // vessel walls, open top; inlet/outlet stubs tie it into the pipeline
        g.strokeStyle = "rgba(152,140,120,.6)"; g.lineWidth = 2;
        g.beginPath(); g.moveTo(x0, y0); g.lineTo(x0, y1); g.lineTo(x1, y1); g.lineTo(x1, y0); g.stroke();
        g.strokeStyle = "rgba(152,140,120,.38)"; g.lineWidth = 2.4;
        g.beginPath(); g.moveTo(a.x + a.w / 2, a.y + 6); g.lineTo(x0, y0 + 10); g.stroke();
        g.beginPath(); g.moveTo(x1, y0 + 10); g.lineTo(b.x - b.w / 2, b.y + 6); g.stroke();
        sigLabel("backlog tank · " + fmtInt(lag) + " msgs", cx, y1 + 15, rgba(col, .95));
        sigLabel(Math.round(f * 100) + "% of the " + fmtInt(mx) + " peak", cx, y1 + 27, "rgba(152,140,120,.8)");
      }
      function sigCone(i, casc) {
        var a = pts.svc, b = pts.down, gh = pts.ghost; if (!a || !b) return;
        var es = series.error_rate_pct || [], ds = series.requests_dropped || [];
        var en = Math.min(1, (es[i] || 0) / (fieldMax.error_rate_pct || 1));
        var dn = Math.min(1, (ds[i] || 0) / (fieldMax.requests_dropped || 1));
        var ang = Math.atan2(b.y - a.y, b.x - a.x);
        var reach = Math.hypot(b.x - a.x, b.y - a.y) * (.55 + .8 * dn);
        if (gh) reach = Math.min(reach, Math.hypot(gh.x - a.x, gh.y - a.y) * .96);
        var half = .12 + .34 * en;
        var tx2 = a.x + Math.cos(ang) * (a.w / 2), ty2 = a.y + Math.sin(ang) * (a.h / 2);
        var pulse = casc ? .24 + Math.sin(animT * 3.2) * .06 : .14;
        var grd = g.createRadialGradient(tx2, ty2, 6, tx2, ty2, reach);
        grd.addColorStop(0, rgba(CH.critical, pulse)); grd.addColorStop(1, rgba(CH.critical, 0));
        g.fillStyle = grd;
        g.beginPath(); g.moveTo(tx2, ty2); g.arc(tx2, ty2, reach, ang - half, ang + half); g.closePath(); g.fill();
        g.strokeStyle = rgba(CH.critical, casc ? .5 : .26); g.lineWidth = 1.2; g.setLineDash([5, 5]);
        g.beginPath(); g.arc(tx2, ty2, reach, ang - half, ang + half); g.stroke(); g.setLineDash([]);
        // inner range rings — the cascade's advance, fractions of the current reach
        [.45, .75].forEach(function (r2) {
          g.strokeStyle = rgba(CH.critical, .14); g.lineWidth = 1; g.setLineDash([2, 6]);
          g.beginPath(); g.arc(tx2, ty2, reach * r2, ang - half, ang + half); g.stroke(); g.setLineDash([]);
        });
        // label rides the LOWER rim so it clears the edge callout on the same axis
        sigLabel("blast radius · " + fmtOne(es[i] || 0) + "% err · " + fmtInt(ds[i] || 0) + " dropped",
          tx2 + Math.cos(ang + half) * (reach + 20), ty2 + Math.sin(ang + half) * (reach + 24), rgba(CH.critical, .92));
      }
      function sigFork(i) {
        var c = pts.ctrl, o = pts.out, gh = pts.ghost; if (!c || !o || !gh) return;
        var bs = series.transactions_blocked || [], blk = bs[i] || 0;
        var bn = Math.min(1, blk / (fieldMax.transactions_blocked || 1));
        var sr = (series.surge_ratio || [])[i] || 0, gsev = SEV.critical(sr), gcol = CH[gsev] || CH.watch;
        // settled leg — the dark branch up to the partner banks (no counted signal)
        var gA = bd(c, gh), gB = bd(gh, c), gcp = cpOf(gA, gB, -18);
        g.strokeStyle = "rgba(111,98,80,.3)"; g.lineWidth = 9; g.setLineDash([4, 7]);
        g.beginPath(); g.moveTo(gA.x, gA.y); g.quadraticCurveTo(gcp.x, gcp.y, gB.x, gB.y); g.stroke(); g.setLineDash([]);
        // blocked branch — a pipe that thickens with every counted block
        var bcol = blk > 0 ? CH.critical : CH.cool;
        var bA = bd(c, o), bB = bd(o, c), bcp = cpOf(bA, bB, 18), w = 3 + 17 * bn;
        g.lineCap = "round";
        g.strokeStyle = rgba(bcol, .16 + .18 * bn); g.lineWidth = w;
        g.beginPath(); g.moveTo(bA.x, bA.y); g.quadraticCurveTo(bcp.x, bcp.y, bB.x, bB.y); g.stroke();
        g.strokeStyle = rgba(bcol, .4 + .3 * bn); g.lineWidth = Math.max(1.6, w * .38);
        g.beginPath(); g.moveTo(bA.x, bA.y); g.quadraticCurveTo(bcp.x, bcp.y, bB.x, bB.y); g.stroke();
        // the gate — a bar at the control's exit that swings shut as blocks mount
        var gx = c.x + c.w / 2 + 10, gy = c.y, glen = 34;
        g.save(); g.translate(gx, gy - glen / 2); g.rotate(-.5 + bn * 1.15);
        g.strokeStyle = rgba(gcol, .9); g.lineWidth = 4;
        g.beginPath(); g.moveTo(0, 0); g.lineTo(0, glen); g.stroke();
        g.fillStyle = rgba(gcol, .9); g.beginPath(); g.arc(0, 0, 3.4, 0, 6.2832); g.fill();
        g.restore(); g.lineCap = "butt";
        sigLabel("gate · " + fmtOne(sr) + "× baseline", gx + 10, gy - glen / 2 - 12, rgba(gcol, .92));
        var bmid = bez(bA, bcp, bB, .55);
        sigLabel("blocked branch · " + fmtInt(blk), bmid.x, bmid.y + 22, rgba(bcol, .92));
        var gmid = bez(gA, gcp, gB, .5);
        sigLabel("settled leg · dark", gmid.x, gmid.y - 12, "rgba(140,124,102,.85)");
      }
      function sigWall(i) {
        var a = pts.idp, b = pts.svcs, gh2 = pts.ghost; if (!a || !b) return;
        var ls = series.customers_locked_out || [], lk = ls[i] || 0;
        var ln = Math.min(1, lk / (fieldMax.customers_locked_out || 1));
        var dark = (series.responder_lockout || [])[i] || 0;
        var fs = (series.auth_failure_rate_pct || [])[i] || 0;
        var sev = SEV.err ? SEV.err(fs) : "critical", col = CH[sev] || CH.critical;
        // the wall — a bar across the idp→services leg that RISES with lockouts
        var wx = (a.x + b.x) / 2, H = Math.min(110, stage.clientHeight * .26);
        var y1 = a.y + H / 2, wh = Math.max(4, H * ln);
        g.fillStyle = rgba(col, .2 + .3 * ln);
        g.fillRect(wx - 7, y1 - wh, 14, wh);
        g.strokeStyle = rgba(col, .85); g.lineWidth = 2;
        g.strokeRect(wx - 7, y1 - wh, 14, wh);
        // padlock hasp on top of the wall
        g.beginPath(); g.arc(wx, y1 - wh - 6, 6, Math.PI, 0); g.stroke();
        sigLabel("the wall · " + fmtInt(lk) + " locked out", wx, y1 + 16, rgba(col, .95));
        sigLabel(fmtOne(fs) + "% auth failing", wx, y1 + 28, "rgba(152,140,120,.8)");
        // the recursion, drawn: while responders are dark, their leg pulses red
        if (dark && gh2) {
          var mx2 = (a.x + gh2.x) / 2, my2 = (a.y + gh2.y) / 2;
          g.strokeStyle = rgba(CH.critical, .55 + Math.sin(animT * 3) * .2); g.lineWidth = 2.4; g.setLineDash([3, 5]);
          g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(gh2.x, gh2.y); g.stroke(); g.setLineDash([]);
          sigLabel("responders dark — locked out with the customers", mx2, my2 - 10, rgba(CH.critical, .92));
        }
      }
      function drawSig(i, casc) {
        if (d.domain_id === "kafka_lag_storm") sigTank(i);
        else if (d.domain_id === "deployment_cascade") sigCone(i, casc);
        else if (d.domain_id === "velocity_surge") sigFork(i);
        else if (d.domain_id === "identity_outage") sigWall(i);
      }

      function render() {
        var i = Math.floor(idx), casc = phaseAt(events, i) === "cascade";
        g.clearRect(0, 0, cv.width, cv.height);
        drawSig(i, casc);
        topo.edges.forEach(function (e) {
          var G = geom(e); if (!G) return;
          g.beginPath(); g.moveTo(G.a.x, G.a.y); g.quadraticCurveTo(G.cp.x, G.cp.y, G.b.x, G.b.y);
          if (e[3] === "mon") { var a = casc ? .18 + Math.sin(animT * 6) * .12 : .07; g.strokeStyle = rgba(CH.critical, a); g.lineWidth = casc ? 1.7 : 1.1; g.setLineDash([7, 6]); g.stroke(); g.setLineDash([]); }
          else if (e[3] === "blind") { g.strokeStyle = "rgba(111,98,80,.28)"; g.lineWidth = 1; g.setLineDash([3, 5]); g.stroke(); g.setLineDash([]); }
          else { g.strokeStyle = "rgba(152,140,120,.36)"; g.lineWidth = 2.4; g.stroke(); }
          // r48: direction is drawn, not implied — arrowheads on flow + monitor
          // edges (the ghost leg stays ghost: no signal, no claimed direction)
          if (e[3] !== "blind") {
            var pmH = bez(G.a, G.cp, G.b, 0.55), pmH2 = bez(G.a, G.cp, G.b, 0.6);
            var angH = Math.atan2(pmH2.y - pmH.y, pmH2.x - pmH.x);
            g.save(); g.translate(pmH.x, pmH.y); g.rotate(angH);
            g.fillStyle = e[3] === "mon" ? rgba(CH.critical, casc ? .55 : .28) : "rgba(152,140,120,.65)";
            g.beginPath(); g.moveTo(5.5, 0); g.lineTo(-3.5, -3.6); g.lineTo(-3.5, 3.6); g.closePath(); g.fill();
            g.restore();
          }
        });
        topo.edges.forEach(function (e) { if (e[3] === "flow" && e[2]) drawECG(e); });
        // edge callouts — which seeded telemetry rides each edge (the reference "real ✓" provenance treatment)
        topo.edges.forEach(function (e) {
          if (e[3] !== "flow" || !e[2]) return; var G = geom(e); if (!G) return;
          var mid = bez(G.a, G.cp, G.b, .5), lbl = (FIELD_LBL[e[2]] || e[2]) + " · seeded ✓";
          g.font = "600 8.5px ui-monospace, SFMono-Regular, monospace"; g.textAlign = "center";
          g.shadowColor = "rgba(0,0,0,.92)"; g.shadowBlur = 4; g.fillStyle = "rgba(127,159,201,.7)";
          g.fillText(lbl, mid.x, mid.y + 30); g.shadowBlur = 0;
        });
        parts.forEach(function (p) {
          var e = topo.edges[p.e], mon = e[3] === "mon", G = geom(e); if (!G) return;
          var sf = e[2] ? (series[e[2]] || []) : null;
          var rate = sf ? Math.min(1.6, (sf[i] || 0) / (fieldMax[e[2]] || 1) * 2.2) : .6;
          p.t += p.spd * (mon ? .55 : .55 + rate * .65) * .055; if (p.t > 1) p.t -= 1;
          var pos = bez(G.a, G.cp, G.b, p.t);
          var sev = mon ? (casc ? "critical" : "normal") : nodeSev(nodeById[e[1]] || {}, i);
          var col = CH[sev] || CH.normal, env = Math.sin(p.t * Math.PI), a = (mon ? .58 : .95) * env;
          g.fillStyle = rgba(col, a * .2); g.beginPath(); g.arc(pos.x, pos.y, mon ? 3.2 : 5, 0, 6.2832); g.fill();
          g.fillStyle = rgba(col, a); g.beginPath(); g.arc(pos.x, pos.y, mon ? 1.6 : 2.7, 0, 6.2832); g.fill();
        });
        topo.nodes.forEach(function (n) {
          var pt = pts[n.id]; if (!pt) return;
          var sev = nodeSev(n, i); if (sev === "normal") return;
          var col = CH[sev]; if (!col) return;
          var pulse = (sev === "critical" ? .22 : .12) + Math.sin(animT * (sev === "critical" ? 3.4 : 2.1) + pt.x * .01) * .07;
          var R = Math.max(pt.w, pt.h) * 1.15;
          var grd = g.createRadialGradient(pt.x, pt.y, R * .5, pt.x, pt.y, R);
          grd.addColorStop(0, rgba(col, pulse)); grd.addColorStop(1, rgba(col, 0));
          g.fillStyle = grd; g.beginPath(); g.arc(pt.x, pt.y, R, 0, 6.2832); g.fill();
        });
      }
      function loop(t) { raf = null; var dd = last ? Math.min(.05, (t - last) / 1000) : .016; last = t; animT += dd; render(); if (!paused() && driving()) raf = requestAnimationFrame(loop); }

      // ── controls ──
      function stopPlay() {
        playing = false; if (ptimer) { clearInterval(ptimer); ptimer = null; }
        var p = q('[data-obs="play"]'); if (p) { p.textContent = "▶ play"; p.classList.remove("on"); }
      }
      scrub.addEventListener("input", function () { stopPlay(); idx = +this.value; panels(idx); render(); });
      qa(".obs-mom").forEach(function (b) { b.addEventListener("click", function () { stopPlay(); idx = +this.dataset.idx; panels(idx); render(); }); });
      qa(".obs-spd button").forEach(function (b) { b.addEventListener("click", function () { speed = +this.dataset.spd; qa(".obs-spd button").forEach(function (x) { x.classList.toggle("on", x === b); }); }); });
      q('[data-obs="play"]').addEventListener("click", function () {
        if (playing) { stopPlay(); return; }
        playing = true; this.textContent = "⏸ pause"; this.classList.add("on");
        ptimer = setInterval(function () { idx += speed * 1.2; if (idx >= N - 1) idx = 0; animT += 0.08; panels(Math.floor(idx)); render(); }, 80);
      });

      // ── tour (3 steps at the named moments, from data) — narration is per-scenario
      //    and points at that scenario's signature shape (tank / cone / fork).
      var TOUR_TXT = {
        identity_outage: {
          "precursor": "Token issuance starts failing at the Identity plane — retry pressure builds from the customers and the wall at the front door begins to rise. The workforce-SSO leg is already flickering.",
          "cascade peak": "The plane goes down and the wall peaks — customers locked out of accounts and funds, and the responder leg runs dark: the people who fix identity authenticate THROUGH identity. Detection was instant; access is the bottleneck.",
          "recovery": "Break-glass restores tool access first, then the fallback token path reopens the front door into a re-auth surge; Response marks the incident audit-ready — the out-of-band evidence recorded straight through the lockout."
        },
        kafka_lag_storm: {
          "precursor": "Producer throughput holds steady while the consumer slips — the backlog tank between the Event Bus and the Consumer starts to fill. Downstream still reads green.",
          "cascade peak": "The backlog crests and the tank hits peak fill — the consumer stalls, downstream violates its SLO, and the feedback arc to Response lights.",
          "recovery": "The consumer catches up and the tank drains; Response marks the incident audit-ready — instrumented detection bought the regime gap over the manual checklist."
        },
        deployment_cascade: {
          "precursor": "The change ships and error rate starts climbing at the Service — the blast cone is still narrow and Downstream holds.",
          "cascade peak": "Error rate peaks and requests drop — the cone sweeps to its widest reach, toward the customer-order leg nobody can see.",
          "recovery": "The rollback lands and the cone collapses back toward the Service; Response marks the incident audit-ready — instrumented detection bought the regime gap over the manual checklist."
        },
        velocity_surge: {
          "precursor": "Transaction inflow climbs over baseline and the gate at the Velocity control starts to bite — the blocked branch is still thin.",
          "cascade peak": "The surge peaks and the gate swings shut — the blocked branch runs at its thickest while the settled leg to the partner banks stays dark.",
          "recovery": "Inflow eases back toward baseline and blocks clear; Response marks the incident audit-ready — instrumented detection bought the regime gap over the manual checklist."
        }
      };
      var tourMoments = moments.map(function (m) {
        var tx = TOUR_TXT[d.domain_id] || TOUR_TXT.kafka_lag_storm;
        return { i: m.i, tl: m.lbl.charAt(0).toUpperCase() + m.lbl.slice(1), bd: tx[m.lbl] || "" };
      });
      var tstep = -1, tourov = q('[data-obs="tourov"]');
      function showTour(sIdx) {
        tstep = sIdx; var tt = tourMoments[sIdx]; if (!tt) return;
        stopPlay(); idx = tt.i; panels(idx); render();
        tourov.style.display = "block";
        tourov.innerHTML = '<div class="obs-tour-tl">' + esc(tt.tl) + '</div><div class="obs-tour-bd">' + esc(tt.bd) + "</div>"
          + '<div class="obs-tour-ct"><span class="obs-tour-pg">step ' + (sIdx + 1) + " of " + tourMoments.length + "</span><span>"
          + '<button data-tour="exit">✕ exit</button>'
          + (sIdx < tourMoments.length - 1 ? '<button class="nx" data-tour="next">next →</button>' : '<button class="nx" data-tour="exit">✓ done</button>')
          + "</span></div>";
      }
      function endTour() { tstep = -1; tourov.style.display = "none"; }
      tourov.addEventListener("click", function (e) {
        var b = e.target.closest && e.target.closest("[data-tour]"); if (!b) return;
        if (b.getAttribute("data-tour") === "next") showTour(tstep + 1); else endTour();
      });
      q('[data-obs="tour"]').addEventListener("click", function () { if (tstep >= 0) endTour(); else showTour(0); });

      // ── act visibility & motion self-drive (MutationObserver on body, like the swimlane) ──
      function driving() { return document.body.dataset.act === "observatory"; }
      function start() { centers(); if (!parts.length) seed(); panels(idx); render(); if (!raf && !paused() && driving()) { last = 0; raf = requestAnimationFrame(loop); } }
      function stop() { if (raf) { cancelAnimationFrame(raf); raf = null; } }
      var onResize = function () { if (driving()) { centers(); render(); } };
      window.addEventListener("resize", onResize);
      var mo = window.MutationObserver ? new MutationObserver(function () { if (driving() && !paused()) start(); else stop(); }) : null;
      if (mo) mo.observe(document.body, { attributes: true, attributeFilter: ["class", "data-act"] });

      // ── first paint ──
      renderGap(); renderProv();
      // ensure geometry after layout settles (nodes get sized by CSS)
      requestAnimationFrame(function () { start(); });

      return {
        start: start, stop: stop,
        destroy: function () {
          stopPlay(); stop();
          if (mo) mo.disconnect();
          window.removeEventListener("resize", onResize);
        }
      };
    }

    function renderObservatory(d) {
      // tear down the previous instance (timers / observers / rAF) — no leaks
      if (obs) { obs.destroy(); obs = null; }
      ctx.setTarget("observatory", observatoryHtml(d));
      obs = makeObservatory(d);
    }

    function syncFlow() {
      if (!obs) return;
      if (document.body.dataset.act === "observatory") obs.start(); else obs.stop();
    }

    // hydrate the footer counts from the projection too — so NO mount ships baked
    // literals (closes the render-from-data drift hole the red-team caught).
    function renderFooter() {
      var c = meta.counts || {};
      ctx.setTarget("footer-counts", esc(c.scenarios_total) + " scenarios · "
        + esc(c.events_total) + " events · " + esc(c.kris_exercised) + " canonical KRIs");
    }

    function renderStage() {
      var d = domains[current] || {};
      renderHero(d); renderObservatory(d);
    }

    function _counts() { if (ctx.countUpAll) requestAnimationFrame(function () { ctx.countUpAll(); }); }
    return {
      renderAll: function (c) { renderRail(); renderStage(); renderFooter(); _counts(); },
      onDomainChange: function (id) { if (domains[id]) { current = id; renderRail(); renderStage(); _counts(); } },
      onActChange: function () { _counts(); syncFlow(); },
      onLensChange: function () {}
    };
  }

  function register() {
    if (window.PortfolioRuntime && window.PortfolioRuntime.registerDomain) {
      window.PortfolioRuntime.registerDomain(build(window.PortfolioRuntime));
    }
  }
  register();
})();
