# Stage A — the read, on paper: role-sequenced spine for all four pages

**Status: v2.2 — SIGNED OFF 2026-07-14.** User decisions: (1) default role is
a neutral `basic` dashboard view — role selection is explicit via the spine's
drop-down or nav clicks, never assumed; (2) remaining headlines written in
Stage B under the §8 genre gate; (3) act-tab strip removed per the §3.5
disposition. Stage B (rac as template) is a go.
Owner: Jiten · v1 2026-07-13 · v2 same day, after two blocking reviews.

## v2 amendment log (what each reviewer finding changed)

| finding | resolution |
|---|---|
| Claude #1 BLOCKER — arcs contradict act-as-screen | §2 inverted: the screen unit is the **arc step**; acts become panel metadata; apps keep their own act vocabularies (also closes GROK #3) |
| Claude #2 BLOCKER — disclosure banner unprotected | §5 row 0: banner is tier-H, all roles/pages, own gate line in C26 setup |
| Claude #3 MAJOR — C26 comparison state undefined | §6: canonical comparison state defined + role-subset second check |
| Claude #4 / GROK #1 MAJOR — competing navigations | §3.5 (new): ONE navigation system; spine replaces act tabs; full state machine |
| GROK #2 — ATTACK door = honesty regression | §5: the challenge strip is always-visible tier-H next to the number for ALL roles; only E-depth sits behind the door (rationale inline) |
| GROK #4 — numeric-only fingerprints | §6: protected status-token classes gated hard; full-text hash recorded as acknowledged changelist |
| GROK #5 — role-link ambiguity | §1: canonical link rule + visible "reading as" chip |
| GROK #6 — headline rot | §6: headlines are computed projection data, gated (must cite a number from their own panel) |
| GROK #7 / Claude mobile+keyboard | §3.5: **no DOM reordering**; mobile breadcrumb; keyboard/focus preserved by construction; offline hash routing |
| GROK #8 — landing chooser vs thesis | §4.4: landing stays the neutral index; role entry lives on the tool cards |
| GROK #9 — empty states | §6.5 rule + example |
| GROK #10 / Claude acceptance | §7: visual regression, a11y focus check, console-zero, perf note added |
| Claude — headline genre risk | §8: five exemplar one-liners from counted values lock the genre |
| Claude — "43 minutes" hv thesis | §4.3: **verified stale** (old prototype prose). Thesis rebuilt from counted values; thesis lines join the prose-vs-data gate |
| Claude — back-button | §3.5: hash history navigable, stated in C27 |

Principles (user-locked, unchanged): subtract & sequence by role · spine as
navigation · threads not walls · role links not sign-in · backward compatible,
conservation-checked, zero drift.

---

## 1 · The roles and what each is owed in 30 seconds

| role key | who | their question | the 30-second answer |
|---|---|---|---|
| `basic` (default) | anyone, first visit | "show me the dashboard" | the canonical argument in order — the number, where it comes from, what it forces, how to challenge it — no role assumptions, pick a lens when ready |
| `leadership` | CRO / exec | "one defensible number — what do we decide this week?" | $135.2M residual P95 (+ priced fat-tail range) · the 3-decision docket ($63.4M riding) · who's accountable |
| `engineering` | platform/SRE/security lead | "which of my systems bleeds, what do I gate this sprint?" | your domain's firing patterns ranked by residual $, the control that failed, the verb to run |
| `audit` | IA / examiner / 2LoD | "does any of this re-execute?" | every claim has a runner: seals, 69 gates, OSCAL, one-command verify — start attacking here |

