/* portfolio_core runtime — domain-agnostic render-from-data plumbing.
 *
 * Shared across the portfolio (port spec §15.E step 2b). Provides: projection
 * load, DOM/format helpers, canonicalJson + sha256 + verifyChain (byte-matching
 * portfolio_core/action_log.py), the lineage modal, the verb modal (with the
 * named-human A8 gate), act/lens/domain switching, and a boot that calls the
 * domain's window.PortfolioDomain.renderAll(ctx). NO domain knowledge — the
 * domain registers its render functions + shell metadata.
 */
(function () {
  "use strict";

  // ── Load the embedded projection ──
  var PROJECTION = {};
  var projScript = document.getElementById("projection-source");
  if (projScript) {
    try { PROJECTION = JSON.parse(projScript.textContent || "{}"); }
    catch (e) { console.error("Failed to parse embedded projection:", e); }
  }

  // ── localStorage continuation of the attestation log ──
  // Namespace per project — both portfolio dashboards open as file:// share the
  // null origin + one localStorage; a single key would let an attestation made on
  // one dashboard bleed into the other's chain. Key off the brand (distinct per
  // project), falling back to the artefact version.
  function _lsKey() {
    var brand = document.querySelector(".brand-mark");
    var ns = (brand && brand.textContent.trim())
      || ((PROJECTION.meta || {}).artefact_version) || "default";
    return "portfolio_action_log:" + ns;
  }
  function loadLocalActions() {
    try {
      var raw = localStorage.getItem(_lsKey());
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter(function (e) { return e && typeof e === "object"; }) : [];
    } catch (e) { return []; }
  }
  function saveLocalActions(entries) {
    try { localStorage.setItem(_lsKey(), JSON.stringify(entries)); }
    catch (e) { console.warn("localStorage write failed:", e); }
  }
  function getAllActionEntries() {
    var embedded = ((PROJECTION.action_log || {}).recent_entries) || [];
    return embedded.concat(loadLocalActions());
  }

  // ── helpers ──
  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  // URL scheme allowlist — render-from-data must never emit javascript:/data: links
  function safeUrl(u) {
    var s = (u == null ? "" : String(u)).trim();
    return /^https?:\/\//i.test(s) ? s : "#";
  }
  function targets(name) { return document.querySelectorAll('[data-target="' + name + '"]'); }
  function setTarget(name, html) { targets(name).forEach(function (el) { el.innerHTML = html; }); }

  // ── canonical JSON byte-matching Python json.dumps(sort_keys=True, default=str)
  function _ensureAscii(str) {
    var out = "";
    for (var i = 0; i < str.length; i++) {
      var code = str.charCodeAt(i);
      // Python json.dumps(ensure_ascii=True) escapes every code point >= 0x7f
      // (DEL included — verified). The boundary MUST be >=, not >, or a 0x7f in
      // any signed field makes the JS recompute diverge → false chain BREAK.
      if (code >= 0x7f) { out += "\\u" + code.toString(16).padStart(4, "0"); }
      else { out += str[i]; }
    }
    return out;
  }
  // Match Python's number serialization for the SIGNED domain. Attestation
  // entries carry only integers (counts, cadences, word-counts) + strings; the
  // signer (action_log.py) forbids floats in hashed fields, so canonical JSON is
  // closed. We still guard: a non-integer/huge number can't be byte-matched by
  // String(), so we refuse to silently emit a diverging form.
  function _num(n) {
    if (!isFinite(n)) throw new Error("non-finite number in signed field");
    if (Number.isInteger(n) && Math.abs(n) <= 9007199254740991) return String(n);
    throw new Error("non-integer/oversized number in signed field: " + n);
  }
  function canonicalJson(obj) {
    if (obj === null || obj === undefined) return "null";
    if (typeof obj === "boolean") return obj ? "true" : "false";
    if (typeof obj === "number") return _num(obj);
    if (typeof obj === "string") return _ensureAscii(JSON.stringify(obj));
    if (Array.isArray(obj)) return "[" + obj.map(canonicalJson).join(", ") + "]";
    if (typeof obj === "object") {
      var keys = Object.keys(obj).sort();
      return "{" + keys.map(function (k) {
        return _ensureAscii(JSON.stringify(k)) + ": " + canonicalJson(obj[k]);
      }).join(", ") + "}";
    }
    return _ensureAscii(JSON.stringify(String(obj)));
  }
  async function sha256Hex(s) {
    var bytes = new TextEncoder().encode(s);
    var hash = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(hash)).map(function (b) {
      return b.toString(16).padStart(2, "0");
    }).join("");
  }

  // ── chain verification (content + link, honest about partial windows) ──
  async function verifyChain() {
    var entries = getAllActionEntries();
    if (!entries.length) return { valid: true, verified: 0, total: 0, partial: false, note: "no entries" };
    var contentOk = 0, linkOk = 0, brokenAt = null, reason = "";
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      var eMinus = {};
      Object.keys(e).forEach(function (k) { if (k !== "this_action_hash" && k !== "_local") eMinus[k] = e[k]; });
      var recomputed = null;
      try { recomputed = await sha256Hex(canonicalJson(eMinus)); }
      catch (err) { if (brokenAt === null) { brokenAt = i; reason = "uncanonicalizable entry " + i + " (" + err.message + ")"; } }
      if (recomputed && e.this_action_hash && recomputed === e.this_action_hash) contentOk++;
      else if (recomputed && e.this_action_hash && brokenAt === null) { brokenAt = i; reason = "content hash mismatch at entry " + i; }
      if (i > 0) {
        var prev = entries[i - 1];
        if (e.previous_action_hash && prev.this_action_hash && e.previous_action_hash === prev.this_action_hash) linkOk++;
        else if (e.previous_action_hash && prev.this_action_hash && brokenAt === null) { brokenAt = i; reason = "link break at " + i; }
      }
    }
    var partial = (entries[0].previous_action_hash !== "GENESIS");
    return { valid: brokenAt === null, verified: contentOk, total: entries.length, links_ok: linkOk,
             partial: partial, brokenAt: brokenAt, reason: reason,
             note: partial ? "window verified · full chain needs server-side log" : "full chain genesis→head" };
  }

  function renderChainStatus() {
    var el = document.getElementById("chain-status");
    if (!el) return;
    el.innerHTML = "chain · verifying…";
    verifyChain().then(function (res) {
      var label = res.valid
        ? (res.partial ? "verified " + res.verified + "/" + res.total + " (window)" : "intact " + res.verified + "/" + res.total)
        : "BREAK @ " + res.brokenAt;
      el.innerHTML = "chain · " + esc(label);
      el.setAttribute("data-state", res.valid ? "verified" : "broken");
      el.title = "live verifyChain() walk · " + res.note + (res.reason ? " · " + res.reason : "");
    }).catch(function (e) { el.innerHTML = "chain · verify-error"; el.setAttribute("data-state", "demo"); });
  }

  // ── artefact seal: SHA-256 over the embedded projection (the evidence
  //    payload). Independently verifiable — anyone can extract #projection-source
  //    and hash it — and recomputed live here so tamper-evidence is REAL, not an
  //    unverifiable footer string.
  async function verifyArtefactSeal() {
    var el = document.getElementById("artefact-seal-value");
    var status = document.getElementById("seal-status");
    var proj = document.getElementById("projection-source");
    if (!el || !proj) return null;
    var shown = (el.textContent || "").trim();
    try {
      var recomputed = await sha256Hex((proj.textContent || "").trim());
      var ok = (recomputed === shown);
      if (status) {
        status.textContent = ok ? " ✓ projection verified" : " ✗ SEAL MISMATCH";
        status.setAttribute("data-state", ok ? "verified" : "broken");
        status.title = ok ? "Recomputed SHA-256 of the embedded projection matches the seal."
                          : "Recomputed " + recomputed.slice(0, 12) + "… ≠ sealed " + shown.slice(0, 12) + "…";
      }
      return ok;
    } catch (e) {
      if (status) { status.textContent = " · seal verify-error"; }
      return null;
    }
  }

  // ── lineage modal ──
  function openLineage(rows, title, sub) {
    var m = document.getElementById("lineage-modal"); if (!m) return;
    var t = document.getElementById("lineage-title"); if (t) t.textContent = title || "Lineage";
    var s = document.getElementById("lineage-subtitle"); if (s) s.textContent = sub || "";
    var body = document.getElementById("lineage-body");
    if (body) body.innerHTML = (rows || []).map(function (r) {
      return '<div class="lin-row"><div class="lin-row-label">' + esc(r.label) + '</div><div class="lin-row-value">' + (r.html || esc(r.value || "")) + "</div></div>";
    }).join("");
    m.setAttribute("data-open", "true");
  }
  function closeLineage() { var m = document.getElementById("lineage-modal"); if (m) m.setAttribute("data-open", "false"); }

  // ── verb modal with the named-human A8 gate ──
  var JUST_MIN = 12;
  var _activeVerb = null, _activeTarget = null;
  function wordCount(s) { return (s || "").trim().split(/\s+/).filter(Boolean).length; }
  // A8: the actor must be a NAMED HUMAN, not a team/rotation/service handle.
  // Unicode-aware (accepts José García, Müller Hans, Иван Петров, and space-less
  // CJK names like 李明) while still rejecting org handles. Name-shape alone can't
  // fully distinguish a person from a team, so we also denylist org/role words —
  // in production this would gate against an SSO/roster, not a regex.
  var _ORG_HANDLE = /(^|[\s.\-])(teams?|rotations?|rota|on[-\s]?call|service\s+accounts?|accounts?|bots?|robots?|ops|admin|sysadmin|systems?|group|queue|desk|automation|pipeline|svc|daemon|cron|webhook|integration)([\s.\-]|$)/i;
  function actorIsNamedHuman(raw) {
    var v = (raw || "").trim();
    if (!v) return false;
    if (v.charAt(0) === "@") return false;            // handle
    if (/[_\/]/.test(v)) return false;                // slug
    if (_ORG_HANDLE.test(v)) return false;            // team/rotation/service handle
    // space-less CJK personal name (family+given written together)
    if (/^[㐀-鿿぀-ヿ가-힯]{2,}$/.test(v)) return true;
    // otherwise: >= 2 Unicode-letter tokens
    try { return /^[\p{L}][\p{L}.'’-]*(\s+[\p{L}][\p{L}.'’-]*)+$/u.test(v); }
    catch (e) { return /^[A-Za-z][A-Za-z.'’-]*(\s+[A-Za-z][A-Za-z.'’-]*)+$/.test(v); }
  }
  function _verbsNeedingExpiry() {
    return (((PROJECTION.action_log || {}).verbs_needing_expiry) || ["gate", "accept", "require_eval", "restrict_scope", "suppress"]);
  }
  function updateConfirmState() {
    var actor = document.getElementById("verb-actor"), just = document.getElementById("verb-justification"),
        exp = document.getElementById("verb-expiry"), conf = document.getElementById("verb-confirm-btn");
    if (!conf) return;
    var justOk = wordCount(just && just.value) >= JUST_MIN;
    var actorOk = actorIsNamedHuman(actor && actor.value);
    var expiryNeeded = _verbsNeedingExpiry().indexOf(_activeVerb) >= 0;
    var expiryOk = expiryNeeded ? !!(exp && exp.value) : true;
    conf.disabled = !(justOk && actorOk && expiryOk);
    var hint = document.getElementById("verb-actor-hint");
    if (hint) {
      var v = (actor && actor.value || "").trim();
      if (!v) { hint.removeAttribute("data-state"); hint.textContent = "Per A8 — name a person, not a team handle (e.g. D. Patel)."; }
      else if (!actorOk) { hint.setAttribute("data-state", "error"); hint.textContent = 'Per A8 — "' + v + '" is not a named human. Use a person’s name.'; }
      else { hint.setAttribute("data-state", "ok"); hint.textContent = "Named human ✓"; }
    }
  }
  function openVerb(verb, targetId, targetName, targetType) {
    _activeVerb = verb; _activeTarget = { id: targetId, name: targetName, type: targetType || "finding" };
    var ctx = document.getElementById("verb-context");
    if (ctx) ctx.innerHTML = "<b>" + esc(verb) + "</b> · " + esc(targetName || targetId);
    ["verb-actor", "verb-justification", "verb-expiry"].forEach(function (id) { var el = document.getElementById(id); if (el) el.value = ""; });
    updateConfirmState();
    var m = document.getElementById("verb-modal"); if (m) m.setAttribute("data-open", "true");
  }
  function closeVerb() { var m = document.getElementById("verb-modal"); if (m) m.setAttribute("data-open", "false"); }

  function wireVerbModal() {
    var actor = document.getElementById("verb-actor"), just = document.getElementById("verb-justification"),
        exp = document.getElementById("verb-expiry"), conf = document.getElementById("verb-confirm-btn"),
        cancel = document.getElementById("verb-cancel-btn");
    [actor, just, exp].forEach(function (el) { if (el) el.addEventListener("input", updateConfirmState); });
    if (cancel) cancel.addEventListener("click", closeVerb);
    if (conf) conf.addEventListener("click", async function () {
      var entries = getAllActionEntries();
      var lastHash = entries.length ? (entries[entries.length - 1].this_action_hash || "GENESIS") : "GENESIS";
      var entry = {
        schema_version: "1.0", actor_name: actor.value.trim(),
        actor_handle: "@" + actor.value.trim().split(/\s+/).join("").toLowerCase(),
        actor_role: "Self-attested · client session", actor_role_tier: "1LoD",
        verb: _activeVerb, target_type: _activeTarget.type, target_id: _activeTarget.id,
        target_name: _activeTarget.name, timestamp: new Date().toISOString(),
        justification: just.value, justification_min_words: JUST_MIN,
        expiry: exp.value || null, review_cadence_days: 30, dissenting_voice: null,
        linked_findings: [_activeTarget.id], thresholds_at_time: {}, previous_action_hash: lastHash, _local: true
      };
      var eForHash = {}; Object.keys(entry).forEach(function (k) { if (k !== "this_action_hash" && k !== "_local") eForHash[k] = entry[k]; });
      try { entry.this_action_hash = await sha256Hex(canonicalJson(eForHash)); }
      catch (e) { entry.this_action_hash = "unhashed-" + Date.now(); }
      var local = loadLocalActions(); local.push(entry); saveLocalActions(local);
      closeVerb();
      if (window.PortfolioDomain && window.PortfolioDomain.renderAll) window.PortfolioDomain.renderAll(CTX);
      renderChainStatus();
    });
  }

  // ── identity ribbon reflects the active user (generic chrome) ──
  function updateRibbon(chip) {
    if (!chip) return;
    var nameEl = chip.querySelector(".user-chip-name"), roleEl = chip.querySelector(".user-chip-role");
    var rn = document.getElementById("ribbon-name"), rr = document.getElementById("ribbon-role");
    if (rn && nameEl) rn.textContent = nameEl.textContent;
    if (rr && roleEl) rr.textContent = "· " + roleEl.textContent;
  }

  // ── act / lens / domain switching (body data-attrs drive [data-acts] visibility) ──
  // Scroll the first act-controlled section into view on switch. The always-on
  // region above the sections (banner + chrome + hero) can exceed a viewport, so
  // without this a tab click changes nothing the user can SEE — human cold-read
  // finding: "tabs change but the content stays the same."
  function scrollToActContent() {
    var first = null;
    document.querySelectorAll("[data-acts]").forEach(function (s) {
      if (!first && s.getBoundingClientRect().height > 0) first = s;
    });
    if (!first) return;
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    first.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }
  function wireSwitching() {
    document.querySelectorAll(".act-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.body.dataset.act = tab.dataset.act;
        document.querySelectorAll(".act-tab").forEach(function (t) { t.setAttribute("aria-pressed", t === tab ? "true" : "false"); });
        if (window.PortfolioDomain && window.PortfolioDomain.onActChange) window.PortfolioDomain.onActChange(tab.dataset.act, CTX);
        scrollToActContent();
      });
    });
    document.querySelectorAll(".user-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        document.body.dataset.lens = chip.dataset.lens;
        var act = chip.dataset.defaultAct; if (act) document.body.dataset.act = act;
        document.querySelectorAll(".user-chip").forEach(function (c) { c.setAttribute("aria-pressed", c === chip ? "true" : "false"); });
        if (act) document.querySelectorAll(".act-tab").forEach(function (t) { t.setAttribute("aria-pressed", t.dataset.act === act ? "true" : "false"); });
        updateRibbon(chip);
        if (window.PortfolioDomain && window.PortfolioDomain.onLensChange) window.PortfolioDomain.onLensChange(chip.dataset.lens, CTX);
      });
    });
    document.addEventListener("click", function (e) {
      var item = e.target.closest && e.target.closest(".rail-item[data-domain]");
      if (!item) return;
      document.body.dataset.domain = item.dataset.domain;
      document.querySelectorAll(".rail-item").forEach(function (i) { i.setAttribute("aria-pressed", i === item ? "true" : "false"); });
      if (window.PortfolioDomain && window.PortfolioDomain.onDomainChange) window.PortfolioDomain.onDomainChange(item.dataset.domain, CTX);
    });
  }

  // ── modal close wiring ──
  function wireModals() {
    ["lineage-modal", "verb-modal"].forEach(function (id) {
      var m = document.getElementById(id);
      if (m) m.addEventListener("click", function (e) { if (e.target.id === id) m.setAttribute("data-open", "false"); });
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeLineage(); closeVerb(); } });
    var lc = document.getElementById("lineage-close-btn"); if (lc) lc.addEventListener("click", closeLineage);
  }

  // ── the context handed to domain render functions ──
  var CTX = {
    PROJECTION: PROJECTION, esc: esc, safeUrl: safeUrl, setTarget: setTarget, targets: targets,
    openLineage: openLineage, openVerb: openVerb, canonicalJson: canonicalJson,
    sha256Hex: sha256Hex, verifyChain: verifyChain, getAllActionEntries: getAllActionEntries,
    renderChainStatus: renderChainStatus, verifyArtefactSeal: verifyArtefactSeal,
    countUpAll: countUpAll, disclosure: disclosure,
    shouldAnimate: function () { return !_paused(); },
  };
  window.PortfolioRuntime = CTX;

  // ── domain registration handshake (no reliance on script-tag ordering) ──
  var _booted = false;
  function _renderDomain() {
    if (window.PortfolioDomain && window.PortfolioDomain.renderAll) {
      window.PortfolioDomain.renderAll(CTX);
      return true;
    }
    return false;
  }
  CTX.registerDomain = function (d) { window.PortfolioDomain = d; if (_booted) _renderDomain(); };

  // ── count-up (shared) — CTX.countUpAll() eases every [data-countup] number 0→target.
  //    Domains call it after rendering, so numbers re-animate on act/scenario switch.
  //    Honest: if motion is paused / reduced, it shows the final value immediately (never
  //    animates a figure a reader is trying to read). Only animates numbers currently in
  //    the viewport, so off-screen acts don't churn. ──
  function _paused() { return document.body.classList.contains("anim-paused"); }
  function _fmt(v, dec) { return dec ? v.toFixed(dec) : Math.round(v).toLocaleString(); }
  function _inView(el) {
    var r = el.getBoundingClientRect();
    return r.bottom > 0 && r.top < (window.innerHeight || 800) && r.width > 0;
  }
  function countUp(el) {
    var target = parseFloat(el.getAttribute("data-countup"));
    if (isNaN(target)) return;
    var suffix = el.getAttribute("data-suffix") || "";
    var dec = el.hasAttribute("data-dec") ? +el.getAttribute("data-dec") : (target % 1 !== 0 ? 1 : 0);
    if (_paused() || !_inView(el)) { el.textContent = _fmt(target, dec) + suffix; return; }
    var dur = 850, t0 = null;
    el.textContent = _fmt(0, dec) + suffix;
    function step(ts) {
      if (!t0) t0 = ts;
      var p = Math.min(1, (ts - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = _fmt(target * e, dec) + suffix;
      if (p < 1 && !_paused()) requestAnimationFrame(step);
      else el.textContent = _fmt(target, dec) + suffix;
    }
    requestAnimationFrame(step);
  }
  function countUpAll(root) { (root || document).querySelectorAll("[data-countup]").forEach(countUp); }

  // ── progressive disclosure (shared) — collapsed row = caret + headline + right-aligned key
  //    figure (the verdict, readable WITHOUT expanding); detail opens on click. Kills walls of
  //    text cards. Height animates via grid-rows 0fr→1fr (no fixed-height guess); snaps with no
  //    transition under paused / reduced-motion. Header is a real <button> so Enter/Space + focus
  //    work for free. Build markup with CTX.disclosure({headline,key,sub,body,tone,open}). ──
  function disclosure(o) {
    o = o || {};
    var key = o.key != null && o.key !== "" ? '<span class="disc-key">' + o.key + "</span>" : "";
    var sub = o.sub ? '<span class="disc-sub">' + esc(o.sub) + "</span>" : "";
    return '<div class="disc' + (o.open ? " open" : "") + '"'
      + (o.tone ? ' data-tone="' + esc(o.tone) + '"' : "") + ">"
      + '<button class="disc-head" type="button" aria-expanded="' + (o.open ? "true" : "false") + '">'
      + '<span class="disc-caret" aria-hidden="true">▸</span>'
      + '<span class="disc-headline">' + esc(o.headline || "") + sub + "</span>"
      + key + "</button>"
      + '<div class="disc-body"><div class="disc-inner">' + (o.body || "") + "</div></div></div>";
  }
  function wireDisclosures() {
    document.addEventListener("click", function (e) {
      var head = e.target.closest && e.target.closest(".disc-head");
      if (!head || !head.parentNode) return;
      var disc = head.parentNode, willOpen = !disc.classList.contains("open");
      disc.classList.toggle("open", willOpen);
      head.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
  }

  // ── boot ──
  function boot() {
    _booted = true;
    wireSwitching();
    wireVerbModal();
    wireModals();
    wireDisclosures();
    var sealBtn = document.getElementById("verify-seal-btn");
    if (sealBtn) sealBtn.addEventListener("click", verifyArtefactSeal);
    // motion toggle — defaults to the reader's OS reduced-motion preference; manual override.
    var motionBtn = document.getElementById("motion-toggle");
    if (motionBtn) {
      var setPaused = function (p) {
        document.body.classList.toggle("anim-paused", p);
        motionBtn.setAttribute("aria-pressed", p ? "true" : "false");
        motionBtn.textContent = p ? "▶ motion" : "⏸ motion";
      };
      setPaused(!!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches));
      motionBtn.addEventListener("click", function () { setPaused(!document.body.classList.contains("anim-paused")); });
    }
    renderChainStatus();
    verifyArtefactSeal();
    if (!_renderDomain()) {
      console.warn("PortfolioRuntime: no PortfolioDomain registered at boot — "
        + "body stays empty until one registers via PortfolioRuntime.registerDomain().");
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
