/*
 * Admin dashboard.
 * Every piece of data on this page comes from the protected Flask API,
 * which reads it from Supabase PostgreSQL. If the session is missing or
 * expired, the API answers 401 and we send the admin back to login.html.
 */
document.addEventListener("DOMContentLoaded", async () => {
  const SECTIONS = {
    overview:  ["Overview", "Snapshot of all feedback collected"],
    feedback:  ["Feedback Management", "Search, filter and review individual responses"],
    analytics: ["Analytics", "Charts generated live from the cloud database"],
    reports:   ["Reports", "Export data or generate a printable report"],
  };
  const state = { page: 1, per_page: 10, sort: "created_at", order: "desc", search: "", category: "", rating: "" };
  const loaded = { overview: false, feedback: false, analytics: false };

  /** Wrapper that redirects to login when the session has expired. */
  async function guarded(promise) {
    try {
      return await promise;
    } catch (err) {
      if (err.status === 401) window.location.replace("login.html?expired=1");
      throw err;
    }
  }

  // ---------------------------------------------------------------- auth gate
  let me = null;
  try {
    me = (await API.get("/api/session")).admin;
  } catch (err) {
    document.body.classList.remove("auth-pending");
    document.querySelector(".content").innerHTML =
      `<div class="card-soft empty-state"><i class="bi bi-cloud-slash"></i>${UI.esc(err.message)}</div>`;
    return;
  }
  if (!me) {
    window.location.replace("login.html");
    return;
  }
  document.body.classList.remove("auth-pending");
  document.getElementById("adminName").textContent = me.username;
  document.getElementById("adminAvatar").textContent = me.username.charAt(0).toUpperCase();

  // ---------------------------------------------------------------- database status badge
  (async () => {
    const badge = document.getElementById("dbBadge");
    try {
      const h = await API.get("/api/health");
      badge.innerHTML = `<i class="bi bi-circle-fill text-success" style="font-size:.5rem"></i>Cloud DB connected`;
      badge.title = h.database_engine;
    } catch (_) {
      badge.innerHTML = `<i class="bi bi-circle-fill text-danger" style="font-size:.5rem"></i>Database unreachable`;
    }
  })();

  // ---------------------------------------------------------------- navigation
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  function closeMenu() { sidebar.classList.remove("open"); backdrop.classList.remove("show"); }
  document.getElementById("menuBtn").addEventListener("click", () => { sidebar.classList.add("open"); backdrop.classList.add("show"); });
  backdrop.addEventListener("click", closeMenu);

  function show(section) {
    if (!SECTIONS[section]) section = "overview";
    document.querySelectorAll(".section-pane").forEach((p) => p.classList.toggle("active", p.id === `sec-${section}`));
    document.querySelectorAll(".side-link[data-section]").forEach((b) => {
      const on = b.dataset.section === section;
      b.classList.toggle("active", on);
      if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    });
    document.getElementById("sectionTitle").textContent = SECTIONS[section][0];
    document.getElementById("sectionSub").textContent = SECTIONS[section][1];
    if (location.hash !== `#${section}`) history.replaceState(null, "", `#${section}`);
    closeMenu();
    if (section === "overview" && !loaded.overview) loadOverview();
    if (section === "feedback" && !loaded.feedback) loadFeedback();
    if (section === "analytics" && !loaded.analytics) loadAnalytics();
  }
  document.querySelectorAll("[data-section]").forEach((b) => b.addEventListener("click", () => show(b.dataset.section)));
  document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => show(b.dataset.goto)));
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));

  document.getElementById("refreshBtn").addEventListener("click", () => {
    loaded.overview = loaded.feedback = loaded.analytics = false;
    show(location.hash.slice(1) || "overview");
    UI.toast("Data refreshed from the cloud database.", "info");
  });

  document.getElementById("logoutBtn").addEventListener("click", async () => {
    try { await API.post("/api/admin/logout"); } catch (_) { /* ignore */ }
    window.location.replace("login.html?loggedout=1");
  });

  // ---------------------------------------------------------------- overview
  async function loadOverview() {
    loaded.overview = true;
    try {
      const [dash, analytics] = await Promise.all([
        guarded(API.get("/api/admin/dashboard")),
        guarded(API.get("/api/feedback/analytics?days=30")),
      ]);
      const s = dash.stats;
      document.getElementById("statTotal").textContent = s.total_feedback.toLocaleString();
      document.getElementById("statTotalSub").textContent = `${s.submissions_last_24_hours} in the last 24 hours`;
      document.getElementById("statAvg").textContent = s.average_rating !== null ? `${s.average_rating.toFixed(2)} / 5` : "—";
      document.getElementById("statAvgStars").innerHTML = s.average_rating !== null ? UI.stars(Math.round(s.average_rating)) : "No ratings yet";
      document.getElementById("statCats").textContent = s.total_categories;
      document.getElementById("statCatsSub").textContent = `${s.categories_with_feedback} have received feedback`;
      document.getElementById("statRecent").textContent = s.submissions_last_7_days.toLocaleString();

      const recent = document.getElementById("recentList");
      recent.innerHTML = s.recent_submissions.length ? s.recent_submissions.map((f) => `
        <div class="recent-item" role="button" tabindex="0" data-id="${f.id}">
          <div class="icon-tile" style="width:40px;height:40px;font-size:1.05rem"><i class="bi ${UI.categoryIcon(f.category)}"></i></div>
          <div class="flex-grow-1 min-w-0">
            <div class="d-flex justify-content-between gap-2"><span class="fw-semibold text-truncate">${UI.esc(f.student_name)}</span>${UI.stars(f.rating)}</div>
            <div class="small text-ink-3 text-truncate">${UI.esc(f.category)} · ${UI.formatDate(f.created_at)}</div>
          </div>
        </div>`).join("")
        : `<div class="empty-state py-4"><i class="bi bi-inbox"></i>No feedback yet. Submissions will appear here.</div>`;
      recent.querySelectorAll("[data-id]").forEach(bindDetail);

      const t = analytics.submission_trend;
      Charts.line("overviewTrendChart", t.map((d) => Charts.dayLabel(d.date)), t.map((d) => d.count));
    } catch (err) {
      loaded.overview = false;
      if (err.status !== 401) UI.toast(err.message, "danger");
    }
  }

  // ---------------------------------------------------------------- feedback table
  const rows = document.getElementById("feedbackRows");

  async function loadFeedback() {
    loaded.feedback = true;
    rows.innerHTML = `<tr><td colspan="8" class="empty-state"><div class="spinner-border text-primary"></div></td></tr>`;
    try {
      const data = await guarded(API.get("/api/feedback" + API.query(state)));
      renderRows(data.items);
      renderPagination(data.pagination);
    } catch (err) {
      loaded.feedback = false;
      rows.innerHTML = `<tr><td colspan="8" class="empty-state"><i class="bi bi-exclamation-triangle"></i>${UI.esc(err.message)}</td></tr>`;
    }
  }

  function renderRows(items) {
    if (!items.length) {
      const filtered = state.search || state.category || state.rating;
      rows.innerHTML = `<tr><td colspan="8" class="empty-state"><i class="bi bi-inbox"></i>${filtered ? "No feedback matches these filters." : "No feedback has been submitted yet."}</td></tr>`;
      return;
    }
    rows.innerHTML = items.map((f) => `
      <tr data-id="${f.id}" tabindex="0">
        <td class="text-ink-3">${f.id}</td>
        <td class="text-nowrap small">${UI.formatDate(f.created_at)}</td>
        <td><div class="fw-semibold text-nowrap">${UI.esc(f.student_name)}</div><div class="small text-ink-3">${UI.esc(f.student_id)}</div></td>
        <td class="small"><div>${UI.esc(f.department)}</div><div class="text-ink-3">${UI.semesterLabel(f.semester)}</div></td>
        <td><span class="badge-cat small text-nowrap"><i class="bi ${UI.categoryIcon(f.category)} me-1"></i>${UI.esc(Charts.shortCategory(f.category))}</span></td>
        <td>${UI.stars(f.rating)}</td>
        <td><div class="truncate-2 small">${UI.esc(f.description)}</div></td>
        <td class="text-end"><button class="btn btn-sm btn-outline-primary" data-view="${f.id}" aria-label="View feedback ${f.id}"><i class="bi bi-eye"></i></button></td>
      </tr>`).join("");
    rows.querySelectorAll("tr[data-id]").forEach(bindDetail);
  }

  function renderPagination(p) {
    const from = p.total ? (p.page - 1) * p.per_page + 1 : 0;
    const to = Math.min(p.page * p.per_page, p.total);
    document.getElementById("pageInfo").textContent = `Showing ${from}–${to} of ${p.total} record${p.total === 1 ? "" : "s"}`;
    const ul = document.getElementById("pagination");
    const pages = [];
    const windowStart = Math.max(1, p.page - 2);
    const windowEnd = Math.min(p.pages, p.page + 2);
    const item = (label, page, disabled, active, aria) =>
      `<li class="page-item${disabled ? " disabled" : ""}${active ? " active" : ""}">
         <button class="page-link" data-page="${page}" ${disabled ? "disabled" : ""} ${aria ? `aria-label="${aria}"` : ""}>${label}</button></li>`;
    pages.push(item("&laquo;", p.page - 1, !p.has_prev, false, "Previous page"));
    if (windowStart > 1) pages.push(item("1", 1), windowStart > 2 ? item("…", 0, true) : "");
    for (let i = windowStart; i <= windowEnd; i++) pages.push(item(String(i), i, false, i === p.page));
    if (windowEnd < p.pages) pages.push(windowEnd < p.pages - 1 ? item("…", 0, true) : "", item(String(p.pages), p.pages));
    pages.push(item("&raquo;", p.page + 1, !p.has_next, false, "Next page"));
    ul.innerHTML = pages.join("");
    ul.querySelectorAll("[data-page]").forEach((b) => b.addEventListener("click", () => {
      const n = Number(b.dataset.page);
      if (n >= 1) { state.page = n; loadFeedback(); }
    }));
  }

  // filters: search is debounced so we don't hit the API on every keystroke
  let searchTimer;
  document.getElementById("fSearch").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = e.target.value.trim(); state.page = 1; loadFeedback(); }, 350);
  });
  document.getElementById("filterForm").addEventListener("submit", (e) => e.preventDefault());
  document.getElementById("fCategory").addEventListener("change", (e) => { state.category = e.target.value; state.page = 1; loadFeedback(); });
  document.getElementById("fRating").addEventListener("change", (e) => { state.rating = e.target.value; state.page = 1; loadFeedback(); });
  document.getElementById("fPerPage").addEventListener("change", (e) => { state.per_page = Number(e.target.value); state.page = 1; loadFeedback(); });
  const sortSelect = document.getElementById("fSort");
  sortSelect.addEventListener("change", (e) => {
    [state.sort, state.order] = e.target.value.split(":"); state.page = 1; loadFeedback();
  });
  document.querySelectorAll(".th-sort").forEach((b) => b.addEventListener("click", () => {
    const col = b.dataset.sort;
    state.order = state.sort === col && state.order === "desc" ? "asc" : "desc";
    state.sort = col; state.page = 1;
    const match = [...sortSelect.options].find((o) => o.value === `${state.sort}:${state.order}`);
    sortSelect.value = match ? match.value : sortSelect.value;
    loadFeedback();
  }));
  document.getElementById("clearFilters").addEventListener("click", () => {
    Object.assign(state, { page: 1, search: "", category: "", rating: "", sort: "created_at", order: "desc" });
    ["fSearch", "fCategory", "fRating"].forEach((id) => { document.getElementById(id).value = ""; });
    sortSelect.value = "created_at:desc";
    loadFeedback();
  });

  // ---------------------------------------------------------------- detail modal
  const modal = new bootstrap.Modal(document.getElementById("detailModal"));
  function bindDetail(el) {
    const open = () => openDetail(el.dataset.id);
    el.addEventListener("click", open);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
  }
  async function openDetail(id) {
    const body = document.getElementById("detailBody");
    body.innerHTML = `<div class="empty-state"><div class="spinner-border text-primary"></div></div>`;
    modal.show();
    try {
      const f = await guarded(API.get(`/api/feedback/${encodeURIComponent(id)}`));
      document.getElementById("detailTitle").textContent = `Feedback #${f.id}`;
      body.innerHTML = `
        <div class="d-flex flex-wrap align-items-center gap-2 mb-4">
          <span class="badge-cat"><i class="bi ${UI.categoryIcon(f.category)} me-1"></i>${UI.esc(f.category)}</span>
          <span class="fs-5">${UI.stars(f.rating)}</span><span class="fw-semibold">${f.rating}/5 · ${UI.RATING_WORDS[f.rating]}</span>
        </div>
        <div class="detail-grid mb-4">
          <div><div class="k">Student name</div><div class="v">${UI.esc(f.student_name)}</div></div>
          <div><div class="k">Student ID</div><div class="v">${UI.esc(f.student_id)}</div></div>
          <div><div class="k">Department</div><div class="v">${UI.esc(f.department)}</div></div>
          <div><div class="k">Year / Semester</div><div class="v">${UI.semesterLabel(f.semester)}</div></div>
          <div><div class="k">Submitted</div><div class="v">${UI.formatDate(f.created_at)}</div></div>
        </div>
        <h3 class="h6">Feedback description</h3>
        <div class="quote-box mb-3">${UI.esc(f.description)}</div>
        <h3 class="h6">Suggestions</h3>
        <div class="quote-box">${f.suggestions ? UI.esc(f.suggestions) : '<span class="text-ink-3">No suggestions provided.</span>'}</div>`;
    } catch (err) {
      body.innerHTML = `<div class="alert alert-danger mb-0">${UI.esc(err.message)}</div>`;
    }
  }

  // ---------------------------------------------------------------- analytics
  async function loadAnalytics() {
    loaded.analytics = true;
    const days = Number(document.getElementById("trendDays").value);
    try {
      const a = await guarded(API.get(`/api/feedback/analytics?days=${days}`));

      const cats = a.category_distribution;
      Charts.bar("categoryChart", cats.map((c) => Charts.shortCategory(c.category)), cats.map((c) => c.count),
        { horizontal: true, tooltip: (v) => `${v} submission${v === 1 ? "" : "s"}` });
      Charts.table("categoryTable", ["Category", "Submissions"], cats.map((c) => [c.category, c.count]));

      const ratings = a.rating_distribution;
      Charts.bar("ratingChart", ratings.map((r) => `${r.rating} ★`), ratings.map((r) => r.count),
        { tooltip: (v) => `${v} response${v === 1 ? "" : "s"}` });
      Charts.table("ratingTable", ["Rating", "Responses"], ratings.map((r) => [`${r.rating} star${r.rating > 1 ? "s" : ""}`, r.count]));

      const avg = a.average_rating_by_category;
      Charts.bar("avgChart", avg.map((c) => Charts.shortCategory(c.category)), avg.map((c) => c.average_rating),
        { horizontal: true, max: 5, stepSize: 1, tooltip: (v) => (v === null ? "No feedback yet" : `Average ${v.toFixed(2)} / 5`) });
      Charts.table("avgTable", ["Category", "Average rating"], avg.map((c) => [c.category, c.average_rating === null ? "—" : c.average_rating.toFixed(2)]));

      const t = a.submission_trend;
      Charts.line("trendChart", t.map((d) => Charts.dayLabel(d.date)), t.map((d) => d.count));
      Charts.table("trendTable", ["Date (UTC)", "Submissions", "Avg rating"],
        t.filter((d) => d.count > 0).map((d) => [d.date, d.count, d.average_rating === null ? "—" : d.average_rating.toFixed(2)]));
    } catch (err) {
      loaded.analytics = false;
      if (err.status !== 401) UI.toast(err.message, "danger");
    }
  }
  document.getElementById("trendDays").addEventListener("change", loadAnalytics);

  // ---------------------------------------------------------------- reports
  const reportForm = document.getElementById("reportForm");
  function reportParams() {
    const p = Object.fromEntries(new FormData(reportForm).entries());
    const err = document.getElementById("reportError");
    err.textContent = "";
    if (p.date_from && p.date_to && p.date_from > p.date_to) {
      err.textContent = "'From date' must be on or before 'To date'.";
      return null;
    }
    return p;
  }

  document.getElementById("exportCsvBtn").addEventListener("click", async (e) => {
    const params = reportParams();
    if (!params) return;
    const btn = e.currentTarget;
    UI.setLoading(btn, true, "Preparing…");
    try {
      // fetch (with the session cookie) → Blob → temporary link → download
      const res = await guarded(API.download("/api/feedback/export" + API.query(params)));
      const blob = await res.blob();
      const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: match ? match[1] : "feedback.csv" });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      UI.toast("CSV downloaded.", "success");
    } catch (err) {
      if (err.status !== 401) UI.toast(err.message, "danger");
    } finally {
      UI.setLoading(btn, false);
    }
  });

  document.getElementById("printReportBtn").addEventListener("click", () => {
    const params = reportParams();
    if (!params) return;
    window.open("report.html" + API.query(params), "_blank", "noopener");
  });

  // ---------------------------------------------------------------- start
  show(location.hash.slice(1) || "overview");
});