**Role mechanics (GROK #5 resolved):**
- `location.hash` is the single source of truth: `#role=<key>&node=<spine-node>`.
- Bare links default to **`basic`** — the neutral dashboard view (user decision
  2026-07-14). A **"viewing as: basic — choose your lens"** drop-down renders
  prominently in the spine strip; roles are always an explicit choice (drop-down
  or spine/nav click), never an assumption about the reader.
- Every internal link and the spine's copy-link affordance emit **fully-qualified**
  hashes. Cross-page links (landing → apps) carry the role forward explicitly.
- A role view can differ from another ONLY in ordering/expansion — never in
  values (§6's subset check makes that a gate, which is the evidentiary-integrity
  answer: any role following any link sees the same numbers).

## 2 · Screens and beats — REVISED (Claude #1, GROK #3)

**The screen unit is the arc step**: a curated set of panels shown together,
one step at a time, spine-navigated. The 5 acts (SIGNAL/PROPAGATE/IMPACT/
DECIDE/ATTEST) stop being screens and become **metadata on panels** — kept as
familiar labels on panel headers and spine nodes, so nothing the reviewers
learned is renamed. atg and hv **keep their own act vocabularies**; the beat
model below is a *sequencing overlay*, not a renaming, and only the role
ordering is shared across apps.

| beat | what it answers | rac panels drawn from acts |
|---|---|---|
| STAKE | why care | mostly IMPACT |
| BELIEVE | where the number comes from | SIGNAL + PROPAGATE |
| ACT | what happens Monday | DECIDE |
| ATTACK | can I break it | ATTEST |

Beat order per role: `basic` STAKE→BELIEVE→ACT→ATTACK (the canonical pyramid) ·
`leadership` STAKE→ACT→BELIEVE→ATTACK · `engineering` BELIEVE→ACT→STAKE→ATTACK ·
`audit` ATTACK→BELIEVE→STAKE→ACT.

## 3 · The spine

One compact **spine strip** pinned under the header: the current role's arc as
clickable nodes, "you are here" highlighted, plus an expand control opening the
**full map overlay** (the object graph below, role path highlighted). Nodes and
edges derive from the projection — counts, dollars, slice names — so the map
cannot say something the page doesn't.

```
platform telemetry (illustrative, seeded 2026-Q3-baseline)
        │
   13 risk patterns ──(signals vs thresholds)──► 25-finding register
        │                                             │ by domain (rail)
   correlated MC · seed 42 · 20k trials               ▼
   ONE DISTRIBUTION ◄──────────────────── per-pattern residual P95
   $38.3M P50 · $135.2M P95 · $242.6M P99
        ├── slice BY PATTERN ──► intervention queue (what to gate)
        ├── slice BY REGULATION ──► regulation residual (applies? · filter)
        └── slice BY DECISION ──► Monday-morning docket (3 decisions · org reality)
        │
   CHALLENGE TRAIL (the ATTACK surfaces)
        ├── tornado (12 levers) + σ sweep      ├── judgment log
        ├── control test evidence (C24)        ├── internal-audit register
        └── seal · 69 gates · OSCAL · a2a ──► verify_bundle
```

### 3.5 · Navigation: ONE system (Claude #4, GROK #1, #7 — the state machine)

- **The spine replaces the act-tab strip — with its information re-homed, not
  dropped.** Disposition of everything the strip carries: act NAMES
  (SIGNAL…ATTEST) → spine-node captions + panel-header metadata badges; act
  DESCRIPTIONS ("what fired" … "prove it") → spine-node subtitles/tooltips
  (they are the beats in plain language); direct-jump affordance + tablist
  keyboard semantics → spine nodes. The ONLY thing removed from the new view is
  the fixed `01→05` numerals and the reading order they assert — deliberately,
  since no role reads in that order — and they survive in the frozen classic
  view. Gate: C26f asserts the five act names and five descriptions render in
  every role view (chrome isn't a data-target, so it gets a named gate like the
  banner). **Complete portfolio-wide removal list: (1) the act numerals/fixed
  order (new view only); (2) hv persona-chip labels, replaced 1:1 by the shared
  role keys. Nothing else is removed anywhere — everything re-homes.**
- **The role drop-down is part of the spine component** (top-left of the strip),
  not separate chrome: `viewing as: basic ▾` with the four options. hv's existing
  persona chips are replaced by it (one vocabulary). Total navigation systems after Stage B: **spine (with role
  chips) + rail**. The rail survives because it is *data scoping* (which
  domain), not narrative navigation — orthogonal by design.
- **State machine:** hash is the only state. Spine click → `node` updates →
  the step's panels render/expand, others collapse to headlines. Role click →
  `role` updates → spine redraws that role's path; **current node is kept if it
  exists on the new path, else jump to the path's first node**. Browser
  back/forward walk hash history (C27 asserts round-trip). Rail selection is
  independent state and survives role/node changes.
- **No DOM reordering — ever.** The DOM keeps one canonical order; roles change
  *which step you land on, what's expanded, and what the spine suggests next* —
  sequence is guided navigation, not restacking. This preserves the hard-won
  keyboard nav (j/k, verb keys), focus order, and screen-reader sanity by
  construction, and it kills the "what state after three clicks" ambiguity:
  panels have exactly two axes (expanded-tier × on-screen), both derivable from
  the hash + rail alone.
- **Mobile (≤640px):** the strip collapses to a one-line breadcrumb
  ("◂ STAKE · **you are here** · ACT ▸") with the full map behind a tap;
  role chips fold into the breadcrumb's overflow. No pinned chrome beyond one
  line.
- **Offline packs:** hash routing is pure client-side — works on `file://` and
  the COLD_READ server alike. No history API dependency beyond hashchange.

## 4 · Page theses and role arcs

Thesis lines are the highest-visibility claims on the site, so they join the
prose-vs-data gate: **every number a thesis cites must exist in that page's
projection** (B6-class check, §6). The "43 minutes" figure in v1's hv thesis
failed exactly this test — it was stale prototype prose; v2's is counted.

### 4.1 rac
**Thesis:** *13 failure patterns roll up to one challengeable number — $135.2M
residual P95 — and it puts three decisions on the table this week.*
- `leadership`: hero (number + range + challenge strip) → Monday-morning docket →
  regulation residual (binding-only ON by default for this role) → ATTACK depth
- `engineering`: rail: your domain → queue (firing patterns by $) → cascade
  (blast radius) → per-pattern translation (what a fix buys) → verbs → ATTACK depth
- `audit`: seal + gate board → tornado + judgment log → control evidence →
  internal-audit register → action log → OSCAL/a2a/verify_bundle pointers

### 4.2 atg
**Thesis:** *Agents doing governance work leave verifiable evidence trails — and
the trail is what catches the agent that exceeded its scope.*
Arcs as v1 (leadership: magnitude→verbs→attack · engineering: lineage→queue→
verbs→attack · audit: attest log→lineage evidence→verbs→magnitude). atg keeps
its act names (Claude #1 / GROK #3 resolution).

### 4.3 hv
**Thesis (rebuilt from counted values):** *The same incident, two regimes:
instrumented detection flags in 2 minutes what the manual playbook finds in
10–12 — and has audit-ready evidence ~90 minutes sooner.*
(Counted: detection 10→2 / 12→2 / 12→2 min; evidence-ready 100→12 / 90→10 /
85→10 min across the three scenarios.)
Arcs as v1; hv persona chips replaced by the shared role chips (§3.5).

### 4.4 landing — REVISED (GROK #8)
**The landing stays the neutral portfolio index.** Hierarchy unchanged: thesis +
substrate diagram first, shared-object strip second (it stays the star). The
role affordance moves DOWN into the three tool cards — each card carries three
compact entry links ("enter as leadership / engineering / audit" →
`rac.html#role=…`). No top-of-page chooser; the landing argues *one substrate*,
and role-forking its own hierarchy would fight that thesis.

## 5 · Panel disposition

Tiers: **H** always visible · **S** summary on-screen in its step · **E**
evidence thread (expand). Unchanged from v1 except the additions below —
the full 43-target rac table, atg, hv, and landing tables from v1 carry over
verbatim (they are the conservation checklist).

**Row 0 (new — Claude #2): the synthetic-demonstrator disclosure banner.**
Tier-**H**, every role, every page, above the fold, never inside a collapse.
It is what licenses the theses' organizational voice ("decisions this week")
on synthetic data. Gated by name in C26 setup: the banner text must render
above the fold in every role view of every page, asserted per-role in the QA
click pass.

**ATTACK disposition (revised — GROK #2):** the challenge machinery is the
number's credibility, so it cannot be hidden from any role. Resolution:
- A tier-**H challenge strip** renders immediately adjacent to the headline
  number for ALL roles: *"holds ±50% under any single judgment · joint bad year
  $278.1M · σ priced to +40.1% · 69 gates green — challenge this number ↓"* —
  every value computed, not typed.
- The strip IS the door: clicking it opens ATTACK depth (tornado, judgment log,
  evidence table, IA register). For `audit` the door renders open by default.
- What changed vs today is therefore *depth placement only* — the existence,
  headline conclusions, and live values of the challenge trail stay in pixels
  for everyone. (Honesty-in-pixels preserved; walls subtracted.)

## 6 · Conservation, accuracy, zero drift — REVISED (Claude #3, GROK #4, #6)

**Classic copies:** unchanged from v1 (frozen `classic.html` per app +
`PORTFOLIO_INDEX_classic.html`, footer-linked, `classic/` ships in
PORTFOLIO_REVIEW, not COLD_READ).

**Canonical comparison state (Claude #3).** The manifest is taken — and C26
compared — in ONE defined state: **all panels rendered, all tiers expanded, all
filters off, rail = all_portfolio, fingerprints read from DOM text regardless
of visibility** (this matches how classic's hidden ai-gov panels fingerprint
today). Role is irrelevant to the canonical state by construction (§3.5: roles
never change values).
- **C26a (exactness):** every classic target renders in the new build's
  canonical state; numeric multisets match exactly.
- **C26b (role subset):** every role's default view — all FOUR, `basic`
  included — renders a **subset** of the canonical multiset: a role view may
  hide numbers behind tiers/filters but may never mint one. Checked per role in
  the QA pass.
- **C26c (protected tokens — GROK #4):** beyond numerics, these token classes
  are gated hard in the fingerprint: RAG values (red/amber/green/critical),
  provenance statuses (`illustrative`, `real_query_synthesized_data`, …),
  lifecycle markers (PAST DUE, repeat, MRA/EX-), applicability flags
  (ILLUSTRATIVE / contractual / licence-conditional), and the banner text.
- **C26d (text changelist):** a full-text hash per target is recorded in the
  manifest; textual diffs don't fail the build but emit a **changelist that must
  be acknowledged in the commit message** — qualitative drift becomes visible
  without freezing the copy we're deliberately rewriting.
- **C26e (banner):** the disclosure banner renders above the fold in every
  role view of every page.

**Conclusion headlines are data, not template strings (GROK #6).** Each
headline lives in the projection, emitted by the same builder that computes the
values it cites — when a number moves, its headline moves in the same commit or
the gate fails. Gate: **every headline must contain ≥1 numeric token present in
its own panel's fingerprint** (falsifiable-against-the-panel, mechanically
checked). Genre locked by §8's exemplars. Ownership: operator-authored
templates in the builders, reviewed like any calibration text.

**Spine integrity (C27):** as v1 (every node resolves · every panel reachable ·
role-path union covers all nodes) **plus**: hash round-trips, browser
back/forward walk the visited-node history, and the three role paths are
click-verified with content diffs per role (round-7 discipline).

**Thesis/prose gate:** thesis lines and the challenge strip join the
B6-class check — any number they cite must appear in the page's projection.

**verify_bundle B9/B10 — invariant AMENDED (round-15, external catch).** The v1
clause promised classic↔new **seal-hash equality**; the shipped builds cannot
and should not satisfy it — classic freezes the pre-grammar projection while
index/read legitimately add the `ia` block, prose fixes, and fresh build
timestamps, so the seals differ by design. The ACTUAL invariant, now stated and
gated: **the multiset of numeric LEAVES in every view's embedded projection is
identical** (classic = index = read; ia headlines and timestamps are string
leaves, so presentation additions and build clocks can neither hide nor be
hidden by a moved number), **plus acknowledged text diffs per C26d**. Gates:
B9.1–3 (per-app conservation report PASS + input hashes match the shipped
classic/index/read) and B10.1–3 (per-app cross-view numeric-leaf equality,
re-derived in-bundle, stdlib-only). The guarantee is "same numbers, named text
changes" — not "same bytes" — and that is the honest formulation of zero-drift
for a presentation restructure. **Round-17 refinement:** additive ANALYTICS
(e.g. the perimeter profiles) legitimately add numeric leaves after the classic
freeze, so the gate splits: contemporary views (index / read / validation) must
be leaf-EQUAL to each other; the frozen classic must be a SUB-multiset of index
(nothing lost; the additive delta is counted and reported, never silent).

**Round-16 dispositions (external findings, recorded not silent):**
- **read.html disposition:** the executive linear read — one conclusion per
  chapter, same sealed projection (gated by `read_sha256` freshness + B10/B11
  numeric equality), the cold-read pack's landing surface. Hedges are priced
  into single falsifiable sentences rather than sprayed.
- **Role-tiered affordances (fixed):** leadership hides operator chrome —
  keyboard hints, per-row verb buttons, the domain rail — via
  `body[data-role="leadership"]` display rules ONLY. textContent (and thus the
  conservation fingerprints) is untouched: every number stays in the DOM;
  the cockpit no longer leads the CRO's walk. Other roles unchanged.
- **Spine statefulness (declined, deliberate):** the spine is an ordered
  SUGGESTION, not a gate. Position IS durable — it lives in the hash, which
  survives reload and copy-link. Enforcing progression (blocking jumps out of
  the declared order) would break deep links, the map, and the audit role's
  attack-first entry; "roles re-sequence, never gate" is the design. Recorded
  here so the trade is named, not silent.
- **Cross-build drift (fixed):** B10 is within-build; `qa/numeric_baseline.json`
  + verify_bundle **B11** pin the numeric-leaf multiset across releases —
  changing numbers requires re-cutting the baseline in the same commit.
- **Matrix evidence (fixed):** the assertion harness ships
  (`scripts/interaction_matrix_runner.js`, paste-per-page, prints per-check
  evidence) — coverage is re-executable, not claimed.

### 6.5 · Empty states (GROK #9)
Rule: **an empty slice states why, counts what it's hiding, and offers the
nearest action — never a blank panel.** Example: engineering selects `custody`
with nothing firing → *"No firing patterns in custody this period — 2 amber
signals sit below threshold (see register). Nearest risk: RP-08 via the
platform cascade edge."* Filters that empty a view show "0 of N — clear
filter". All empty-state copy is computed from the projection like any other
render.

## 7 · Stages and acceptance — extended

- **Stage A (this doc, v2)** — sign-off gate.
- **Stage B — rac as template:** spine strip + map overlay (replacing act tabs),
  role chips + hash router, tier rendering, challenge strip + ATTACK depth,
  banner row 0, headlines-as-data for rac's panels, classic freeze, manifest +
  C26a–e + C27 + B9. **Acceptance:** three role paths click-verified with
  content diffs; C1–C27 green; manifest exact; classic linked & untouched;
  zero console errors both views; **screenshot set per role×step** (visual
  regression baseline); **focus-order check** (tab sequence unchanged from
  classic — no DOM reordering makes this cheap); role-switch renders without
  layout thrash (it re-expands existing DOM; no rebuild).
- **Stage C — propagate** to atg, hv, landing (as §4.4); bundles regen
  (classic/ in review pack); **readability review round whose acceptance test
  is the person who wrote the July-13 critique** — "does the reader who said
  'no flow' now find flow" is the only pass condition that matters. External
  AI rounds are scoped to readability only.

## 8 · Exemplar conclusion headlines (genre lock — Claude's ask)

Each states a *finding*, cites a number that exists in its panel, and is
falsifiable against it. (Values below are today's computed values; in
implementation every one is emitted by the builder, never typed.)

1. **exposure-cards:** "Controls buy a 62% cut — $354.2M inherent shrinks to
   $135.2M residual at P95; the challenge strip prices how far to trust that credit."
2. **cascade-card:** "The dependency graph is ~39% of the tail — switch the 22
   cascade edges off and P95 falls to $82.6M."
3. **monday-morning:** "Three decisions carry $63.4M of residual P95 — none can
   be forced; the levers are challenge, decline-to-countersign, escalate."
4. **regulation-residual:** "95% of stress-P95 sits under an OCC *style-mapping*
   that may not bind this archetype — applicability is a flag and a filter here,
   not a footnote."
5. **sensitivity-panel / challenge strip:** "No single judgment moves the number
   more than ±50%; a joint bad year doubles it to $278.1M — every assumption is
   priced, logged, challengeable."

Anti-genre (fails review): "Exposure across percentiles" — a name, not a finding.

## Open items — RESOLVED (user, 2026-07-14)
1. Default role = **`basic`** neutral dashboard (user overruled the leadership
   rec — role is an explicit choice via drop-down or nav, never assumed).
2. APPROVED: Stage B writes the remaining ~25 headlines in the §8 genre, as
   projection data under the C26 headline gate.
3. APPROVED: act-tab strip removed per §3.5 disposition (names/descriptions/
   jump re-homed to spine; only the 01–05 numerals go; classic keeps them).
