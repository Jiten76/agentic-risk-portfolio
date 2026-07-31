/* ============================================================================
 * flowfield.js — shared canvas particle-flow + topology renderer (portfolio hub)
 *
 * The directional "observatory" primitive: services/stages are NODES, the flows
 * between them are EDGES, and particles stream along each edge — particle DENSITY
 * encodes rate, COLOUR encodes severity (warm = normal, amber = watch, red =
 * critical), and node heat-halos pulse by severity. It reads its whole world from a
 * spec the caller builds FROM THE PROJECTION — it invents no numbers, so a
 * render-from-data dashboard stays seal-honest.
 *
 * Honesty of motion (fixes the reference's gaps):
 *   • Respects body.anim-paused OR prefers-reduced-motion → renders ONE static
 *     frame (edges as dashed lines with evenly-spaced dots sized by rate, nodes
 *     lit to their severity) and stops advancing. Never animates under a reader.
 *   • Particles represent PROJECTED/seeded event units, not a live feed.
 *
 * API:
 *   var ff = new FlowField(canvasEl, spec, {onHover: fn, palette: {...}});
 *   ff.resize(); ff.start();      // begin (or re-draw static frame if paused)
 *   ff.setSpec(newSpec);          // swap scenario; keeps running
 *   ff.stop();                    // halt the loop (call when the view is hidden)
 * spec = { nodes:[{id,x,y,label,sub,severity,tier}], edges:[{from,to,rate,severity,label}] }
 *   x,y are normalized 0..1 (baked to px on resize — layout survives any size).
 *   rate is 0..1 (relative flow); severity ∈ 'normal'|'watch'|'critical'.
 * ==========================================================================*/
