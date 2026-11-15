/*
 * Where is the backend API?
 *
 *  ""  (empty)  → same origin. Use this when Flask serves the frontend
 *                 (local development and the Vercel deployment).
 *  "https://your-backend.vercel.app"
 *               → only if you host the frontend in a separate Vercel
 *                 project without an /api rewrite. Also set CORS_ORIGINS
 *                 on the backend (see docs/deployment.md §8).
 *
 * This file contains NO secrets — database credentials live only on the server.
 */
window.APP_CONFIG = {
  API_BASE_URL: ""
};
