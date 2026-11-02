/* "My Submissions": lists only the logged-in student's own feedback. */
document.addEventListener("DOMContentLoaded", async () => {
  const student = await UI.initStudentNav();
  if (!student) {
    window.location.replace("student-login.html?next=history.html");
    return;
  }
  document.getElementById("whoami").textContent =
    `${student.full_name} · ${student.student_id} · ${student.department}`;

  const list = document.getElementById("historyList");
  let data;
  try {
    data = await API.get("/api/student/feedback");
  } catch (err) {
    list.innerHTML = `<div class="card-soft empty-state"><i class="bi bi-exclamation-triangle"></i>${UI.esc(err.message)}</div>`;
    return;
  }

  const items = data.items;
  const avg = items.length ? (items.reduce((s, f) => s + f.rating, 0) / items.length).toFixed(1) : "—";
  document.getElementById("summary").innerHTML = `
    <div class="col-6 col-md-4"><div class="card-soft p-3 d-flex gap-3 align-items-center"><div class="icon-tile"><i class="bi bi-chat-square-text"></i></div>
      <div><div class="small text-ink-3">Submissions</div><div class="fs-4 fw-bold">${items.length}</div></div></div></div>
    <div class="col-6 col-md-4"><div class="card-soft p-3 d-flex gap-3 align-items-center"><div class="icon-tile"><i class="bi bi-star"></i></div>
      <div><div class="small text-ink-3">Your average rating</div><div class="fs-4 fw-bold">${avg}</div></div></div></div>`;

  if (!items.length) {
    list.innerHTML = `<div class="card-soft empty-state"><i class="bi bi-inbox"></i>
      <p class="mb-3">You haven't submitted any feedback while logged in yet.</p>
      <a class="btn btn-primary" href="feedback.html">Submit your first feedback</a></div>`;
    return;
  }

  list.innerHTML = items.map((f) => `
    <article class="card-soft card-lift p-4">
      <div class="d-flex flex-wrap justify-content-between gap-2 mb-2">
        <div class="d-flex align-items-center gap-2">
          <div class="icon-tile" style="width:40px;height:40px;font-size:1.1rem"><i class="bi ${UI.categoryIcon(f.category)}"></i></div>
          <div><div class="fw-semibold">${UI.esc(f.category)}</div>
            <div class="small text-ink-3">#${f.id} · ${UI.formatDate(f.created_at)} · ${UI.semesterLabel(f.semester)}</div></div>
        </div>
        <div>${UI.stars(f.rating)}</div>
      </div>
      <p class="mb-2" style="white-space:pre-line">${UI.esc(f.description)}</p>
      ${f.suggestions ? `<div class="small bg-brand-50 rounded-3 p-3"><strong>Suggestion:</strong> <span style="white-space:pre-line">${UI.esc(f.suggestions)}</span></div>` : ""}
    </article>`).join("");
});
