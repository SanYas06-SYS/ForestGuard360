# VanRakshak 360

College demonstration of integrated forest monitoring, wildlife protection and eco-tourism, aligned with Synopsis.docx. Stack: Python/FastAPI, PostgreSQL, React, Tailwind, Leaflet/OpenStreetMap. The optional real camera bridge uses YOLO.

## Run this configured Windows copy

Double-click `start.cmd`, then open http://127.0.0.1:8000. Use ADMIN_EMAIL and ADMIN_PASSWORD from your existing `.env` to sign in. Keep `.env` private. The Python environment and compiled frontend are installed in this copy.

## Demonstration walkthrough

1. Sign in as administrator. In Response teams, create officer/rescue accounts, add a member to a team, and save its map/GPS position and Available status, then draw and save its patrol area.
2. Open Live monitoring & GIS. The map shows incidents, team positions, sensors, wildlife sightings and the clearly marked demonstration restricted zone.
3. Use the College demonstration simulator to submit a sensor reading. Temperature >=55 C or smoke >=60/100 creates a fire alert requiring review. Repeated threshold alerts from the same device are suppressed for five minutes.
4. Simulate a camera fire, illegal-logging or human-activity event. It is labeled DEMO and assigned to the nearest available staffed team whose saved patrol area contains the incident. Busy assignments across both fire and conflict cases exclude a team. No trained model runs in the simulator.
5. Open the incident queue, inspect the case history, and advance Assigned -> Responding -> Resolved. The team becomes eligible for another automatic assignment when its active cases finish.
6. Simulate a wildlife sighting to add a species/GPS record to the map.
7. Open Eco-tourism to see a fictional trail and forest guidelines. Administrators can publish routes by adding ordered points on a map. Routes published in demo mode are labeled DEMO.
8. A community account can submit reports and see only its own report list. Rescue staff can read and update incidents assigned to their account or team. Admin/officer roles manage case assignment.

The dashboard and monitoring screen refresh every ten seconds. Notifications are in-app alerts; SMS/email/push services are not configured. The database is hosted and requires internet; map tiles also require internet. Report text drafts are stored locally, but submitting reports requires connectivity. Photo evidence uploads are optional and are stored in PostgreSQL by the application; no Cloudinary credentials are required.

## Fresh installation

Use Python 3.12 and a recent Node.js version compatible with the pinned Vite release. In PowerShell, use `npm.cmd` if execution policy blocks `npm.ps1`.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: PostgreSQL URL, random secrets, administrator email/password.
.venv\Scripts\python.exe -m backend.demo_setup
npm.cmd --prefix frontend ci
npm.cmd run build
.\start.cmd
```

`backend.demo_setup` applies the idempotent schema, inserts the administrator only if absent, enables DEMO_MODE, and inserts the fictional route/zone. It does not reset existing account passwords. `backend.seed_admin` explicitly creates or resets the configured administrator. For deployment, disable DEMO_MODE, use HTTPS with NODE_ENV=production, and calibrated sensors/trained models. This prototype is not a certified emergency detection system.

## Development and checks

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q tests
npm.cmd run build
.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --port 8000
# In another terminal:
npm.cmd --prefix frontend run dev
```

Integration tests create unique disposable PostgreSQL schemas, exercise permissions, reporting, dispatch, state transitions, sensor deduplication and tourism, and remove only their own schemas. Database credentials need CREATE SCHEMA permission. They never reset the public application tables.

## Interfaces

- Auth: `/api/auth/session`, `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`
- Operations: `/api/admin/overview`, `/api/incidents`, `/api/incidents/{fire|conflict}/{id}`
- Teams: `/api/staff`, `/api/response-teams`, `/api/response-teams/{id}/members`
- Community: `/api/fires`, `/api/conflicts`, `/api/my-reports`
- Monitoring: `GET /api/monitoring`; admin-only `POST /api/demo/events` when DEMO_MODE=true
- Sensors: `POST /api/sensors/readings`, authenticated with `x-sensor-key: SENSOR_WEBHOOK_SECRET`; fields deviceId, latitude, longitude, temperature, humidity, smoke
- Tourism: public `GET /api/tourism`; admin `POST /api/tourism/routes`
- AI ingestion: `POST /api/ai/detections`, authenticated with `x-ai-key: AI_WEBHOOK_SECRET`
- Cloudinary: `/api/cloudinary/signature`

