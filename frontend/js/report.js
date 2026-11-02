/* Printable report: loads the filtered feedback through the admin API and lays it out for A4. */
document.addEventListener("DOMContentLoaded", async () => {
  const CATEGORIES = ["Faculty and Teaching", "Infrastructure", "Library", "Canteen",
                      "Events and Workshops", "Overall College Experience"];
  const MAX_RECORDS = 1000;
  const params = Object.fromEntries(new URLSearchParams(location.search).entries());
  const filters = {};
  ["category", "rating", "date_from", "date_to"].forEach((k) => { if (params[k]) filters[k] = params[k]; });
  const status = document.getElementById("reportStatus");

  let me = null;
  try {
    me = (await API.get("/api/session")).admin;
  } catch (err) {
    status.innerHTML = `<i class="bi bi-exclamation-triangle"></i>${UI.esc(err.message)}`;
    return;
  }
  if (!me) {
    window.location.replace("login.html");
    return;
  }

  try {
    // Fetch every matching record, 100 per request (the API's maximum page size).
    const items = [];
    let page = 1;
    let total = 0;
    while (items.length < MAX_RECORDS) {
      const data = await API.get("/api/feedback" + API.query({ ...filters, page, per_page: 100, sort: "created_at", order: "desc" }));
      items.push(...data.items);
      total = data.pagination.total;
      if (!data.pagination.has_next) break;
      page += 1;
    }
    render(items, total);
  } catch (err) {
    status.innerHTML = `<i class="bi bi-exclamation-triangle"></i>${UI.esc(err.message)}`;
  }

  function render(items, total) {
    document.getElementById("generatedAt").textContent = UI.formatDate(new Date().toISOString());
    document.getElementById("generatedBy").textContent = me.username;

    const parts = [];
    if (filters.category) parts.push(`Category: ${filters.category}`);
    if (filters.rating) parts.push(`Rating: ${filters.rating} stars`);
    if (filters.date_from) parts.push(`From: ${filters.date_from}`);
    if (filters.date_to) parts.push(`To: ${filters.date_to}`);
    document.getElementById("filterSummary").textContent = parts.length ? parts.join(" · ") : "None — all feedback included.";

    const n = items.length;
    const avg = n ? items.reduce((s, f) => s + f.rating, 0) / n : null;
    const positive = items.filter((f) => f.rating >= 4).length;
    document.getElementById("mTotal").textContent = total.toLocaleString();
    document.getElementById("mAvg").textContent = avg === null ? "—" : `${avg.toFixed(2)} / 5`;
    document.getElementById("mPositive").textContent = n ? `${Math.round((positive / n) * 100)}%` : "—";

    document.getElementById("catSummary").innerHTML = CATEGORIES.map((c) => {
      const rows = items.filter((f) => f.category === c);
      const a = rows.length ? (rows.reduce((s, f) => s + f.rating, 0) / rows.length).toFixed(2) : "—";
      return `<tr><td>${UI.esc(c)}</td><td class="text-end">${rows.length}</td><td class="text-end">${a}</td></tr>`;
    }).join("");

    const dist = [1, 2, 3, 4, 5].map((r) => items.filter((f) => f.rating === r).length);
    Charts.bar("reportRatingChart", ["1 ★", "2 ★", "3 ★", "4 ★", "5 ★"], dist, { animation: false });

    document.getElementById("recordNote").textContent =
      total > n ? `(first ${n} of ${total} — export CSV for the full list)` : `(${n})`;
    document.getElementById("recordRows").innerHTML = n ? items.map((f) => `
      <tr>
        <td>${f.id}</td>
        <td class="text-nowrap">${UI.formatDate(f.created_at, false)}</td>
        <td><strong>${UI.esc(f.student_name)}</strong><br><span class="text-ink-3">${UI.esc(f.student_id)} · ${UI.esc(f.department)} · Sem ${f.semester}</span></td>
        <td>${UI.esc(f.category)}</td>
        <td class="text-nowrap">${f.rating} / 5</td>
        <td>${UI.esc(f.description)}${f.suggestions ? `<br><em class="text-ink-3">Suggestion: ${UI.esc(f.suggestions)}</em>` : ""}</td>
      </tr>`).join("") : `<tr><td colspan="6" class="text-center text-ink-3 py-3">No feedback matches these filters.</td></tr>`;

    status.classList.add("d-none");
    document.getElementById("reportBody").classList.remove("d-none");
    const printBtn = document.getElementById("printBtn");
    printBtn.disabled = false;
    printBtn.addEventListener("click", () => window.print());
  }
});
