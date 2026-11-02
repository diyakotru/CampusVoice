/*
 * Where is the backend API?
 *
 *  ""  (empty)  → same origin. Use this when Flask serves the frontend
 *                 (local development and the recommended Render setup).
 *  "https://your-backend.onrender.com"
 *               → only if you host the frontend separately (e.g. a Render
 *                 Static Site). Also set CORS_ORIGINS on the backend.
 *
 * This file contains NO secrets — database credentials live only on the server.
 */
window.APP_CONFIG = {
  API_BASE_URL: ""
};