Sensor smoke values are normalized 0â€“100, not ppm. Human detection signals presence only; an officer must verify authorization. No trained weights, physical sensors, camera streaming, mobile app, or automatic identification of illegal behavior are included. The demonstration explicitly simulates these inputs.

## Optional real YOLO bridge

Install `ai_service/requirements.txt`, configure YOLO_MODEL_PATH to a trained local model, and start `.venv\Scripts\python.exe -m uvicorn ai_service.detector:app --port 8100`. POST a JPEG/PNG/WebP frame with latitude/longitude and an `x-ai-key` header to `/detect`. `/health` reports whether weights are present. Recognized classes: forest_fire, smoke, illegal_logging, tree_cutting, wildlife, human (person is mapped to human). Custom fire/logging classes require appropriate training data. Generic weights do not establish that activity is illegal.

## Dependency audit

The installed frontend toolchain audit reports a picomatch advisory propagated through Vite build dependencies. The registry currently reports picomatch 4.0.7 as latest, within the advisory range. Do not expose the development server publicly; use the compiled frontend served by FastAPI. Recheck `npm.cmd --prefix frontend audit` when updating build tooling. Real model inference requires trained weights and is not part of the software-only demonstration verification.


## Independent tab sign-in

Each tab stores its own opaque session token in sessionStorage. A new tab starts at sign-in; refreshing or navigating within an existing tab keeps its account. Supported browsers also detect copied tab storage with BroadcastChannel. Sign out revokes only the current tab token in PostgreSQL. Sessions expire after 12 hours; only token hashes are stored in the database. Old shared login cookies are no longer accepted, so sign in once after this update. Browser session restore may restore sessionStorage; explicitly sign out on shared devices.

Report drafts are isolated by account and tab. All protected screens include navigation and a visible Sign out action. If logout cannot reach the server, the UI shows a retry message and keeps the current login instead of falsely reporting success.

To update an existing installation, run `.venv\Scripts\python.exe -m backend.setup_db`, rebuild the frontend, and restart the server. API clients must send `Authorization: Bearer <token>` using the token returned by login or registration. Public tourism pages do not require login.


## Photos and map selection

Report and team forms use an interactive OpenStreetMap picker. Click/tap to select, drag the pin to refine, or choose Use my location and grant browser location access. If access is denied, selecting on the map still works. Coordinates remain internal for dispatch calculations; users do not type them. Report drafts retain the selected pin in the same tab. Map tiles require internet.

The report photo flow now uploads to `/api/uploads/report-image` using the tab session. The server validates real JPEG/PNG/WebP content, limits files to 10 MB and 25 megapixels, normalizes orientation, strips metadata and resizes to 2400 pixels before storing JPEG bytes in PostgreSQL. `/api/report-images/{id}` requires authorization; the uploader, administrators/officers and assigned responders can view the photo. Existing Cloudinary image links remain supported. The old Cloudinary credential set was rejected by its API; the current report uploader does not use it.

## Manual Render deployment

Connect this repository to Render and create a Blueprint using `render.yaml`.
Alternatively create a Docker Web Service from the repository root. The Dockerfile
builds the React frontend and starts FastAPI; no separate frontend service is needed.
Use `/api/health` as the health check. Startup applies the schema and creates an
administrator only when that email does not already exist; existing passwords are preserved.

Required secret environment variables: `DATABASE_URL` (your PostgreSQL connection
string), `ADMIN_EMAIL`, and `ADMIN_PASSWORD` (12–72 bytes). Keep `PGSSL=true` for
hosted PostgreSQL. Use a dedicated database for the hosted demonstration if you do
not want to share local reports. Photos are stored in PostgreSQL and survive service restarts.
Never upload `.env` or service-account JSON files to GitHub.

