<div align="center">
  <img alt="Logo" src="readme_images/multi_device_mockup.png"></a>
  <br>
  <h1>Hevy Insights</h1>
  This project is a used to gather data from Hevy API endpoints and visualize it in a web interface, acting as alternative for the Hevy PRO membership.

  ---

  <!-- Placeholder for badges -->
  ![GitHub License](https://img.shields.io/github/license/casudo/Hevy-Insights) ![GitHub release (with filter)](https://img.shields.io/github/v/release/casudo/Hevy-Insights) ![GitHub action checks](https://img.shields.io/github/check-runs/casudo/Hevy-Insights/main) ![GitHub issues](https://img.shields.io/github/issues/casudo/Hevy-Insights) ![GitHub last commit](https://img.shields.io/github/last-commit/casudo/Hevy-Insights)
</div>

> [!NOTE]
> Check it out at: [**Hevy Insights Online**](https://hevy.kida.one)

# About Hevy Insights <!-- omit from toc -->

Hevy Insights is a dynamic web application that provides insights and analytics of your workouts and exercises. It visualizes workout data from the Hevy app in a clean dashboard so that you can always keep track of your progress!

In the Hevy app you can only see your stats and progress up to 3 months for free, otherwise you need the paid Hevy PRO membership.
Hevy Insights allows you to log in with your Hevy credentials and fetch your workout data directly from Hevy's API, providing you with detailed visualizations and historical data up to the date of your account creation - no PRO membership required!

# Table of Contents <!-- omit from toc -->

- [Features](#features)
  - [Progressive Overload \& Plateau Detection](#progressive-overload--plateau-detection)
  - [Multi-Vendor Support](#multi-vendor-support)
- [Screenshots](#screenshots)
- [Login Comparison](#login-comparison)
- [Usage](#usage)
  - [Hosted Online](#hosted-online)
  - [Local Setup](#local-setup)
  - [Docker](#docker)
- [Future Goals](#future-goals)
- [Technical Documentation](#technical-documentation)
  - [Project Structure](#project-structure)
  - [High-Level-Flow](#high-level-flow)
    - [API Authentication Flow](#api-authentication-flow)
  - [API in Dev vs Prod](#api-in-dev-vs-prod)
    - [When nginx.conf is used](#when-nginxconf-is-used)
    - [Direct-to-Backend with CORS](#direct-to-backend-with-cors)
- [Legal Disclaimer](#legal-disclaimer)
- [License](#license)
- [Support](#support)

# Features

- **Authentication**: Multiple login options for flexibility:
  - **Hevy Credentials (OAuth2)**: Login with your Hevy username/email and password using OAuth2 with automatic reCAPTCHA v3 handling (no PRO membership required)
  - **Hevy PRO API Key**: Use your revokable Hevy PRO API key from [hevy.com/settings?developer](https://hevy.com/settings?developer)
  - **CSV Upload**: Upload your exported workout CSV file from the Hevy app
  - Authentication tokens are stored in **secure HttpOnly cookies** (not accessible to JavaScript, protecting against XSS attacks)
  - User preferences are stored in your browser's local storage
- **Dashboard**: Interactive charts and statistics of your workouts, including volume, muscle distribution and hours trained.
- **Workout History**: Workout logs with detailed exercise information up to the date of account creation - switch between card and list views.
- **Exercises**: View all exercises with video thumbnails and detailed stats.
  - **Progressive Overload**: Per-exercise status (progressing, ready to increase, holding, plateau suspected, regressing) with a concrete next-session recommendation such as adding weight or reps
  - **Plateau Detection**: Flags exercises with no meaningful progress across several sessions
  - **Multi-Vendor Support**: Track the same exercise even if trained with different vendors (e.g. Chest Flys from Gym A and Gym B) without mixing progress or stats.
- **Body Measurements**: Track your weight and body fat percentage over time with interactive charts.
- **Custom Settings**: Individualize your experience when using Hevy Insights.
- **Languages**: Language support for 🇺🇸, 🇩🇪 and 🇪🇸.

## Progressive Overload & Plateau Detection

Hevy Insights analyzes each exercise across recent training sessions ("exposures") and reports both a **status** and a concrete **recommendation**. The analysis is exposure-based, so calendar gaps (e.g. training an exercise every other week) do not distort the trend.

### Statuses <!-- omit from toc -->

- **📈 Progressing**: e1RM, reps or volume is trending up beyond measurement noise
- **🎯 Ready to increase**: all working sets reached the top of the target rep range at a stable load
- **➡️ Holding**: performance is stable, but for fewer exposures than the plateau threshold
- **⏸️ Plateau suspected**: no meaningful new best across several consecutive exposures
- **📉 Regressing**: performance is declining across recent exposures
- **🔄 Returning**: the exercise was not trained in a long time, so old sessions are not compared directly
- **⚪ Insufficient data**: not enough workout history yet

### Recommendations <!-- omit from toc -->

Each status maps to an action: add weight, add reps, hold, deload, resume, or build more history. Load increases are capped at **10% per week** and rounded to a sensible plate increment; assisted exercises progress by reducing assistance. Cardio exercises progress by distance or duration instead.

### How It Works <!-- omit from toc -->

1. Collects the last N sessions (configurable, default 5) for each exercise
2. Tracks top-set weight and reps, estimated 1RM (Epley), volume, and RPE per session
3. Fits a trend over exposures and counts consecutive sessions without a new best
4. Treats a rep drop after a load increase as progression, not regression
5. Displays the status and recommendation on each exercise card

**Target rep range:** when you train an exercise from a Hevy routine, the prescribed reps are read from your routines and used as the top of the target range ("double progression"). Otherwise the range is inferred from your history. Routine targets require an OAuth (Hevy credentials) login; PRO API-key sessions use inferred targets.

## Multi-Vendor Support

It can happen that you train the same exercise (e.g. Chest Flys) in different gyms or with different equipment, which can lead to incorrect statistics because you are mixing two vendors together which may have a different weight progression. For example, you might have trained Chest Flys in Gym A which has a maximum weight of 80kg, and then you switch to Gym B which has a maximum weight of 110kg. 

If you mix the stats together, strength progression, personal records and other metrics will be skewed. In Hevy Insights you can create multiple vendors for the same exercise so that Hevy Insights can automatically assign each workout session to the correct vendor, so that you can track your progress accurately for each vendor without mixing them together.

[Image](/readme_images/exercises_multivendor.png)

# Screenshots

> [!NOTE]
> Screenshots as of **v1.3.0**

*Login Page*
![Login Page](/readme_images/login_page.png)

*Dashboard*
![Dashboard Page](/readme_images/dashboard_page.png)

*Workouts Page - Card Design*
![Workouts Page - Card Design](/readme_images/workout_page_card.png)

*Workouts Page - List Design*
![Workouts Page - List Design](/readme_images/workout_page_list.png)

---

# Login Comparison

You can decide based on your needs which login method suits you best:

> [!TIP]
> I recommed using the **Hevy Credentials Login** for the best experience since it shows the most data.

| Feature                      | Hevy Credentials Login       | Hevy PRO API Key Login       | CSV Upload                   |
| ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- |
| Requires Hevy PRO Membership | ✅ No                         | ❌ Yes                        | ✅ No                         |
| Data Freshness               | ✅ Live data from Hevy API    | ✅ Live data from Hevy API    | ❌ Static data from CSV file  |
| Data Range                   | ✅ Full history from Hevy API | ✅ Full history from Hevy API | ✅ Full history from CSV file |
| Personal Record Tracking     | ✅ Yes                        | ❌ No                         | ⚠️ Yes, but not in detail     |
| Muscle Distribution Data     | ✅ Yes                        | ❌ No                         | ⚠️ Not everything             |
| Media (Images/GIFs)          | ✅ Yes                        | ❌ No                         | ❌ No                         |
| Plateu Detection             | ✅ Yes                        | ✅ Yes                        | ✅ Yes                        |
| Workout Streaks              | ✅ Yes                        | ✅ Yes                        | ❌ No                         |
| Calories & Heart Rate Data   | ✅ Yes                        | ❌ No                         | ❌ No                         |
| Body Measurements            | ✅ Yes                        | ❌ No                         | ❌ No                         |
| Multi-Vendor Support         | ✅ Yes                        | ✅ Yes                        | ✅ Yes                        |

> [!IMPORTANT]
> **Why the differences in the login modes?** It's because not every login method provides the same data to use. The [Hevy PRO API](https://api.hevyapp.com/docs/#/) key login only provides data for a small amount of features compared to what you can see inside the Hevy app (which is using the **Hevy Credentials** login method). The CSV upload is the most basic one, it only provides the data that is contained in the CSV file you can export from the Hevy app, which is by far not everything that the Hevy API provides.

# Usage

You can either use Hevy Insights online or run it locally on your machine via multiple methods.

## Hosted Online

Navigate to the hosted version of Hevy Insights at: [https://hevy.kida.one](https://hevy.kida.one)

The latest version is always hosted there.

> [!IMPORTANT]
> **Authentication tokens** are stored in **secure HttpOnly cookies** on **your browser only**!
> These cookies are not accessible to JavaScript (XSS protection) and are automatically sent with API requests.  
> **User preferences** (theme, language, settings) are stored in your browser's local storage.

## Local Setup

Clone/download the repository and follow these steps:

1. Rename `.env.example` to `.env`.

2. Install the backend and frontend dependencies.

   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r backend\requirements.txt
   playwright install chromium
   cd frontend && npm ci
   ```

   On macOS/Linux, activate the virtual environment with `source venv/bin/activate` and use `/` instead of `\` in paths.

   Re-run `playwright install chromium` if Playwright is upgraded or the backend reports a missing browser executable.

   The backend stores auth session data in `backend/data/hevy.db` by default. Set `DATABASE_PATH` to use a different SQLite file path. Relative paths resolve from `backend/`.

   The backend runs Alembic migrations automatically on startup. To apply migrations explicitly, run `alembic -c backend/alembic.ini upgrade head` from an activated backend virtual environment.

3. **Start the backend** (Terminal 1):

   `uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 5000`

4. **Start the frontend** (Terminal 2):

   `cd frontend; npm run dev`

5. **Open your browser** and navigate to `http://localhost:5173`

6. **Login** with the desired login method.

## Docker

> [!NOTE]
> The front- and backend images are available for `linux/amd64` and `linux/arm64` architectures.

1. Run the containers:

  `docker-compose up -d`

  > [!NOTE]
  > You can find the [docker-compose.yaml](./docker-compose.yaml) file in the repository root folder.

2. Open your browser and navigate to `http://localhost:8123`

3. Login with the desired login method.

---

# Future Goals

- Better logging
- Add visual representation of trained muscle groups (body heatmap)
- In-depth muscle analysis page
- Remove emojis, use icons instead
- Resort/group CSS styles better
- Dashboard: Top stats: Display them more in rows instead of big "buttons". Maybe like "🏋️ 25 Total Workouts * 💪 282.741,5 kg Total Volume * ⏱️ 34h 15m Total Time Trained"
- CSV upload: PRs not shown and muscle regions missing
- To get more space on mobile: Dashboard charts: Hide Filters. Add something similar to the „i“ button which shows the filters
- Better tablet screen responsiveness
- Dashboard recent PRs: Add unit (seconds/formatted minutes) for "Best Duration" stat
- Workouts pages: PR "best duration" not localized and no unit shown
- Plateu detection not working correctly in Hevy PRO API key login mode
- Add ability on profile page to change account privacy settings (public/private) and opt-in/out of settings like "comments_push_enabled"
- "Clear all" button to flush localStorage?
- Switch `requests` library to `httpx` to be consistent?
- Let the user choose the primary and secondary colors in settings
- Switch to per page localization instead of using `global.{n}.{y}` and reusing the same string from other pages
- Support for distance-based workouts (running, cycling, etc.) and their specific stats (e.g., pace, distance)
  - Seperate distance stats for duraion-based workouts (e.g. Dead Hang)
- "Top 3 Best Sets" not actually showing the best sets for bodyweight exercises
- Multi-Vendor Support: In addition to filtering for include "All Vendors" or "Only Vendor X", add a exclude filter "Exclude Vendor X" so that you can exclude a specific vendor from the stats without excluding all other vendors.

---

# Technical Documentation

> [!NOTE]
> As of March 2026, **v1.8.6**

## Project Structure

```bash
hevy-insights/
├── backend/                   # Backend Components
│   ├── .dockerignore          # Docker ignore file for backend
│   ├── Dockerfile_backend     # Dockerfile for backend
│   ├── app/                   # FastAPI application package
│   │   ├── api/               # API router and route modules
│   │   ├── clients/           # Hevy API and reCAPTCHA clients
│   │   ├── core/              # Settings, database, logging, rate limiting, security helpers
│   │   ├── db/                # SQLAlchemy tables and Alembic migrations
│   │   ├── schemas/           # Pydantic schemas and Hevy API DTOs
│   │   ├── services/          # Demo data and version-check services
│   │   └── main.py            # FastAPI app factory and ASGI app
│   └── requirements.txt       # Python backend dependencies
└── frontend/                  # Frontend Components
    ├── public/                # Static assets
    ├── src/                   # Vue 3 TypeScript application
    │   ├── locales/           # i18n language files
    │   ├── router/            # Vue Router configuration with auth guards
    │   │   └── index.ts       # Router entry point
    │   ├── services/          # API communication layer (Axios)
    │   │   └── api.ts         # Axios instance and API functions
    │   ├── stores/            # Pinia store for state management
    │   │   └── hevy_cache.ts  # Hevy data caching
    │   ├── utils/             # Utility functions
    │   │   ├── csvCalculator.ts  # CSV data calculation 
    │   │   ├── csvParser.ts   # CSV data parsing
    │   │   ├── exerciseTypeDetector.ts  # Exercise type detection logic
    │   │   └── formatter.ts   # Data formatting functions
    │   ├── views/             # Page components (Login, Dashboard, Workouts, ...)
    │   ├── App.vue            # Root Vue component
    │   ├── main.ts            # Vue app entry point
    │   └── style.css          # Global styles
    ├── .dockerignore          # Docker ignore file for frontend
    ├── Dockerfile_frontend    # Dockerfile for frontend
    ├── index.html             # HTML entry point
    ├── nginx.conf             # Nginx configuration for production
    ├── package-lock.json      # npm package lock file
    ├── package.json           # Node.js dependencies
    ├── tsconfig.app.json      # TypeScript configuration for the app
    ├── tsconfig.json          # TypeScript configuration
    ├── tsconfig.node.json     # TypeScript configuration for Node.js
    └── vite.config.ts         # Vite build configuration
```

## High-Level-Flow

- **index.html**: Browser loads this HTML document first. It defines the root node `<div id="app"></div>` and includes `<script type="module" src="/src/main.ts">`.
- **main.ts**: Entry script runs. Vite serves ES modules and applies HMR in dev. We `createApp(App)`, install `Pinia` and the `Router`, then `mount("#app")`.
- **App.vue**: Root component renders the global shell (fixed sidebar + main). On mount and after each route change it checks `localStorage` for `hevy_access_token` to toggle sidebar visibility and protect routes.
- **Router**: Resolves the current URL (`/login`, `/dashboard`, `/workouts-card`, `/workouts-list`) and renders the matched view inside `<router-view />`. Auth guards check authentication status from backend via `/api/auth/status` endpoint.
- **View Components**: The matched page component (`Login.vue`, `Dashboard.vue`, `Workouts_Card.vue`, `.....vue`) runs `setup()` and lifecycle hooks (`onMounted`).
- **Pinia Store** (*frontend/src/stores/hevy_cache.ts*): Centralized state with 5‑minute caching for workouts (`workoutsLastFetched`). Exposes actions `fetchUserAccount()`, `fetchWorkouts(force)` and getters like `username`, `hasWorkouts`. Prevents redundant API calls when navigating.
- **Axios Service** (*frontend/src/services/api.ts*): Configures base URL with `withCredentials: true` for cookie support. Authentication is handled automatically via HttpOnly cookies set by the backend. All frontend API calls to the backend go through these typed helpers.
- **Backend** (FastAPI): Serves `/api` endpoints. Supports dual authentication (OAuth2 Bearer tokens or PRO API keys) via HttpOnly cookies. Workouts and their exercises are cached lazily in the configured SQLite database, defaulting to `backend/data/hevy.db`; sync fetches from newest to oldest until it reaches an already-stored workout ID, then normalized responses are returned from SQLite. Frontend receives JSON responses and Vue reactivity updates the UI.

### API Authentication Flow

**OAuth2 Authentication (Credentials):**

1. User logs in via `/api/login` endpoint with Hevy credentials
2. Backend automatically generates reCAPTCHA v3 token using Playwright (headless Chrome)
3. Backend authenticates with Hevy API using OAuth2 and receives `access_token` + `refresh_token`
4. Backend creates a Hevy saved-account secret and stores it server-side in the configured SQLite database, defaulting to `backend/data/hevy.db`
5. Backend sets **HttpOnly cookies** (`hevy_access_token`, `hevy_refresh_token`, `hevy_token_expires_at`, `hevy_session_id`)
6. Browser automatically sends cookies with subsequent API requests
7. Backend reads authentication from cookies and proxies requests to Hevy API
8. On token expiration, backend re-logins via Hevy's saved-account flow using the server-side session secret

**PRO API Key Authentication:**

1. User validates API key via `/api/validate_api_key` endpoint
2. Backend sets **HttpOnly cookies** (`hevy_api_key`, marker token)
3. Browser automatically sends cookies with subsequent API requests
4. Backend routes requests to Hevy PRO API endpoints

## API in Dev vs Prod

- In development, the frontend talks directly to the FastAPI server: the Axios base URL in [frontend/src/services/api.ts](frontend/src/services/api.ts) is `http://localhost:5000/api` when `import.meta.env.PROD` is false.
- In production, the Axios base URL is `/api` (same origin). Requests resolve as `https://your-domain/api/...` and are reverse‑proxied to the backend by Nginx.
- The `import.meta.env.PROD` flag is set automatically by Vite at build time. No extra configuration is required.

### When nginx.conf is used

- The file [frontend/nginx.conf](frontend/nginx.conf) is used when the built frontend is served by Nginx (e.g. on a server with Nginx).
- It performs two critical roles:
   - SPA fallback: routes like `/dashboard` and `/workouts-list` return `index.html` so client‑side routing works.
   - API proxy: requests to `/api/...` are forwarded to the FastAPI backend (e.g., `http://backend:5000`). This keeps a single public origin and avoids CORS in production.
- If your deployment does not use Nginx (e.g., serving static files from a CDN without proxying), ensure your hosting platform supports SPA fallback and adjust the API base accordingly.

### Direct-to-Backend with CORS

- In local development, the frontend dev server runs on `http://localhost:5173` and the backend on `http://localhost:5000`. Because these are different origins, FastAPI enables CORS middleware so the browser can call the backend directly.
- CORS setup in `backend/app/main.py`.
- In production behind Nginx, CORS is not required because the frontend and `/api` share the same origin.

# Legal Disclaimer

This project is not affiliated with or endorsed by Hevy or its parent company. It is a third-party application developed for personal use and educational purposes only. Users are responsible for complying with Hevy's terms of service when using this application. The developer assumes no liability for any issues arising from the use of this software.

# License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

# Support

I work on this project in my free time and unpaid. If you find it useful and would like to support its development, consider buying me a coffee:

[![Buy Me a Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/casudo)
