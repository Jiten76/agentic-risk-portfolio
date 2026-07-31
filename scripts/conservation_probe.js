// Conservation probe — IA Stage B (reviews/ia_stage_a_role_spine.md v2.2 §6).
// Re-runnable by anyone: open archive/classic.html (r43 location), paste STEP 1;
// open index.html#canonical, paste STEP 2. Verdict must be PASS.
// Own-text rule: a target's fingerprint excludes nested [data-target] text,
// so additive NEW targets (e.g. challenge-strip) don't pollute their parent.
//
// STEP 1 (on archive/classic.html) — store the reference fingerprint:
//   [reducer as in STEP 2, then] localStorage.setItem('ia_classic_fp', JSON.stringify(out))
//
// STEP 2 (on index.html#canonical) — compare + role-subset check:
(async () => {
  const tick = () => new Promise(r => setTimeout(r, 80));
  const NUM = /\$?[\d][\d,\.]*%?|\b(?:red|amber|green|critical|illustrative|real_query_synthesized_data|contractual)\b|PAST DUE|ILLUSTRATIVE/g;
  const djb2 = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(16); };
  const own = el => { let t = el.textContent; el.querySelectorAll('[data-target]').forEach(c => { t = t.replace(c.textContent, ''); }); return t; };
  const takeFp = () => {
    const out = {};
    document.querySelectorAll('[data-target]').forEach(el => {
      const v = own(el); const counts = {};
      (v.match(NUM) || []).forEach(x => { x = x.trim(); counts[x] = (counts[x] || 0) + 1; });
      out[el.getAttribute('data-target')] = { h: djb2(v.replace(/\s+/g, ' ').trim()), c: counts };
    });
    const b = (document.querySelector('.disclosure') || {}).textContent || '';
    const bc = {}; (b.match(NUM) || []).forEach(x => { x = x.trim(); bc[x] = (bc[x] || 0) + 1; });
    out['__banner__'] = { h: djb2(b.replace(/\s+/g, ' ').trim()), c: bc };
    return out;
  };
  const classic = JSON.parse(localStorage.getItem('ia_classic_fp'));
  const fp = takeFp();
  const missing = [], numDiff = [], textChanged = [], newOnly = [];
  for (const k of Object.keys(classic)) {
    if (!(k in fp)) { missing.push(k); continue; }
    const a = classic[k].c, b = fp[k].c;
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    let d = false; for (const t of keys) if ((a[t] || 0) !== (b[t] || 0)) { d = true; break; }
    if (d) numDiff.push(k);
    if (classic[k].h !== fp[k].h) textChanged.push(k);
  }
  for (const k of Object.keys(fp)) if (!(k in classic)) newOnly.push(k);
  const canonTotal = {}; Object.values(fp).forEach(o => Object.entries(o.c).forEach(([t, n]) => canonTotal[t] = (canonTotal[t] || 0) + n));
  const roleViol = {};
  for (const role of ['basic', 'leadership', 'engineering', 'audit']) {
    location.hash = 'role=' + role; await tick();
    const rfp = takeFp(); const tot = {};
    Object.values(rfp).forEach(o => Object.entries(o.c).forEach(([t, n]) => tot[t] = (tot[t] || 0) + n));
    const mint = Object.keys(tot).filter(t => (tot[t] || 0) > (canonTotal[t] || 0));
    if (mint.length) roleViol[role] = mint.slice(0, 3);
  }
  const bannerOk = /demonstrator on synthetic telemetry/i.test((document.querySelector('.disclosure') || {}).textContent || '');
  const actsOk = ['Signal', 'Pattern', 'Impact', 'Decide', 'Attest'].every(n => document.body.textContent.includes(n));
  console.log(JSON.stringify({ missing, numDiff, roleViol, textChanged, newOnly, bannerOk, actsOk,
    verdict: (!missing.length && !numDiff.length && !Object.keys(roleViol).length && bannerOk && actsOk) ? 'PASS' : 'FAIL' }, null, 1));
})();
