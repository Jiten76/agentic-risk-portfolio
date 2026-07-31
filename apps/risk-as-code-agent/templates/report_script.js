// Dashboard interactivity layer. No framework dependency.
// - Tab switching via radio :checked + CSS (handled in CSS — JS only updates ARIA)
// - Filter chips toggle visibility of finding rows by data-* attributes
// - Search box filters rows by pattern id / name / signals / incident text
// - Row click expands inline detail

(function () {
  // ── Finding row expand/collapse ──────────────────────────────────────────
  function toggleRow(row) {
    const open = row.getAttribute("data-expanded") === "true";
    row.setAttribute("data-expanded", open ? "false" : "true");
  }
  document.querySelectorAll(".finding-row").forEach((row) => {
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    row.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      toggleRow(row);
    });
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleRow(row);
      }
    });
  });

  // v1.3.1: auto-expand handled server-side (top-1 red by financial exposure).
  // Do NOT override here — earlier JS expanded all reds, creating a wall of
  // text on landing (council item 6).

  // ── Filter chips + search ────────────────────────────────────────────────
  const state = {
    rag: new Set(["red", "amber"]),    // default: show red+amber (hide green if any)
    domain: new Set(),                 // empty = all
    query: "",
  };

  function rowMatches(row) {
    const rag = row.getAttribute("data-rag");
    const domain = row.getAttribute("data-domain");
    const text = row.getAttribute("data-search") || "";
    if (state.rag.size && !state.rag.has(rag)) return false;
    if (state.domain.size && !state.domain.has(domain)) return false;
    if (state.query && !text.toLowerCase().includes(state.query.toLowerCase())) return false;
    return true;
  }

  function applyFilters() {
    let visible = 0;
    document.querySelectorAll(".finding-row").forEach((row) => {
      const match = rowMatches(row);
      row.setAttribute("data-hidden", match ? "false" : "true");
      // The directly-following sibling is the expand detail row
      const detail = row.nextElementSibling;
      if (detail && detail.classList.contains("finding-detail")) {
        detail.style.display = (match && row.getAttribute("data-expanded") === "true") ? "" : "none";
      }
      if (match) visible++;
    });
    const empty = document.querySelector(".empty-row");
    if (empty) empty.setAttribute("data-hidden", visible > 0 ? "true" : "false");
    const summary = document.querySelector("[data-filter-summary]");
    if (summary) summary.textContent = `${visible} of ${document.querySelectorAll(".finding-row").length} findings`;
  }

  // Wire RAG chips
  document.querySelectorAll(".filter-chip[data-filter='rag']").forEach((chip) => {
    chip.addEventListener("click", () => {
      const rag = chip.getAttribute("data-value");
      if (rag === "all") {
        state.rag = new Set();
        document.querySelectorAll(".filter-chip[data-filter='rag']").forEach((c) => {
          c.setAttribute("data-active", c.getAttribute("data-value") === "all" ? "true" : "false");
        });
      } else {
        if (state.rag.has(rag)) state.rag.delete(rag);
        else state.rag.add(rag);
        // If user toggles any specific rag, turn off "all"
        document.querySelectorAll(".filter-chip[data-filter='rag']").forEach((c) => {
          const v = c.getAttribute("data-value");
          if (v === "all") c.setAttribute("data-active", state.rag.size === 0 ? "true" : "false");
          else c.setAttribute("data-active", state.rag.has(v) ? "true" : "false");
        });
      }
      applyFilters();
    });
  });

  // Wire Domain chips
  document.querySelectorAll(".filter-chip[data-filter='domain']").forEach((chip) => {
    chip.addEventListener("click", () => {
      const d = chip.getAttribute("data-value");
      if (d === "all") {
        state.domain = new Set();
        document.querySelectorAll(".filter-chip[data-filter='domain']").forEach((c) => {
          c.setAttribute("data-active", c.getAttribute("data-value") === "all" ? "true" : "false");
        });
      } else {
        if (state.domain.has(d)) state.domain.delete(d);
        else state.domain.add(d);
        document.querySelectorAll(".filter-chip[data-filter='domain']").forEach((c) => {
          const v = c.getAttribute("data-value");
          if (v === "all") c.setAttribute("data-active", state.domain.size === 0 ? "true" : "false");
          else c.setAttribute("data-active", state.domain.has(v) ? "true" : "false");
        });
      }
      applyFilters();
    });
  });

  // Search
  const searchInput = document.querySelector(".filter-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      state.query = e.target.value;
      applyFilters();
    });
  }

  // Initial filter pass (applies the default rag={red,amber} state)
  applyFilters();
})();