(function () {
  "use strict";

  var DEFAULT_PALETTE = {
    normal: "#E8DFD3",   // warm text — the calm, normal world
    watch: "#E0913A",    // amber — elevated
    critical: "#C24A38",  // red — hot / over-limit
    node: "rgba(224,145,58,0.10)",
    nodeStroke: "rgba(224,145,58,0.55)",
    label: "#E8DFD3",
    sub: "rgba(232,223,211,0.55)",
    grid: "rgba(232,223,211,0.06)",
  };

  function sevColor(pal, sev) { return pal[sev] || pal.normal; }

  function FlowField(canvas, spec, opts) {
    opts = opts || {};
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.pal = {};
    for (var k in DEFAULT_PALETTE) this.pal[k] = DEFAULT_PALETTE[k];
    if (opts.palette) for (var k2 in opts.palette) this.pal[k2] = opts.palette[k2];
    this.onHover = opts.onHover || null;
    this.spec = spec || { nodes: [], edges: [] };
    this.particles = [];
    this.spawnAcc = {};        // per-edge fractional spawn accumulator
    this._cp = {};             // per-edge control point cache (recomputed on resize)
    this._raf = null;
    this._animT = 0;
    this._hover = null;
    this._dpr = 1;
    this._W = 0; this._H = 0;
    this._boundMove = this._onMove.bind(this);
    this._boundLeave = this._onLeave.bind(this);
    canvas.addEventListener("mousemove", this._boundMove);
    canvas.addEventListener("mouseleave", this._boundLeave);
    // self-manage the ⏸ motion toggle: when body.anim-paused flips, re-settle.
    var self = this;
    if (window.MutationObserver) {
      this._mo = new MutationObserver(function () { self.setPaused(); });
      this._mo.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    }
    this._boundResize = function () { self.resize(); if (!self._paused()) self.start(); };
    window.addEventListener("resize", this._boundResize);
  }

  FlowField.prototype.destroy = function () {
    this.stop();
    this.canvas.removeEventListener("mousemove", this._boundMove);
    this.canvas.removeEventListener("mouseleave", this._boundLeave);
    window.removeEventListener("resize", this._boundResize);
    if (this._mo) this._mo.disconnect();
  };

  FlowField.prototype.setSpec = function (spec) {
    this.spec = spec || { nodes: [], edges: [] };
    this.particles = [];
    this.spawnAcc = {};
    this.resize();
  };

  FlowField.prototype._paused = function () {
    return document.body.classList.contains("anim-paused")
      || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  };

  FlowField.prototype._node = function (id) {
    var ns = this.spec.nodes;
    for (var i = 0; i < ns.length; i++) if (ns[i].id === id) return ns[i];
    return null;
  };

  FlowField.prototype.resize = function () {
    var c = this.canvas, rect = c.getBoundingClientRect();
    var w = Math.max(320, rect.width || c.clientWidth || 800);
    var h = Math.max(220, rect.height || c.clientHeight || 460);
    this._dpr = window.devicePixelRatio || 1;
    c.width = Math.round(w * this._dpr);
    c.height = Math.round(h * this._dpr);
    this.ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    this._W = w; this._H = h;
    var pad = 34, self = this;
    // bake normalized coords → px, and radius by tier
    this.spec.nodes.forEach(function (n) {
      n._x = pad + n.x * (w - 2 * pad);
      n._y = pad + n.y * (h - 2 * pad);
      n._r = n.r || 22;
    });
    // cache a perpendicular-bowed control point per edge so parallel edges separate
    this._cp = {};
    this.spec.edges.forEach(function (e) {
      var a = self._node(e.from), b = self._node(e.to);
      if (!a || !b) return;
      var mx = (a._x + b._x) / 2, my = (a._y + b._y) / 2;
      var dx = b._x - a._x, dy = b._y - a._y, len = Math.sqrt(dx * dx + dy * dy) || 1;
      var bow = (e.bow != null ? e.bow : 0) * len;   // 0 = straight
      self._cp[e.from + ">" + e.to] = { x: mx - (dy / len) * bow, y: my + (dx / len) * bow };
    });
    if (this._paused()) this._drawStatic();
  };

  function bez(a, cp, b, t) {
    var mt = 1 - t;
    return {
      x: mt * mt * a._x + 2 * mt * t * cp.x + t * t * b._x,
      y: mt * mt * a._y + 2 * mt * t * cp.y + t * t * b._y,
    };
  }

  FlowField.prototype._spawn = function (e) {
    this.particles.push({
      e: e, t: 0,
      sp: 0.004 + Math.random() * 0.004 + (e.rate || 0.3) * 0.004,   // faster when hotter
      sz: 1.6 + Math.random() * 1.2,
      jx: (Math.random() - 0.5) * 9, jy: (Math.random() - 0.5) * 7,
    });
  };

  FlowField.prototype._edgePath = function (ctx, a, b, cp) {
    ctx.beginPath(); ctx.moveTo(a._x, a._y); ctx.quadraticCurveTo(cp.x, cp.y, b._x, b._y);
  };

  FlowField.prototype._drawEdges = function (dashed) {
    var ctx = this.ctx, self = this, pal = this.pal;
    this.spec.edges.forEach(function (e) {
      var a = self._node(e.from), b = self._node(e.to), cp = self._cp[e.from + ">" + e.to];
      if (!a || !b || !cp) return;
      self._edgePath(ctx, a, b, cp);
      ctx.strokeStyle = sevColor(pal, e.severity);
      ctx.globalAlpha = e.severity === "critical" ? 0.5 : 0.22;
      ctx.lineWidth = e.severity === "critical" ? 2.2 : 1.2;
      ctx.setLineDash(dashed ? [5, 6] : []);
      ctx.stroke();
      ctx.setLineDash([]); ctx.globalAlpha = 1;
    });
  };

  FlowField.prototype._drawNodes = function () {
    var ctx = this.ctx, self = this, pal = this.pal, t = this._animT, paused = this._paused();
    this.spec.nodes.forEach(function (n) {
      var col = sevColor(pal, n.severity);
      // heat halo — brighter for hotter nodes; gently pulses unless paused
      var base = n.severity === "critical" ? 0.16 : n.severity === "watch" ? 0.1 : 0.05;
      var pulse = paused ? base : base + Math.sin(t * 2.0 + n._x * 0.01) * 0.03;
      var g = ctx.createRadialGradient(n._x, n._y, n._r * 0.4, n._x, n._y, n._r * 2.6);
      g.addColorStop(0, hexA(col, Math.max(0, pulse)));
      g.addColorStop(1, hexA(col, 0));
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(n._x, n._y, n._r * 2.6, 0, 6.2832); ctx.fill();
      // node disc
      var hovered = self._hover === n.id;
      ctx.beginPath(); ctx.arc(n._x, n._y, n._r, 0, 6.2832);
      ctx.fillStyle = pal.node;
      ctx.fill();
      ctx.lineWidth = hovered ? 2.4 : 1.4;
      ctx.strokeStyle = n.severity === "critical" ? pal.critical : (n.severity === "watch" ? pal.watch : pal.nodeStroke);
      ctx.stroke();
      // backlog pile — messages jammed at a bottleneck, heaped on the inbound side.
      // Size ∝ n.backlog (0..1); shimmers when running, sits still when paused.
      if (n.backlog) {
        var cnt = Math.round(n.backlog * 22), bx0 = n._x - n._r - 5;
        for (var q = 0; q < cnt; q++) {
          var col = Math.floor(q / 5), row = q % 5;
          var sh = paused ? 0 : Math.sin(t * 3 + q) * 0.8;
          var qx = bx0 - col * 5.2, qy = n._y - 10 + row * 5 + sh;
          ctx.beginPath(); ctx.arc(qx, qy, 1.9, 0, 6.2832);
          ctx.fillStyle = hexA(pal.critical, 0.5 + (paused ? 0.2 : Math.sin(t * 2 + q) * 0.18 + 0.15));
          ctx.fill();
        }
      }
      // labels
      ctx.textAlign = "center";
      ctx.fillStyle = pal.label;
      ctx.font = "600 12px ui-monospace, 'SF Mono', Menlo, monospace";
      ctx.fillText(clip(n.label || n.id, 18), n._x, n._y + n._r + 15);
      if (n.sub) {
        ctx.fillStyle = pal.sub;
        ctx.font = "10px ui-sans-serif, system-ui, sans-serif";
        ctx.fillText(clip(n.sub, 24), n._x, n._y + n._r + 28);
      }
    });
  };

  FlowField.prototype._drawEdgeLabels = function () {
    var ctx = this.ctx, self = this, pal = this.pal;
    this.spec.edges.forEach(function (e) {
      if (!e.label) return;
      var a = self._node(e.from), b = self._node(e.to), cp = self._cp[e.from + ">" + e.to];
      if (!a || !b || !cp) return;
      var p = bez(a, cp, b, 0.5);
      ctx.font = "600 11px ui-monospace, 'SF Mono', Menlo, monospace";
      ctx.textAlign = "center";
      var tw = ctx.measureText(e.label).width, bx = p.x - tw / 2 - 8, by = p.y - 26, bw = tw + 16, bh = 18;
      ctx.fillStyle = "rgba(20,17,13,0.86)";
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 9); else ctx.rect(bx, by, bw, bh);
      ctx.fill();
      ctx.fillStyle = sevColor(pal, e.severity);
      ctx.fillText(e.label, p.x, by + 13);
    });
  };

  function bezTan(a, cp, b, t) {   // unit tangent of the quadratic bezier at t
    var dx = 2 * (1 - t) * (cp.x - a._x) + 2 * t * (b._x - cp.x);
    var dy = 2 * (1 - t) * (cp.y - a._y) + 2 * t * (b._y - cp.y);
    var len = Math.hypot(dx, dy) || 1; return { x: dx / len, y: dy / len };
  }
  // ECG telemetry — a real metric time-series rides the edge as a waveform, offset
  // perpendicular to the flow. The window scrolls with animT for a live-monitor feel
  // (holds still when paused). This is the edge's HEALTH, distinct from the particles
  // (its traffic). e.ecg = number[], e.ecgMax = scale.
  FlowField.prototype._drawECG = function (scroll) {
    var ctx = this.ctx, self = this, pal = this.pal;
    this.spec.edges.forEach(function (e) {
      if (!e.ecg || e.ecg.length < 2) return;
      var a = self._node(e.from), b = self._node(e.to), cp = self._cp[e.from + ">" + e.to];
      if (!a || !b || !cp) return;
      var full = e.ecg, mx = e.ecgMax || Math.max.apply(null, full) || 1;
      var win = Math.min(full.length, 34), amp = 22;
      var start = scroll ? (Math.floor(self._animT * 14) % full.length) : Math.max(0, full.length - win);
      ctx.beginPath();
      for (var k = 0; k < win; k++) {
        var idx = (start + k) % full.length, t = k / (win - 1);
        var pt = bez(a, cp, b, t), tn = bezTan(a, cp, b, t);
        var v = (full[idx] || 0) / mx;
        var wx = pt.x + (-tn.y) * v * amp, wy = pt.y + (tn.x) * v * amp;
        k ? ctx.lineTo(wx, wy) : ctx.moveTo(wx, wy);
      }
      ctx.strokeStyle = sevColor(pal, e.severity);
      ctx.lineWidth = 1.5; ctx.globalAlpha = 0.92; ctx.stroke(); ctx.globalAlpha = 1;
    });
  };

  FlowField.prototype._drawStatic = function () {
    // paused / reduced-motion: dashed edges + evenly spaced dots sized by rate,
    // nodes lit to severity. The final, readable state — nothing moving.
    var ctx = this.ctx, self = this, pal = this.pal;
    ctx.clearRect(0, 0, this._W, this._H);
    this._drawEdges(true);
    this._drawECG(false);
    this.spec.edges.forEach(function (e) {
      var a = self._node(e.from), b = self._node(e.to), cp = self._cp[e.from + ">" + e.to];
      if (!a || !b || !cp) return;
      var n = Math.max(2, Math.round((e.rate || 0.3) * 7));
      for (var i = 1; i < n; i++) {
        var p = bez(a, cp, b, i / n);
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.8, 0, 6.2832);
        ctx.fillStyle = sevColor(pal, e.severity); ctx.globalAlpha = 0.55; ctx.fill(); ctx.globalAlpha = 1;
      }
    });
    this._drawNodes();
    this._drawEdgeLabels();
  };

  FlowField.prototype._draw = function () {
    var self = this;
    if (this._paused()) { this._drawStatic(); this._raf = null; return; }  // stop the loop when paused
    this._animT += 0.016;
    var ctx = this.ctx, pal = this.pal;
    ctx.clearRect(0, 0, this._W, this._H);
    this._drawEdges(false);
    this._drawECG(true);
    // spawn by rate
    this.spec.edges.forEach(function (e) {
      var key = e.from + ">" + e.to;
      self.spawnAcc[key] = (self.spawnAcc[key] || 0) + (e.rate || 0.3) * 0.9;
      if (self.spawnAcc[key] >= 1) { self.spawnAcc[key] -= 1; if (self.particles.length < 900) self._spawn(e); }
    });
    // move + draw particles
    var live = [];
    for (var i = 0; i < this.particles.length; i++) {
      var p = this.particles[i]; p.t += p.sp;
      if (p.t >= 1) continue;
      var a = this._node(p.e.from), b = this._node(p.e.to), cp = this._cp[p.e.from + ">" + p.e.to];
      if (!a || !b || !cp) continue;
      var pos = bez(a, cp, b, p.t);
      var al = Math.sin(p.t * Math.PI) * 0.85;
      var col = sevColor(pal, p.e.severity);
      ctx.globalAlpha = al * 0.18;                       // glow
      ctx.beginPath(); ctx.arc(pos.x + p.jx * (1 - p.t), pos.y + p.jy * (1 - p.t), p.sz * 2.4, 0, 6.2832);
      ctx.fillStyle = col; ctx.fill();
      ctx.globalAlpha = al;                              // core
      ctx.beginPath(); ctx.arc(pos.x + p.jx * (1 - p.t), pos.y + p.jy * (1 - p.t), p.sz, 0, 6.2832);
      ctx.fillStyle = col; ctx.fill();
      ctx.globalAlpha = 1;
      live.push(p);
    }
    this.particles = live;
    this._drawNodes();
    this._drawEdgeLabels();
    this._raf = requestAnimationFrame(function () { self._draw(); });
  };

  FlowField.prototype.start = function () {
    if (this._raf) return;
    if (this._paused()) { this._drawStatic(); return; }
    var self = this; this._raf = requestAnimationFrame(function () { self._draw(); });
  };
  FlowField.prototype.stop = function () {
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
  };
  FlowField.prototype.setPaused = function () {   // call after the ⏸ toggle flips
    if (this._paused()) { this.stop(); this._drawStatic(); } else this.start();
  };

  FlowField.prototype._onMove = function (ev) {
    var rect = this.canvas.getBoundingClientRect();
    var mx = ev.clientX - rect.left, my = ev.clientY - rect.top, hit = null, self = this;
    this.spec.nodes.forEach(function (n) {
      if (Math.hypot(mx - n._x, my - n._y) < n._r * 1.5) hit = n;
    });
    if ((hit && hit.id) !== this._hover) {
      this._hover = hit ? hit.id : null;
      if (this._paused()) this._drawStatic();
      if (this.onHover) this.onHover(hit, ev);
    }
  };
  FlowField.prototype._onLeave = function () {
    this._hover = null; if (this.onHover) this.onHover(null);
    if (this._paused()) this._drawStatic();
  };

  function clip(s, n) { s = "" + s; return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  function hexA(hex, a) {
    if (hex.charAt(0) !== "#") return hex;   // already rgba
    var n = parseInt(hex.slice(1), 16), r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    return "rgba(" + r + "," + g + "," + b + "," + a.toFixed(3) + ")";
  }

  window.FlowField = FlowField;
})();