The blueprint enables the software simulator (`DEMO_MODE=true`) and automatic
dispatch (`ENABLE_DISPATCH_WORKER=true`). Set `DEMO_MODE=false` to hide the simulator.
Teams must have members, Available status and a location saved within the last
60 minutes (`TEAM_LOCATION_MAX_AGE_MINUTES`). Assignment uses straight-line distance,
excludes busy teams, and queues incidents when no eligible team exists. Team locations
and report locations can be selected on a map or obtained with browser GPS permission.
Demo assignments do not send Android push notifications.

Firebase push remains disabled until configuration is supplied. Later, set
`FIREBASE_SERVICE_ACCOUNT_JSON` as a private Render environment variable (the entire
service-account JSON), or provide a Render secret file and set
`GOOGLE_APPLICATION_CREDENTIALS` to its path. Then set `PUSH_ENABLED=true`. These
server credentials must never be included in Android apps. The guard app will register
its FCM token through `/api/push/devices` after sign-in. The backend has an inbox and
a retrying push outbox; Firebase acceptance is not proof that a phone displayed an alert.
Android apps and end-to-end phone delivery are pending the hosted HTTPS URL and
Firebase Android configuration. Do not use this college demonstration as a sole emergency channel.

A free Render service may sleep when idle, so background dispatch and notification
retries are not guaranteed to run continuously on that plan. The app also needs internet
for PostgreSQL and map tiles. After deployment, check `/api/health`, sign in, save a
team location and submit a demonstration report. Share the HTTPS URL before building
the community and guard Android apps.

## Android apps

The Android project is in `android/`. It builds two separate installable applications:
Community (`com.vanrakshak.community`) for villagers and tourists, and Guard
(`com.vanrakshak.guard`) for officer/rescue accounts. Both connect to
https://forestguard360.onrender.com and reuse the responsive website through an
origin-restricted WebView. Control-room administrators use the website.

Open `android/` in Android Studio, or use JDK 21 and the Gradle wrapper:
`gradlew.bat :app:assembleCommunityDebug :app:assembleGuardDebug`.
These are development APKs for college testing, not Play Store release builds.
Android sign-ins persist after closing the app for up to 30 days. Website sessions remain isolated per tab and expire after 12 hours. My profile lets signed-in members change their password after entering their current password; other sessions are revoked.
Location sharing requires permission and runs only while the My team screen is visible.
Photo attachments use Android's image picker, without broad storage access.

For Guard push, place the Firebase Android configuration at
`android/app/src/guard/google-services.json` before rebuilding. It must register
`com.vanrakshak.guard`. The Gradle build reads client configuration only; never put a
service-account private key in an Android project. Without that file the Guard APK
works with the inbox but shows that Firebase configuration is pending. Allow Android
notifications, sign in with a guard account, and keep the backend Firebase credentials
and `PUSH_ENABLED=true` configured to enable background alerts. Reopen the app to
register a refreshed FCM token. Phone delivery must still be tested on a device with
Google Play services after configuration.

## Team areas and administration

People, teams & patrol areas supports creating, renaming and deleting teams, adding or removing members, and deleting guard/officer login accounts. Deleted accounts lose all sessions; historical case records remain. Teams with active cases and their last members cannot be deleted until those cases are reassigned or finished. Team membership is no longer limited to five people.

Draw a team border by clicking points on the map, adjust points by dragging, then save. Borders include their edges and must not cross. Existing teams start without areas and must have an area saved before automatic dispatch selects them. Overlapping areas select the nearest available team with a fresh location. Uncovered incidents remain queued for manual review. Manual case assignment selects a team, may override area boundaries, and refuses teams already responding elsewhere. Every current team member receives an inbox entry and, when Firebase and their signed-in phone are configured, a push notification. Reassigning a case creates fresh notifications; removed members are excluded from future delivery.
