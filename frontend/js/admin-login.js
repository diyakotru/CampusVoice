/* Admin login: POST credentials, the server answers with a signed session cookie. */
document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("adminLoginForm");
  const button = document.getElementById("loginBtn");
  const alertBox = document.getElementById("loginAlert");
  const notice = document.getElementById("notice");

  const params = new URLSearchParams(location.search);
  if (params.get("expired")) { notice.textContent = "Your session has expired. Please sign in again."; notice.classList.remove("d-none"); }
  if (params.get("loggedout")) { notice.textContent = "You have been logged out."; notice.className = "alert alert-success small"; }

  // Already logged in? Go straight to the dashboard.
  try {
    if ((await API.get("/api/session")).admin) { window.location.replace("dashboard.html"); return; }
  } catch (_) { /* server unreachable — show the form */ }

  document.getElementById("togglePw").addEventListener("click", (e) => {
    const pw = form.password;
    const show = pw.type === "password";
    pw.type = show ? "text" : "password";
    e.currentTarget.innerHTML = `<i class="bi ${show ? "bi-eye-slash" : "bi-eye"}"></i>`;
    e.currentTarget.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    UI.clearFieldErrors(form);
    alertBox.classList.add("d-none");
    const body = { username: form.username.value.trim(), password: form.password.value };
    const errors = {};
    if (!body.username) errors.username = "Username is required.";
    if (!body.password) errors.password = "Password is required.";
    if (Object.keys(errors).length) { UI.showFieldErrors(form, errors); return; }

    UI.setLoading(button, true, "Signing in…");
    try {
      await API.post("/api/admin/login", body);
      window.location.replace("dashboard.html");
    } catch (err) {
      alertBox.textContent = err.message;
      alertBox.classList.remove("d-none");
      form.password.value = "";
      form.password.focus();
      UI.setLoading(button, false);
    }
  });
});
