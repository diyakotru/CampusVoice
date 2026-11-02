/* Helpers shared by all pages. */
const UI = (() => {
  const CATEGORY_ICONS = {
    "Faculty and Teaching": "bi-person-video3",
    "Infrastructure": "bi-building",
    "Library": "bi-book",
    "Canteen": "bi-cup-hot",
    "Events and Workshops": "bi-calendar-event",
    "Overall College Experience": "bi-mortarboard",
  };
  const RATING_WORDS = ["", "Poor", "Fair", "Good", "Very good", "Excellent"];

  /** Escape text before putting it into HTML — prevents XSS from stored feedback. */
  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function formatDate(iso, withTime = true) {
    if (!iso) return "—";
    const d = new Date(iso);
    const opts = withTime
      ? { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
      : { day: "2-digit", month: "short", year: "numeric" };
    return d.toLocaleString(undefined, opts);
  }

  function stars(rating) {
    const r = Number(rating) || 0;
    let html = `<span class="stars-static" aria-label="${r} out of 5 stars" title="${r} / 5">`;
    for (let i = 1; i <= 5; i++) html += `<i class="bi bi-star-fill${i <= r ? "" : " off"}"></i>`;
    return html + "</span>";
  }

  function semesterLabel(sem) {
    const s = Number(sem);
    return s ? `Year ${Math.ceil(s / 2)} · Sem ${s}` : "—";
  }

  function categoryIcon(category) {
    return CATEGORY_ICONS[category] || "bi-chat-square-text";
  }

  /** Bootstrap toast in the corner. type: success | danger | warning | info */
  function toast(message, type = "success") {
    let container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      container.className = "toast-container position-fixed top-0 end-0 p-3";
      document.body.appendChild(container);
    }
    const icons = { success: "bi-check-circle-fill", danger: "bi-x-circle-fill",
                    warning: "bi-exclamation-triangle-fill", info: "bi-info-circle-fill" };
    const el = document.createElement("div");
    el.className = `toast align-items-center text-bg-${type}`;
    el.setAttribute("role", type === "danger" ? "alert" : "status");
    el.setAttribute("aria-live", "assertive");
    el.innerHTML = `<div class="d-flex"><div class="toast-body d-flex gap-2 align-items-start">
        <i class="bi ${icons[type] || icons.info}"></i><span>${esc(message)}</span></div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>`;
    container.appendChild(el);
    const t = new bootstrap.Toast(el, { delay: 5000 });
    el.addEventListener("hidden.bs.toast", () => el.remove());
    t.show();
  }

  function setLoading(button, loading, text) {
    if (loading) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>${esc(text || "Please wait…")}`;
    } else {
      button.disabled = false;
      if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
    }
  }

  /** Show server-side field errors under the matching inputs. */
  function showFieldErrors(form, fields) {
    Object.entries(fields || {}).forEach(([name, message]) => {
      const input = form.querySelector(`[name="${name}"]`);
      const box = form.querySelector(`[data-error-for="${name}"]`);
      if (input) input.classList.add("is-invalid");
      if (box) { box.textContent = message; box.classList.add("d-block"); }
    });
  }

  function clearFieldErrors(form) {
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
    form.querySelectorAll("[data-error-for]").forEach((el) => { el.textContent = ""; el.classList.remove("d-block"); });
  }

  /** Public navbar: show "My Submissions / Logout" when a student is logged in. */
  async function initStudentNav() {
    const loggedOut = document.querySelectorAll("[data-show='student-logged-out']");
    const loggedIn = document.querySelectorAll("[data-show='student-logged-in']");
    let student = null;
    try { student = (await API.get("/api/session")).student; } catch (_) { /* server unreachable: treat as logged out */ }
    loggedOut.forEach((el) => el.classList.toggle("d-none", !!student));
    loggedIn.forEach((el) => el.classList.toggle("d-none", !student));
    document.querySelectorAll("[data-student-name]").forEach((el) => { el.textContent = student ? student.full_name : ""; });
    document.querySelectorAll("[data-action='student-logout']").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.preventDefault();
        try { await API.post("/api/student/logout"); } catch (_) { /* ignore */ }
        window.location.href = "index.html";
      });
    });
    const year = document.getElementById("year");
    if (year) year.textContent = new Date().getFullYear();
    return student;
  }

  return { esc, formatDate, stars, semesterLabel, categoryIcon, toast, setLoading,
           showFieldErrors, clearFieldErrors, initStudentNav, RATING_WORDS };
})();
