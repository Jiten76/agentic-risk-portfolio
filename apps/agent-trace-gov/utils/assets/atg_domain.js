/* agent-trace-gov domain renderer — window.PortfolioDomain.
 *
 * Consumes the shared runtime's CTX (PROJECTION + helpers) and paints the five
 * ATG narrative acts from the embedded projection. NO data is minted here — every
 * value is read from PROJECTION and carries its provenance badge. The lineage
 * graph (PROPAGATE) is the first-paint hero (port spec §14.E / §15.G).
 *
 * Acts (internal id → label):
 *   signal   → SIGNAL     · what the governance pass fired
 *   pattern  → PROPAGATE  · how risk flows agent→system→external (the hero)
 *   impact   → IMPACT     · records / PII-flows exposed + framework materiality
 *   decide   → DECIDE     · ATG verbs on findings (named-human A8 gate)
 *   attest   → ATTEST     · hash-chained log + chain detail + precedent register
 */
(function () {
  "use strict";

  // ── value/provenance helpers ──
  function val(w) { return (w && typeof w === "object" && "value" in w) ? w.value : w; }
  function prov(w) { return (w && typeof w === "object" && w.provenance) ? w.provenance : {}; }
  // human navigation label for a workflow (WF-<hash> ids are opaque)
  function _wfLabel(P, wid) { var d = (P.domains || {})[wid]; return (d && d.label) || wid; }

  var PROV_LABEL = {
    real_query_real_data: "telemetry",
    real_query_synthesized_data: "counted",
    derived: "derived",
    published_standard: "standard",
    illustrative: "illustrative",
    absent: "not instrumented",
  };
  function provBadge(E, status, title) {
    var label = PROV_LABEL[status] || status || "—";
    return '<span class="prov-badge" data-prov="' + E(status || "") + '"'
      + (title ? ' title="' + E(title) + '"' : "") + ">" + E(label) + "</span>";
  }
  // render an absent value honestly ("—" + reason), or the value + a counted/derived badge
  function provValue(E, wrapped, opts) {
    opts = opts || {};
    var p = prov(wrapped), v = val(wrapped), status = p.source_status;
    if (status === "absent" || v === null || v === undefined) {
      return '<span class="val-absent" title="' + E(p.note || "not instrumented") + '">—</span> '
        + provBadge(E, "absent", p.note || "not instrumented");
    }
    var shown = (opts.fmt ? opts.fmt(v) : E(v));
    var t = p.computation || p.source_query || p.source_note || "";
    return '<span class="val">' + shown + "</span> " + provBadge(E, status, t);
  }

  var RAG_ORDER = { critical: 2, watch: 1, evidence: 0 };

  // ── workflow rail (the domain selector; rail = workflow per §14.E) ──
  function renderRail(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, domains = P.domains || {};
    var active = document.body.dataset.domain || "all";
    var ragRank = { critical: 0, watch: 1, evidence: 2 };
    // findings-bearing workflows first (worst rag, then most findings) so a user
    // browsing for "the relevant ones" sees them at the top; clean runs sink.
    var wids = Object.keys(domains).sort(function (a, b) {
      var da = domains[a], db = domains[b], na = (da.findings || []).length, nb = (db.findings || []).length;
      if ((na > 0) !== (nb > 0)) return na > 0 ? -1 : 1;
      var ra = ragRank[da.overall_rag] != null ? ragRank[da.overall_rag] : 3;
      var rb = ragRank[db.overall_rag] != null ? ragRank[db.overall_rag] : 3;
      if (ra !== rb) return ra - rb;
      if (nb !== na) return nb - na;
      return String(da.label || a).localeCompare(String(db.label || b));
    });
    var html = "";
    wids.forEach(function (wid) {
      var d = domains[wid], n = (d.findings || []).length, label = d.label || wid;
      html += '<div class="rail-item" data-domain="' + E(wid) + '" data-rag="' + E(d.overall_rag || "evidence")
        + '" aria-pressed="' + (active === wid ? "true" : "false") + '" title="' + E(label + " · " + wid + " · " + (d.scenario || "")) + '">'
        + '<span class="rail-text"><span class="rail-name">' + E(label) + "</span>"
        + '<span class="rail-id">' + E(wid) + "</span></span>"
        + '<span class="rail-badge">' + E(n) + "</span></div>";
    });
    ctx.setTarget("rail-domains", html);
    // keep the static "all" item's count in sync
    var allBadge = document.querySelector('[data-target="rail-count-all"]');
    if (allBadge) {
      var total = 0; Object.keys(domains).forEach(function (w) { total += (domains[w].findings || []).length; });
      allBadge.textContent = total;
    }
  }

  // ════════════════════════════════════════════════════════════════════
  // SIGNAL — posture hero + the firing queue
  // ════════════════════════════════════════════════════════════════════
  // per-workflow counts recomputed from findings + lineage, so the hero reflects
  // the rail selection instead of always showing portfolio totals (GROK review).
  function _scopedCounts(P, domain) {
    var findings = _allFindings(P, domain);
    var sev = { critical: 0, high: 0, medium: 0, low: 0 }, occ = 0;
    findings.forEach(function (f) { sev[f.severity] = (sev[f.severity] || 0) + 1; occ += f.occurrence_count; });
    var dist = {};
    ((P.lineage_graph || {}).edges || []).forEach(function (e) {
      if (e.workflow_id !== domain) return;
      var d = dist[e.from + "→" + e.to] = dist[e.from + "→" + e.to] || { pii: false, ext: false };
      d.pii = d.pii || e.pii; d.ext = d.ext || e.external;
    });
    var pii = 0, ext = 0;
    Object.keys(dist).forEach(function (k) { if (dist[k].pii) pii++; if (dist[k].ext) ext++; });
    return { findings_total: findings.length, critical: sev.critical, high: sev.high, medium: sev.medium,
             low: sev.low, pii_flows: pii, external_flows: ext, workflows_analyzed: 1, actions_traced: occ };
  }

  function renderSignalHero(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, m = P.meta || {}, cp = m.counts_provenance || {};
    var domain = document.body.dataset.domain || "all", scoped = domain !== "all";
    var c, scopeLabel, posture, actionsTile;
    if (scoped) {
      c = _scopedCounts(P, domain);
      scopeLabel = _wfLabel(P, domain);
      posture = c.critical ? "critical" : (c.findings_total ? "watch" : "clean");
      actionsTile = { k: "actions_traced", label: "RE occurrences", sub: "risk-events in this workflow" };
    } else {
      c = m.counts || {};
      scopeLabel = "all workflows";
      posture = m.overall_posture || "clean";
      actionsTile = { k: "actions_traced", label: "actions", sub: "trace steps governed" };
    }
    var rawOcc = (m.counts || {}).risk_events_total;
    var findSub = scoped ? "workflow × risk-event"
      : ("grouped · " + (rawOcc != null ? rawOcc + " raw occ" : "workflow × risk-event"));
    var tiles = [
      { k: "findings_total", label: "findings", sub: findSub, title: m.counts_gloss || "" },
      { k: "critical", label: "critical", sub: "sev = critical", rag: "critical" },
      { k: "high", label: "high", sub: "sev = high", rag: "critical" },
      { k: "pii_flows", label: "PII flows", sub: "distinct in lineage" },
      { k: "external_flows", label: "external flows", sub: "unauthorised egress", rag: "critical" },
      { k: "workflows_analyzed", label: "workflows", sub: "agentic runs traced" },
      actionsTile,
    ];
    var seedTxt = (m.run_seed != null) ? " · seed " + m.run_seed + " (reproducible)" : "";
    var html = '<div class="exec-hero-band" data-posture="' + E(posture) + '">'
      + '<div class="exec-hero-headline"><span class="exec-hero-posture">' + E(String(posture === "critical" ? "critical" : posture).toUpperCase())
      + '</span><span class="exec-hero-scope"' + (scoped ? ' title="' + E(domain) + '"' : "") + ">" + E(scopeLabel) + "</span>"
      + '<span class="exec-hero-sub">governance posture · ' + E(m.period || "")
      + ' · <span class="prov-inline">' + E(P.telemetry_status || "synthesised") + " input, real governance logic" + E(seedTxt) + "</span></span></div>"
      + '<div class="hero-tiles">';
    tiles.forEach(function (t) {
      var v = c[t.k] || 0, status = cp[t.k];
      html += '<div class="hero-tile"' + (t.rag && v ? ' data-rag="' + t.rag + '"' : "")
        + (t.title ? ' title="' + E(t.title) + '"' : "") + ">"
        + '<div class="hero-tile-num"' + (typeof v === "number" ? ' data-countup="' + v + '"' : "") + ">" + E(v) + "</div>"
        + '<div class="hero-tile-label">' + E(t.label) + "</div>"
        + '<div class="hero-tile-sub">' + E(t.sub) + "</div>"
        + (status ? '<div class="hero-tile-prov">' + provBadge(E, status) + "</div>" : "")
        + "</div>";
    });
    html += "</div></div>";
    ctx.setTarget("signal-hero", html);
  }

  function _allFindings(P, domainFilter) {
    var out = [];
    Object.keys(P.domains || {}).forEach(function (wid) {
      if (domainFilter && domainFilter !== "all" && wid !== domainFilter) return;
      (P.domains[wid].findings || []).forEach(function (f) { out.push(f); });
    });
    out.sort(function (a, b) {
      return (a._sort_rank - b._sort_rank) || (b.occurrence_count - a.occurrence_count);
    });
    return out;
  }

  function renderQueue(ctx, mount, withVerbs) {
    var E = ctx.esc, P = ctx.PROJECTION;
    var domain = document.body.dataset.domain || "all";
    var findings = _allFindings(P, domain);
    if (!findings.length) {
      ctx.setTarget(mount, '<div class="queue-empty">No findings for this selection — workflow traced clean.</div>');
      return;
    }
    var verbs = (P.action_log || {}).verbs_supported || [];
    // group by risk-event so the same RE across N workflows reads as ONE finding
    // class with N occurrences — not N near-identical rows (scanability).
    var groups = {};
    findings.forEach(function (f) { (groups[f.risk_event_id] = groups[f.risk_event_id] || []).push(f); });
    var order = Object.keys(groups).sort(function (a, b) {
      var ga = groups[a][0], gb = groups[b][0];
      return (ga._sort_rank - gb._sort_rank) || (groups[b].length - groups[a].length);
    });
    var html = "";
    order.forEach(function (re) {
      var items = groups[re], lead = items[0];
      var occ = items.reduce(function (s, f) { return s + f.occurrence_count; }, 0);
      var totalPII = items.reduce(function (s, f) { return s + (val(f.records_exposed.pii_flow_count) || 0); }, 0);
      var wfWord = items.length === 1 ? "workflow" : "workflows";
      html += '<div class="q-group" data-rag="' + E(lead.overall_rag) + '">'
        + '<div class="q-group-head">'
        + '<span class="q-sev sev-' + E(lead.severity) + '">' + E(lead.severity) + "</span>"
        + '<span class="q-re">' + E(re) + "</span>"
        + '<span class="q-name">' + E(lead.name) + "</span>"
        + '<span class="q-group-count">' + items.length + " " + wfWord + "</span>"
        + '<span class="q-group-meta">' + occ + " occ · " + totalPII + " PII flows</span>"
        + "</div>"
        + '<div class="q-group-body">';
      items.forEach(function (f) {
        var pii = val(f.records_exposed.pii_flow_count) || 0;
        html += '<div class="q-sub" data-finding="' + E(f.finding_id) + '">'
          + '<span class="q-sub-wf" title="' + E(f.workflow_id) + '">' + E(_wfLabel(P, f.workflow_id))
          + ' <span class="q-sub-id">' + E(f.workflow_id) + "</span></span>"
          + '<span class="q-sub-meta">×' + E(f.occurrence_count) + " · PII " + E(pii)
          + " · first " + provValue(E, f.first_detected) + "</span>"
          + '<button class="q-lineage lineage-link" type="button" data-finding="' + E(f.finding_id) + '" title="See the evidence trail">lineage ↪</button>';
        if (withVerbs) {
          html += '<span class="q-sub-act-hint">act ▾</span><span class="q-sub-verbs">';
          verbs.forEach(function (vb) {
            html += '<button class="verb-btn q-verb" type="button" data-verb="' + E(vb)
              + '" data-finding="' + E(f.finding_id) + '" data-name="' + E(re + " · " + f.name) + '">' + E(vb) + "</button>";
          });
          html += "</span>";
        }
        html += "</div>";
      });
      html += "</div></div>";
    });
    ctx.setTarget(mount, html);
  }

  // finding → lineage modal payload (the evidence trail)
  function openFindingLineage(ctx, fid) {
    var P = ctx.PROJECTION, E = ctx.esc, f = null;
    Object.keys(P.domains || {}).forEach(function (wid) {
      (P.domains[wid].findings || []).forEach(function (x) { if (x.finding_id === fid) f = x; });
    });
    if (!f) return;
    var rows = [
      { label: "risk event", value: f.risk_event_id + " · " + f.name },
      // r56: the rating carries its consequence basis and, where a notification
      // clock runs, the assessment chip — the severity defends itself
      { label: "severity", html: '<span class="q-sev sev-' + E(f.severity) + '">' + E(f.severity) + '</span>'
          + (f.severity_default && f.severity_default !== f.severity
              ? ' <span class="sev-floor">class default ' + E(f.severity_default) + '</span>' : '') },
      { label: "why this severity", value: f.severity_basis || "class default — no escalating or de-escalating consequence in the traces" },
    ].concat(f.notification_clock ? [
      { label: "notification clock", html: '<span class="clock-chip">⏱ ' + E(f.notification_clock.citation)
          + ' · ' + E(f.notification_clock.status) + '</span><div class="clock-note">' + E(f.notification_clock.note) + '</div>' },
    ] : []).concat([
      { label: "workflow", value: f.workflow_id },
      { label: "occurrences", value: String(f.occurrence_count) + " trace(s)" },
      { label: "affected agents", value: (f.affected_agents || []).join(", ") || "—" },
      { label: "affected targets", value: (f.affected_targets || []).join(", ") || "—" },
      { label: "data classes", value: (f.records_exposed.data_classes || []).join(", ") || "—" },
      { label: "first detected", html: provValue(E, f.first_detected) },
      { label: "last seen", html: provValue(E, f.last_seen) },
      { label: "PII flows exposed", html: provValue(E, f.records_exposed.pii_flow_count) },
      { label: "affected record count", html: provValue(E, f.records_exposed.record_count) },
      { label: "framework", value: f.framework || "—" },
    ]);
    ctx.openLineage(rows, f.risk_event_id + " — lineage", f.finding_id + " · evidence trail derived from simulated agent traces");
  }

  // ════════════════════════════════════════════════════════════════════
  // PROPAGATE — the lineage SVG hero (the signature surface)
  // ════════════════════════════════════════════════════════════════════
  function _dedupeEdges(edges) {
    var map = {};
    edges.forEach(function (e) {
      var key = e.from + "→" + e.to;
      var cur = map[key];
      if (!cur) {
        map[key] = {
          from: e.from, to: e.to, count: 1,
          pii: !!e.pii, external: !!e.external,
          risk_events: (e.risk_events || []).slice(),
          rag: e.rag, actions: e.action ? [e.action] : [],
        };
      } else {
        cur.count++;
        cur.pii = cur.pii || !!e.pii;
        cur.external = cur.external || !!e.external;
        (e.risk_events || []).forEach(function (r) { if (cur.risk_events.indexOf(r) < 0) cur.risk_events.push(r); });
        if ((RAG_ORDER[e.rag] || 0) > (RAG_ORDER[cur.rag] || 0)) cur.rag = e.rag;
        if (e.action && cur.actions.indexOf(e.action) < 0) cur.actions.push(e.action);
      }
    });
    return Object.keys(map).map(function (k) { return map[k]; });
  }

  function renderLineageHero(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, lg = P.lineage_graph || {};
    var domain = document.body.dataset.domain || "all";
    var rawEdges = (lg.edges || []).filter(function (e) {
      return domain === "all" || !e.workflow_id || e.workflow_id === domain;
    });
    var edges = _dedupeEdges(rawEdges);

    // external sinks = targets of an external edge
    var externalSinks = {};
    edges.forEach(function (e) { if (e.external) externalSinks[e.to] = true; });

    // ── humans in the loop (DERIVED from the attestation log) ──
    // This is a WORKFLOW-LEVEL attestation proxy, not an edge- or finding-level gate:
    // a flow counts as "gated" iff a named person attested ANY finding on its workflow
    // (escalate/gate preferred over certify as the gate-keeper). It means "a human
    // reviewed this workflow", not "a human specifically gated this external data flow".
    var gateActorByFinding = {};
    ((P.action_log || {}).recent_entries || []).forEach(function (en) {
      (en.linked_findings || []).forEach(function (fid) {
        if (!gateActorByFinding[fid] || en.verb === "escalate" || en.verb === "gate")
          gateActorByFinding[fid] = en.actor_name;
      });
    });
    function flowGateActor(wf) {
      if (!wf) return null;
      var actor = null;
      // exact workflow match (finding_id is "RE-nn-<workflow_id>") — not a fragile substring
      Object.keys(gateActorByFinding).forEach(function (fid) {
        if (fid === wf || fid.indexOf("-" + wf) >= 0) actor = gateActorByFinding[fid];
      });
      return actor;
    }
    // aggregate the RAW external flows (pre-dedupe) by route, with gate stats
    var flowGate = {}, gateKeepers = {};
    rawEdges.forEach(function (e) {
      if (!e.external) return;
      var k = e.from + "→" + e.to, actor = flowGateActor(e.workflow_id);
      var s = flowGate[k] || (flowGate[k] = { total: 0, ungated: 0, actors: [] });
      s.total++;
      if (actor) { if (s.actors.indexOf(actor) < 0) s.actors.push(actor); gateKeepers[actor] = true; }
      else s.ungated++;
    });
    var extTotal = 0, extUngated = 0, extGated = 0;
    Object.keys(flowGate).forEach(function (k) { extTotal += flowGate[k].total; extUngated += flowGate[k].ungated; extGated += flowGate[k].total - flowGate[k].ungated; });
    var keepers = Object.keys(gateKeepers);

    // nodes present in the (filtered) edge set
    var present = {};
    edges.forEach(function (e) { present[e.from] = true; present[e.to] = true; });
    var nodes = (lg.nodes || []).filter(function (n) { return present[n.id]; });
    // include edge endpoints missing from node list (defensive)
    var known = {}; nodes.forEach(function (n) { known[n.id] = true; });
    Object.keys(present).forEach(function (id) {
      if (!known[id]) { nodes.push({ id: id, type: "system", pii_touched: false }); known[id] = true; }
    });

    // column buckets: 0 agents · 1 systems · 2 external sinks
    var cols = [[], [], []];
    nodes.forEach(function (n) {
      var col = (n.type === "agent") ? 0 : (externalSinks[n.id] ? 2 : 1);
      cols[col].push(n);
    });

    // nodes touched by a critical (unauthorized-flow) edge → danger ring
    var danger = {};
    edges.forEach(function (e) { if (e.rag === "critical") { danger[e.from] = true; danger[e.to] = true; } });

    // layout
    var COLX = [150, 510, 850], NODE_W = 196, NODE_H = 34, ROW = 50, TOP = 92, PADX = 16;
    var maxRows = Math.max(cols[0].length, cols[1].length, cols[2].length, 1);
    var H = TOP + maxRows * ROW + 40;
    var W = 1000;
    var pos = {};
    cols.forEach(function (colNodes, ci) {
      var colH = colNodes.length * ROW;
      var startY = TOP + (maxRows * ROW - colH) / 2;
      colNodes.forEach(function (n, ri) {
        pos[n.id] = { x: COLX[ci], y: startY + ri * ROW + NODE_H / 2, col: ci };
      });
    });

    function nodeAnchor(id, side) {
      var p = pos[id]; if (!p) return null;
      return { x: p.x + (side === "out" ? NODE_W / 2 : -NODE_W / 2), y: p.y };
    }

    var ariaSummary = "Data-flow graph, agents to systems to external destinations: "
      + nodes.length + " nodes, " + edges.length + " distinct edges; "
      + (lg.external_flow_count || 0) + " external flows shown as thick red critical edges, "
      + (lg.pii_flow_count || 0) + " PII-bearing flows, "
      + ((lg.loop_edges || []).length) + " RE-08 multi-agent loops shown as dashed edges.";
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" class="lineage-svg" role="img" '
      + 'aria-label="' + E(ariaSummary) + '"><desc>' + E(ariaSummary) + "</desc>";

    // column headers
    var heads = ["AGENTS", "SYSTEMS / DATA", "EXTERNAL"];
    heads.forEach(function (t, i) {
      svg += '<text x="' + COLX[i] + '" y="56" class="lin-col-head" text-anchor="middle">' + E(t) + "</text>";
    });

    // edges first (under nodes)
    var gateMarkers = [];
    edges.forEach(function (e) {
      var a = nodeAnchor(e.from, "out"), b = nodeAnchor(e.to, "in");
      if (!a || !b) return;
      var isLoop = e.risk_events.indexOf("RE-08") >= 0;
      var gate = e.external ? flowGate[e.from + "→" + e.to] : null;
      var ungated = gate && gate.ungated > 0;
      var cls = "lin-edge rag-" + e.rag + (e.pii ? " is-pii" : "") + (e.external ? " is-external" : "")
        + (isLoop ? " is-loop" : "") + (ungated ? " no-gate" : (gate ? " is-gated" : ""));
      var mx = (a.x + b.x) / 2;
      var d;
      if (b.x <= a.x) {
        // back-edge / same-column → bow outward (loop or upstream)
        var bow = 60 + Math.abs(a.y - b.y) * 0.2;
        d = "M" + a.x + "," + a.y + " C" + (a.x + bow) + "," + (a.y - 40) + " " + (b.x - bow) + "," + (b.y - 40) + " " + b.x + "," + b.y;
      } else {
        d = "M" + a.x + "," + a.y + " C" + mx + "," + a.y + " " + mx + "," + b.y + " " + b.x + "," + b.y;
      }
      var title = e.from + " → " + e.to + (e.actions.length ? " · " + e.actions.join(", ") : "")
        + (e.risk_events.length ? " · " + e.risk_events.join(",") : "") + " · ×" + e.count;
      svg += '<path d="' + d + '" class="' + cls + '" fill="none"><title>' + E(title) + "</title></path>";
      // r48 (operator: direction must be drawn, not implied): a chevron rides
      // every flow at its midpoint — loops included, where it matters most.
      var c1x, c1y, c2x, c2y;
      if (b.x <= a.x) { var bow2 = 60 + Math.abs(a.y - b.y) * 0.2; c1x = a.x + bow2; c1y = a.y - 40; c2x = b.x - bow2; c2y = b.y - 40; }
      else { c1x = mx; c1y = a.y; c2x = mx; c2y = b.y; }
      var mxp = (a.x + 3 * c1x + 3 * c2x + b.x) / 8, myp = (a.y + 3 * c1y + 3 * c2y + b.y) / 8;
      var dxv = 0.75 * (c1x - a.x) + 1.5 * (c2x - c1x) + 0.75 * (b.x - c2x);
      var dyv = 0.75 * (c1y - a.y) + 1.5 * (c2y - c1y) + 0.75 * (b.y - c2y);
      svg += '<polygon points="6,0 -4,-4 -4,4" class="lin-arrow rag-' + e.rag + (isLoop ? " is-loop" : "") + '" transform="translate(' + mxp.toFixed(1) + ',' + myp.toFixed(1) + ') rotate(' + (Math.atan2(dyv, dxv) * 180 / Math.PI).toFixed(1) + ')"></polygon>';
      // human-in-the-loop gate marker, sitting ON the external flow at its midpoint
      if (gate) gateMarkers.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, g: gate });
    });

    // nodes
    nodes.forEach(function (n) {
      var p = pos[n.id]; if (!p) return;
      var x = p.x - NODE_W / 2, y = p.y - NODE_H / 2;
      var cls = "lin-node type-" + E(n.type) + (n.pii_touched ? " is-pii" : "") + (danger[n.id] ? " is-danger" : "")
        + (externalSinks[n.id] ? " is-external" : "");
      var label = n.id.length > 26 ? n.id.slice(0, 25) + "…" : n.id;
      svg += '<g class="' + cls + '">'
        + '<rect x="' + x + '" y="' + y + '" width="' + NODE_W + '" height="' + NODE_H + '" rx="7"></rect>'
        + '<text x="' + p.x + '" y="' + (p.y + 4) + '" text-anchor="middle" class="lin-node-label">' + E(label) + "</text>"
        + (n.pii_touched ? '<circle cx="' + (x + NODE_W - 10) + '" cy="' + (y + 9) + '" r="4" class="lin-pii-dot"></circle>' : "")
        + "<title>" + E(n.id + " · " + n.type + (n.pii_touched ? " · PII-touched" : "")) + "</title>"
        + "</g>";
    });

    // human-in-the-loop gate markers, ON the external flows (drawn above nodes)
    gateMarkers.forEach(function (m) {
      var g = m.g, gated = g.total - g.ungated, danger = g.ungated > 0;
      var who = g.actors.length ? "Reviewed by " + g.actors.join(", ") + " (maker-checker). " : "";
      var lbl = (gated ? "✓ " + gated + " via human" : "")
        + (gated && g.ungated ? "  ·  " : "")
        + (g.ungated ? "⚠ " + g.ungated + " no gate" : "");
      var w = 20 + lbl.length * 6.7;
      svg += '<g class="lin-gate ' + (danger ? "no-gate" : "is-gated") + '" transform="translate(' + m.x + "," + m.y + ')">'
        + '<rect x="' + (-w / 2) + '" y="-13" width="' + w + '" height="26" rx="13" class="lin-gate-pill"></rect>'
        + '<text x="0" y="4" text-anchor="middle" class="lin-gate-txt">' + E(lbl) + "</text>"
        + "<title>" + E(who + g.ungated + " of " + g.total + " flows on this route had no human gate") + "</title></g>";
    });

    svg += "</svg>";

    var legend = '<div class="lin-legend">'
      + '<span class="lin-leg"><i class="swatch no-gate"></i>external flow · no human gate</span>'
      + '<span class="lin-leg"><i class="swatch rag-critical"></i>RE-03 unauthorised external flow</span>'
      + '<span class="lin-leg"><i class="swatch is-loop"></i>RE-08 multi-agent loop</span>'
      + '<span class="lin-leg"><i class="swatch is-pii"></i>PII-bearing flow</span>'
      + '<span class="lin-leg"><i class="swatch rag-evidence"></i>governed flow</span>'
      + "</div>";

    var note = (lg.source_note || "");
    var stat = '<div class="lin-stat-row">'
      + '<span class="lin-stat" data-rag="critical"><b>' + E(lg.external_flow_count || 0) + "</b> external flows</span>"
      + '<span class="lin-stat"><b>' + E(lg.pii_flow_count || 0) + "</b> PII flows</span>"
      + '<span class="lin-stat"><b>' + E((lg.loop_edges || []).length) + "</b> RE-08 loops</span>"
      + '<span class="lin-stat"><b>' + E(edges.length) + "</b> distinct edges · " + E(nodes.length) + " nodes</span>"
      + provBadge(E, lg.source_status, note) + "</div>";

    // ── the headline: what this flow actually tells you, computed from the data ──
    var insightSev = extUngated > 0 ? "high" : "ok";
    var proxyTag = ' <span class="lin-proxy-tag" title="A named human attested the WORKFLOW, not this specific edge — see below">workflow-level</span>';
    var insightHead = extUngated > 0
      ? extUngated + " of " + extTotal + " external flows had <strong>no human gate</strong>" + proxyTag
      : "All " + extTotal + " external flows passed a human gate" + proxyTag;
    var keeperLine = (keepers.length
      ? "Humans in the loop: " + keepers.map(E).join(" · ") + " — reviewed " + extGated + " of " + extTotal + " external flows"
      : "No human gate was attested on any external flow in this run")
      + " · workflow-level attestation (a human reviewed the workflow, not the specific edge)";
    var banner = '<div class="lin-insight" data-sev="' + insightSev + '">'
      + '<span class="lin-insight-icon" aria-hidden="true">' + (extUngated > 0 ? "⚠" : "✓") + "</span>"
      + '<span class="lin-insight-text"><span class="lin-insight-head">' + insightHead + "</span>"
      + '<span class="lin-insight-sub">' + keeperLine + "</span></span></div>";

    ctx.setTarget("lineage-hero", banner + stat + '<div class="lineage-canvas">' + svg + "</div>" + legend
      + '<div class="lin-foot">' + E(note) + "</div>");
  }

  function renderPatternPrimer(ctx) {
    var E = ctx.esc, S = ctx.safeUrl, P = ctx.PROJECTION, pm = P.patterns_meta || {};
    var firing = {};
    Object.keys(P.domains || {}).forEach(function (wid) {
      (P.domains[wid].findings || []).forEach(function (f) { firing[f.risk_event_id] = true; });
    });
    var pats = pm.patterns || [];
    var firingCount = pats.filter(function (re) { return firing[re.id]; }).length;
    var toneOf = function (s) { return (s === "critical" || s === "high") ? "risk" : (s === "medium" ? "warn" : ""); };
    // Show what matters: firing patterns open, clean ones collapsed to a scannable row.
    var html = '<div class="primer-summary"><strong>' + firingCount + " of " + pats.length
      + "</strong> risk-event patterns firing in this run &middot; firing open, clean collapsed</div>";
    pats.forEach(function (re) {
      var lit = !!firing[re.id];
      var key = lit ? '<span class="primer-firing">● firing</span>' : '<span class="primer-clean">clean</span>';
      var body = '<div class="primer-desc">' + E(re.description) + "</div>"
        + '<div class="primer-fw">' + (re.framework_source_url
            ? '<a href="' + E(S(re.framework_source_url)) + '" target="_blank" rel="noopener">' + E(re.framework) + " ↪</a>"
            : E(re.framework)) + "</div>";
      // r56: the class value is the FLOOR, said so — findings carry the
      // consequence-derived rating; this register carries the default
      html += ctx.disclosure({
        headline: re.id + " · " + re.name,
        sub: "default " + re.severity_default,
        key: key,
        tone: lit ? toneOf(re.severity_default) : "",
        open: lit,
        body: body,
      });
    });
    ctx.setTarget("pattern-primer", html);
  }

  // ════════════════════════════════════════════════════════════════════
  // IMPACT — records-exposed magnitude + framework materiality
  // ════════════════════════════════════════════════════════════════════
  function renderMagnitude(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, mg = P.magnitude || {};
    var html = '<div class="mag-card">'
      + '<div class="mag-eyebrow">MAGNITUDE · PII-bearing / external flows <span class="scope-note">portfolio</span><span class="mag-axis">distinct lineage flows — not a dollar figure, not the Art. 33(1)(a) records quantity</span></div>'
      + '<div class="mag-grid">'
      + '<div class="mag-tile"><div class="mag-num">' + provValue(E, mg.pii_flows_exposed) + '</div><div class="mag-label">distinct PII-bearing flows</div></div>'
      + '<div class="mag-tile" data-rag="critical"><div class="mag-num">' + provValue(E, mg.external_flows) + '</div><div class="mag-label">distinct external / cross-border flows</div></div>'
      + '<div class="mag-tile"><div class="mag-num mag-classes">' + ((mg.data_classes || []).map(E).join(", ") || "—")
        + '</div><div class="mag-label">data classes touched</div></div>'
      + "</div>"
      + '<div class="mag-secondary">raw traversals (same flow across workflows): '
        + provValue(E, mg.pii_flow_traversals) + ' PII · ' + provValue(E, mg.external_flow_traversals) + ' external</div>'
      + '<div class="mag-foot"><span class="mag-caveat">Affected-record / data-subject count is <strong>not carried in the traces</strong>, so it is not shown &mdash; we don\'t fabricate one. The Art. 33(1)(a) quantity is a Legal/Compliance determination.</span> '
        + E(mg.source_note || "") + "</div></div>";
    ctx.setTarget("impact-magnitude", html);
  }

  function renderMateriality(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, mt = P.materiality || {};
    var keys = Object.keys(mt);
    var JORDER = ["US", "EU", "Cross-cutting"];
    var jLabel = { US: "United States", EU: "European Union", "Cross-cutting": "Cross-cutting standards" };
    var triggered = keys.filter(function (k) { return mt[k].status === "TRIGGERED"; });
    var clear = keys.filter(function (k) { return mt[k].status !== "TRIGGERED"; });
    var cov = { US: 0, EU: 0, "Cross-cutting": 0 };
    triggered.forEach(function (k) { cov[mt[k].jurisdiction] = (cov[mt[k].jurisdiction] || 0) + 1; });
    function tile(k) {
      var m = mt[k];
      return '<div class="mat-tile is-triggered">'
        + '<div class="mat-status">● TRIGGERED</div>'
        + '<div class="mat-cite">' + E(m.regulation_citation) + "</div>"
        + '<div class="mat-triggered-by">triggered by ' + (m.triggered_patterns || []).map(E).join(", ") + "</div>"
        + '<div class="mat-note">' + E((m.provenance || {}).computation || "") + "</div></div>";
    }
    function clearTile(k) {
      var m = mt[k];
      return '<div class="mat-tile"><div class="mat-status">○ clear</div>'
        + '<div class="mat-cite">' + E(m.regulation_citation) + "</div>"
        + '<div class="mat-triggered-by">no firing risk-event triggers this framework</div></div>';
    }
    var html = '<div class="mat-coverage"><strong>' + triggered.length + " of " + keys.length
      + "</strong> obligations triggered by these findings &middot; "
      + '<span class="mat-jur us">US ' + (cov.US || 0) + "</span> "
      + '<span class="mat-jur eu">EU ' + (cov.EU || 0) + "</span> "
      + '<span class="mat-jur xc">cross-cutting ' + (cov["Cross-cutting"] || 0) + "</span></div>";
    JORDER.forEach(function (j) {
      var inJ = triggered.filter(function (k) { return mt[k].jurisdiction === j; });
      if (!inJ.length) return;
      html += '<div class="mat-group"><div class="mat-group-label">' + E(jLabel[j]) + " &middot; " + inJ.length
        + '</div><div class="mat-grid">' + inJ.map(tile).join("") + "</div></div>";
    });
    if (clear.length) {
      html += '<details class="mat-clear"><summary>' + clear.length + " framework"
        + (clear.length > 1 ? "s" : "") + " not triggered by these findings &mdash; show</summary>"
        + '<div class="mat-grid">' + clear.map(clearTile).join("") + "</div></details>";
    }
    ctx.setTarget("impact-materiality", html);
  }

  // ════════════════════════════════════════════════════════════════════
  // PROPAGATE — the agent estate's shared-dependency layer (structural twin
  // of rac's dependency tornado, in atg units: workflows / finding classes)
  // ════════════════════════════════════════════════════════════════════
  function renderAgentDeps(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, dl = P.agent_dependency_layer || {};
    var nodes = dl.nodes || [];
    if (!nodes.length) { ctx.setTarget("agent-dependencies", '<div class="atg-panel-sub">agent_dependency_layer not in projection.</div>'); return; }
    var total = dl.workflows_total || 0;
    var html = '<div class="dep-onething" style="font-size:14px; line-height:1.55; margin-bottom:12px; padding:10px 12px; border-left:3px solid var(--critical, #e5484d); background:rgba(229,72,77,.06)">'
      + E(dl.one_thing || '') + '</div>';
    nodes.forEach(function (n) {
      var pct = total ? Math.round(n.workflows_affected / total * 100) : 0;
      html += '<div class="dep-row" style="margin-bottom:13px">'
        + '<div style="display:flex; justify-content:space-between; align-items:baseline; gap:8px">'
        + '<span style="font-weight:600">' + E(n.name) + '</span>'
        + '<span style="font-family:var(--font-mono, monospace); font-size:12px" title="' + E(n.blast_basis) + '">'
        + n.workflows_affected + ' / ' + total + ' workflows</span></div>'
        + '<div style="height:8px; border-radius:4px; background:rgba(255,255,255,.07); margin:5px 0 4px; overflow:hidden">'
        + '<div style="height:100%; width:' + pct + '%; background:var(--critical, #e5484d); opacity:.75"></div></div>'
        + '<div style="font-size:12px; color:var(--text-mut, #999); line-height:1.5">'
        + 'loss: ' + E((n.loss_effect || '').split('—')[0].trim())
        + (n.blindness_re && n.blindness_re.length
            ? ' · <b style="color:var(--text, #ddd)">blindness unmasks ' + n.blindness_re.length
              + ' finding class' + (n.blindness_re.length > 1 ? 'es' : '') + '</b> ('
              + n.blindness_re.join(', ') + ') — ' + n.findings_at_stake + ' of ' + (dl.findings_total || 0)
              + ' current findings sit in those classes'
            : '')
        + (n.rac_analog ? ' · <span class="illustrative-tag" title="same mechanism, priced in dollars on the infrastructure substrate — see rac data/dependency_catalog.json">rac analog: ' + E(n.rac_analog) + '</span>' : '')
        + (n.anchors && n.anchors.length ? '<br>anchors: ' + n.anchors.map(function (a) {
            return E(a.date + ' ' + a.name) + (a.label === 'CLASS_ANALOG' ? ' <i>(class analog — declared)</i>' : '');
          }).join(' · ') : '')
        + '</div></div>';
    });
    html += '<div style="font-size:11px; color:var(--text-mut, #888); border-top:1px solid rgba(255,255,255,.1); padding-top:8px; margin-top:4px">'
      + E(dl.units_note || '') + '<br><b>DECLARED DEFERRALS:</b> '
      + ((dl.deferred_nodes || {}).classes || []).join(' · ') + '</div>';
    ctx.setTarget("agent-dependencies", html);
  }

  // ════════════════════════════════════════════════════════════════════
  // DECIDE — ATG verb affordances on findings
  // ════════════════════════════════════════════════════════════════════
  function renderVerbBar(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, al = P.action_log || {};
    var verbs = al.verbs_supported || [], needExp = al.verbs_needing_expiry || [];
    var html = '<div class="verbbar-eyebrow">ATG action vocabulary · every action requires a named human + ≥12-word justification'
      + ' <span class="verbbar-a8">(A8 gate, enforced in-browser)</span></div><div class="verbbar">';
    verbs.forEach(function (v) {
      var exp = needExp.indexOf(v) >= 0;
      html += '<span class="verbbar-chip">' + E(v) + (exp ? ' <span class="verbbar-exp">⧗ expiry</span>' : "") + "</span>";
    });
    html += "</div>";
    ctx.setTarget("decide-verbs", html);
  }

  // ════════════════════════════════════════════════════════════════════
  // ATTEST — hash-chained log + chain detail + precedent register
  // ════════════════════════════════════════════════════════════════════
  function renderActionLog(ctx) {
    var E = ctx.esc, entries = ctx.getAllActionEntries();
    if (!entries.length) {
      ctx.setTarget("attest-log", '<div class="action-log-empty">No attestations yet. Act on a finding in DECIDE — '
        + 'each confirmed action is hash-chained into this append-only log and verified live in your browser.</div>');
      return;
    }
    var html = "";
    entries.slice().reverse().forEach(function (e) {
      var local = e._local;
      html += '<div class="action-log-entry">'
        + '<div class="action-log-head"><span class="action-log-verb">' + E(e.verb) + "</span>"
        + '<span class="action-log-target">' + E(e.target_name || e.target_id || "") + "</span>"
        + (local ? '<span class="action-log-local-badge">this session</span>' : "") + "</div>"
        + '<div class="action-log-meta"><span class="action-log-actor">' + E(e.actor_name || "")
        + '</span> <span class="action-log-role">' + E(e.actor_role || "") + "</span>"
        + (e.expiry ? ' · expiry ' + E(e.expiry) : "") + "</div>"
        + '<div class="action-log-justification">' + E(e.justification || "") + "</div>"
        + '<div class="action-log-hash" title="SHA-256 over canonical entry">⛓ ' + E((e.this_action_hash || "").slice(0, 18)) + "…</div>"
        + "</div>";
    });
    ctx.setTarget("attest-log", html);
  }

  function renderChainDetail(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, al = P.action_log || {};
    ctx.verifyChain().then(function (res) {
      var rows = [
        ["embedded entries", String((al.recent_entries || []).length) + " (server log: " + (al.total_entries || 0) + ")"],
        ["verified content hashes", res.verified + " / " + res.total],
        ["link integrity", (res.links_ok || 0) + " links"],
        ["chain", res.valid ? (res.partial ? "window-verified" : "genesis→head intact") : "BREAK @ " + res.brokenAt],
        ["algorithm", "SHA-256 over canonical JSON (sort_keys, ensure_ascii) — byte-matches the Python signer"],
      ];
      var html = '<div class="chain-detail">';
      rows.forEach(function (r) {
        html += '<div class="chain-detail-row"><span class="chain-detail-label">' + E(r[0])
          + '</span><span class="chain-detail-value">' + E(r[1]) + "</span></div>";
      });
      html += '<div class="chain-detail-note">' + E(res.note || "") + "</div></div>";
      ctx.setTarget("attest-chain", html);
    });
  }

  function renderPrecedent(ctx) {
    var E = ctx.esc, S = ctx.safeUrl, P = ctx.PROJECTION, pm = P.patterns_meta || {};
    var html = '<div class="precedent-intro">Regulatory precedent register — incident anchors are keyed to the RE <b>class</b>, '
      + 'never co-located with a finding’s magnitude (port spec §14.A.3).</div><div class="precedent-list">';
    var any = false;
    (pm.patterns || []).forEach(function (re) {
      (re.anchors || []).forEach(function (a) {
        any = true;
        html += '<div class="precedent-row"><div class="precedent-re">' + E(re.id) + "</div>"
          + '<div class="precedent-body"><div class="precedent-name">'
          + (a.url ? '<a href="' + E(S(a.url)) + '" target="_blank" rel="noopener">' + E(a.name) + " ↪</a>" : E(a.name))
          + ' <span class="precedent-date">' + E(a.date) + "</span></div>"
          + '<div class="precedent-sum">' + E(a.summary) + "</div></div></div>";
      });
    });
    html += "</div>";
    if (!any) html = '<div class="precedent-intro">No incident anchors registered for the firing RE classes.</div>';
    ctx.setTarget("attest-precedent", html);
  }

  function renderEvalEfficacy(ctx) {
    var E = ctx.esc, P = ctx.PROJECTION, de = (P.meta || {}).detection_eval;
    if (!de) { ctx.setTarget("eval-efficacy", '<div class="atg-panel-sub">detection_eval not in projection.</div>'); return; }
    var html = '<div class="eval-hero">'
      + '<div class="eval-cell"><div class="eval-big">' + E(de.tp) + '</div><div class="eval-lbl">in-class variants caught</div></div>'
      + '<div class="eval-cell"><div class="eval-big">' + E(de.near_miss) + '</div><div class="eval-lbl">near-misses cleanly rejected</div></div>'
      + '<div class="eval-cell eval-warn"><div class="eval-big">' + E(String(de.false_fires)) + '</div><div class="eval-lbl">false fires</div></div>'
      + "</div><div class='eval-rows'>";
    (de.by_class || []).forEach(function (r) {
      html += '<div class="eval-row"><span class="eval-k">' + E(r.cls) + " · " + E(r.name)
        + '</span><span class="eval-v">' + E(r.tp) + " caught · " + E(r.near_miss) + " near-miss clean</span></div>";
    });
    html += '<div class="eval-row"><span class="eval-k">rule boundaries documented</span><span class="eval-v eval-dim">'
      + E(String(de.boundaries_documented)) + " · named in the record</span></div></div>";
    (de.coverage_gap_rows || []).forEach(function (g) {
      html += '<div class="eval-gap"><b>Open coverage gap, stated:</b> ' + E(g.cls) + " " + E(g.name) + " — " + E(g.note) + "</div>";
    });
    html += '<div class="eval-closure"><b>The loop closes through a human, deliberately.</b> '
      + "A governor that tunes itself on what it measures marks its own homework. This eval is "
      + E(de.loop_closure) + ".</div>"
      + '<div class="eval-prov">' + E(de.source) + " · catalog sha " + E(de.catalog_sha12)
      + " · " + E(String(de.injections_total)) + " injections · no RNG · byte-verified by gate C23 each build</div>";
    ctx.setTarget("eval-efficacy", html);
  }

  // ── delegated interactions ──
  var _wired = false;
  function wireDomain(ctx) {
    if (_wired) return; _wired = true;
    document.addEventListener("click", function (ev) {
      var lin = ev.target.closest && ev.target.closest(".q-lineage[data-finding], .lineage-link[data-finding]");
      if (lin) { ev.preventDefault(); openFindingLineage(ctx, lin.getAttribute("data-finding")); return; }
      var vb = ev.target.closest && ev.target.closest(".q-verb[data-verb]");
      if (vb) {
        ev.preventDefault();
        ctx.openVerb(vb.getAttribute("data-verb"), vb.getAttribute("data-finding"), vb.getAttribute("data-name"), "finding");
      }
    });
  }

  // ════════════════════════════════════════════════════════════════════
  function renderAll(ctx) {
    wireDomain(ctx);
    renderRail(ctx);
    renderSignalHero(ctx);
    renderQueue(ctx, "signal-queue", false);
    renderLineageHero(ctx);
    renderPatternPrimer(ctx);
    renderAgentDeps(ctx);
    renderMagnitude(ctx);
    renderMateriality(ctx);
    renderVerbBar(ctx);
    renderQueue(ctx, "decide-queue", true);
    renderActionLog(ctx);
    renderChainDetail(ctx);
    renderPrecedent(ctx);
    renderEvalEfficacy(ctx);
    if (ctx.countUpAll) requestAnimationFrame(function () { ctx.countUpAll(); });
  }

  function onDomainChange(_d, ctx) {
    renderSignalHero(ctx);
    renderQueue(ctx, "signal-queue", false);
    renderLineageHero(ctx);
    renderQueue(ctx, "decide-queue", true);
  }

  window.PortfolioDomain = {
    renderAll: renderAll,
    onDomainChange: onDomainChange,
    onActChange: function (_a, ctx) { if (ctx && ctx.countUpAll) requestAnimationFrame(function () { ctx.countUpAll(); }); },
    onLensChange: function () {},
  };
})();
