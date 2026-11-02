/* Student login + registration. On success the server sets the session cookie. */
document.addEventListener("DOMContentLoaded", async () => {
  // Only allow redirects to our own pages (prevents "open redirect" abuse).
  const next = new URLSearchParams(location.search).get("next");
  const target = next && /^[a-z-]+\.html$/.test(next) ? next : "history.html";

  try {
    if ((await API.get("/api/session")).student) {
      window.location.replace(target);   // already logged in
      return;
    }
  } catch (_) { /* server unreachable — the forms will show the error on submit */ }

  if (location.hash === "#register") bootstrap.Tab.getOrCreateInstance(document.getElementById("tab-register")).show();

  function wire(form, endpoint, buildBody, clientCheck) {
    const alertBox = form.querySelector("[data-role=alert]");
    const button = form.querySelector("button[type=submit]");
    form.addEventListener("input", (e) => {
      e.target.classList.remove("is-invalid");
      const box = form.querySelector(`[data-error-for="${e.target.name}"]`);
      if (box) box.classList.remove("d-block");
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      UI.clearFieldErrors(form);
      alertBox.classList.add("d-none");
      const body = buildBody(form);
      const errors = clientCheck(body, form);
      if (Object.keys(errors).length) { UI.showFieldErrors(form, errors); return; }

      UI.setLoading(button, true);
      try {
        await API.post(endpoint, body);
        window.location.href = target;
      } catch (err) {
        UI.showFieldErrors(form, err.fields);
        alertBox.textContent = err.message;
        alertBox.classList.remove("d-none");
        UI.setLoading(button, false);
      }
    });
  }

  wire(
    document.getElementById("studentLoginForm"),
    "/api/student/login",
    (f) => ({ student_id: f.student_id.value.trim().toUpperCase(), password: f.password.value }),
    (b) => {
      const errors = {};
      if (!b.student_id) errors.student_id = "Student ID is required.";
      if (!b.password) errors.password = "Password is required.";
      return errors;
    }
  );

  wire(
    document.getElementById("studentRegisterForm"),
    "/api/student/register",
    (f) => ({
      full_name: f.full_name.value.trim().replace(/\s+/g, " "),
      student_id: f.student_id.value.trim().toUpperCase(),
      department: f.department.value,
      password: f.password.value,
    }),
    (b, f) => {
      const errors = {};
      if (!/^[A-Za-z][A-Za-z .'-]{1,99}$/.test(b.full_name)) errors.full_name = "Enter your full name (letters only).";
      if (!/^[A-Z0-9/_-]{3,20}$/.test(b.student_id)) errors.student_id = "3–20 characters: letters, digits, / _ -";
      if (!b.department) errors.department = "Please select your department.";
      if (b.password.length < 8 || !/[A-Za-z]/.test(b.password) || !/\d/.test(b.password))
        errors.password = "At least 8 characters with a letter and a number.";
      if (f.confirm.value !== b.password) errors.confirm = "Passwords do not match.";
      return errors;
    }
  );
});
