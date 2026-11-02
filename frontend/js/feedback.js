/*
 * Feedback form logic.
 * 1. Validate in the browser (fast feedback for the student).
 * 2. POST the JSON to /api/feedback.
 * 3. The server validates again and stores it in Supabase PostgreSQL.
 * 4. Show success and clear the form, or show the server's error messages.
 */
document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("feedbackForm");
  const submitBtn = document.getElementById("submitBtn");
  const formAlert = document.getElementById("formAlert");
  const successPanel = document.getElementById("successPanel");
  const starWrap = document.getElementById("starRating");
  const stars = [...starWrap.querySelectorAll("button")];
  const ratingInput = document.getElementById("rating");
  const ratingText = document.getElementById("ratingText");
  const categoryGrid = document.getElementById("categoryGrid");

  let student = null;

  // ---------- logged-in student: prefill and lock name / ID ----------
  function applyStudent() {
    document.getElementById("studentBanner").classList.toggle("d-none", !student);
    document.getElementById("guestBanner").classList.toggle("d-none", !!student);
    if (student) {
      form.student_name.value = student.full_name;
      form.student_id.value = student.student_id;
      form.student_name.readOnly = true;
      form.student_id.readOnly = true;
      if (!form.department.value) form.department.value = student.department;
    }
  }
  student = await UI.initStudentNav();
  applyStudent();

  // ---------- star rating ----------
  function paintStars(value) {
    stars.forEach((btn) => btn.classList.toggle("on", Number(btn.dataset.value) <= value));
  }
  function setRating(value) {
    ratingInput.value = value || "";
    stars.forEach((btn) => btn.setAttribute("aria-checked", String(Number(btn.dataset.value) === value)));
    paintStars(value);
    ratingText.textContent = value ? `${value} / 5 · ${UI.RATING_WORDS[value]}` : "Click to rate";
    if (value) {
      starWrap.classList.remove("is-invalid");
      setError("rating", "");
    }
  }
  stars.forEach((btn) => {
    btn.addEventListener("click", () => setRating(Number(btn.dataset.value)));
    btn.addEventListener("mouseenter", () => paintStars(Number(btn.dataset.value)));
    btn.addEventListener("keydown", (e) => {   // arrow keys change the rating
      const current = Number(ratingInput.value) || 0;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") { e.preventDefault(); setRating(Math.min(5, current + 1)); stars[Math.min(5, current + 1) - 1].focus(); }
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") { e.preventDefault(); setRating(Math.max(1, current - 1)); stars[Math.max(1, current - 1) - 1].focus(); }
    });
  });
  starWrap.addEventListener("mouseleave", () => paintStars(Number(ratingInput.value) || 0));

  // ---------- character counters ----------
  [["description", "descCount"], ["suggestions", "sugCount"]].forEach(([field, counter]) => {
    const el = form[field];
    const out = document.getElementById(counter);
    const update = () => { out.textContent = el.value.length; };
    el.addEventListener("input", update);
    update();
  });

  // ---------- validation (mirrors backend/utils/validators.py) ----------
  const NAME_RE = /^[A-Za-z][A-Za-z .'-]{1,99}$/;
  const ID_RE = /^[A-Z0-9/_-]{3,20}$/;

  function setError(name, message) {
    const box = form.querySelector(`[data-error-for="${name}"]`);
    const input = form.querySelector(`[name="${name}"]:not([type=hidden]):not([type=radio])`);
    if (box) { box.textContent = message; box.classList.toggle("d-block", !!message); }
    if (input) input.classList.toggle("is-invalid", !!message);
    if (name === "category") categoryGrid.classList.toggle("is-invalid", !!message);
    if (name === "rating") starWrap.classList.toggle("is-invalid", !!message);
  }

  function collect() {
    const checked = form.querySelector("input[name=category]:checked");
    return {
      student_name: form.student_name.value.trim().replace(/\s+/g, " "),
      student_id: form.student_id.value.trim().toUpperCase(),
      department: form.department.value,
      semester: form.semester.value ? Number(form.semester.value) : "",
      category: checked ? checked.value : "",
      rating: ratingInput.value ? Number(ratingInput.value) : "",
      description: form.description.value.trim(),
      suggestions: form.suggestions.value.trim(),
    };
  }

  function validate(data) {
    const errors = {};
    if (!data.student_name) errors.student_name = "Name is required.";
    else if (!NAME_RE.test(data.student_name)) errors.student_name = "Use 2–100 letters (spaces, . ' - allowed).";
    if (!data.student_id) errors.student_id = "Student ID is required.";
    else if (!ID_RE.test(data.student_id)) errors.student_id = "3–20 characters: letters, digits, / _ -";
    if (!data.department) errors.department = "Please select your department.";
    if (!data.semester) errors.semester = "Please select your semester.";
    if (!data.category) errors.category = "Please choose a feedback category.";
    if (!data.rating) errors.rating = "Please select a star rating.";
    if (!data.description) errors.description = "Please describe your feedback.";
    else if (data.description.length < 10) errors.description = "Please write at least 10 characters.";
    if (data.suggestions.length > 1000) errors.suggestions = "Maximum 1000 characters.";
    return errors;
  }

  // clear a field's error as soon as the user fixes it
  form.addEventListener("input", (e) => { if (e.target.name) setError(e.target.name, ""); });
  form.addEventListener("change", (e) => { if (e.target.name) setError(e.target.name, ""); });

  // Runs after the browser's native reset has cleared the inputs.
  function afterReset() {
    UI.clearFieldErrors(form);
    categoryGrid.classList.remove("is-invalid");
    starWrap.classList.remove("is-invalid");
    setRating(0);
    formAlert.classList.add("d-none");
    document.getElementById("descCount").textContent = "0";
    document.getElementById("sugCount").textContent = "0";
    applyStudent();
  }

  function resetForm() {
    form.reset();   // fires the "reset" event below as well; afterReset is safe to run twice
    afterReset();
  }

  form.addEventListener("reset", () => setTimeout(afterReset, 0));

  // ---------- submit ----------
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    formAlert.classList.add("d-none");
    const data = collect();
    const errors = validate(data);
    ["student_name", "student_id", "department", "semester", "category", "rating", "description", "suggestions"]
      .forEach((f) => setError(f, errors[f] || ""));
    if (Object.keys(errors).length) {
      UI.toast("Please fix the highlighted fields.", "danger");
      const first = form.querySelector(".is-invalid, .category-grid.is-invalid input, .star-rating.is-invalid button");
      if (first) first.focus();
      return;
    }

    UI.setLoading(submitBtn, true, "Submitting…");
    try {
      const result = await API.post("/api/feedback", data);
      document.getElementById("refNumber").textContent = `#${result.feedback.id}`;
      resetForm();
      form.classList.add("d-none");
      successPanel.classList.remove("d-none");
      successPanel.focus();
      window.scrollTo({ top: 0, behavior: "smooth" });
      UI.toast(result.message, "success");
    } catch (err) {
      if (err.fields && Object.keys(err.fields).length) Object.entries(err.fields).forEach(([f, m]) => setError(f, m));
      formAlert.textContent = err.message;
      formAlert.classList.remove("d-none");
      UI.toast(err.message, "danger");
    } finally {
      UI.setLoading(submitBtn, false);
    }
  });

  document.getElementById("anotherBtn").addEventListener("click", () => {
    successPanel.classList.add("d-none");
    form.classList.remove("d-none");
    form.student_name.readOnly ? form.department.focus() : form.student_name.focus();
  });
});
