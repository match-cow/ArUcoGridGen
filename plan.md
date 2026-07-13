# ArUcoGridGen v2 Comprehensive Rewrite

## Summary

- Replace the 1,700-line Streamlit `app.py` with a React/TypeScript frontend and a typed FastAPI backend.
- Target robotics and computer-vision users working primarily in desktop Chromium.
- Preserve the three board workflows—ArUco Grid, ChArUco, and Checkerboard—plus live preview, printable PDF, JSON export, annotations, print compensation, and coordinate transforms.
- Introduce a clean v2 contract; legacy JSON and pixel-level output compatibility are intentionally out of scope.
- Retain the MATCH logo, lime accent, stateless single-container deployment, GHCR publishing, and public port `8501`.
- Remove Streamlit, `pdf2image`, Poppler, duplicated overlay rendering, and the current failure mode where an invalid configuration can leave an old PDF available for download.

## Architecture and Behavior

- Use Python 3.12, FastAPI/Pydantic, OpenCV, NumPy/SciPy, Pillow, and ReportLab. Use React, TypeScript, Vite, React Hook Form, generated OpenAPI types, Vitest, and Testing Library on the frontend.
- Organize the backend around one immutable, millimetre-based scene model:
  - Validate and normalize the request.
  - Calculate page, target, annotation, feature-point, and pose geometry once.
  - Render that scene directly to a capped 1,600-pixel PNG preview, a one-page vector PDF, and deterministic JSON.
  - Decode ArUco modules into vector rectangles; derive ChArUco placement from OpenCV board metadata; render checkerboards as vector squares.
- Apply X/Y print compensation about the board center while leaving the physical page size unchanged. All board-attached geometry and exported feature coordinates use the compensated dimensions.
- Reserve a 2 mm page-edge clearance and calculate safe annotation areas. Marker IDs, scale ruler, parameters, and frame legend must never cover calibration targets; return a specific fit error when safe placement is impossible.
- Define the board frame at the compensated outer board's top-left corner: `+X` right, `+Y` down, and `+Z` into the page. Pose rotation is `Rz(yaw) · Ry(pitch) · Rx(roll)`; exported quaternions use XYZW order and transform translations use metres.
- Build a desktop-first MATCH-branded workspace:
  - Header with branding and application identity.
  - Fixed configuration pane with board selector and Page, Board, Annotations, and Coordinate Frame sections.
  - Sticky paper-proportional preview pane with loading, current, stale, validation-error, and service-error states.
  - Inline field errors plus an accessible error summary; the last valid preview may remain visible but must be labelled stale and downloads disabled.
  - A 300 ms debounced preview request with `AbortController`; ignore late responses and enable exports only when the successful preview hash matches current settings.
  - Preserve separate board-specific drafts when switching board types while sharing page and annotation settings.
- Use a bounded in-memory cache keyed by a canonical SHA-256 configuration hash. Store no user data and require no database, authentication, CORS exceptions, or background workers.
- Serve the built SPA and API from one Uvicorn process. Use a multi-stage Node/Python image, run as a non-root user, exclude browsers and test dependencies from production, and health-check the API.

## Public v2 Interfaces

| Method and path | Contract |
|---|---|
| `GET /api/v2/capabilities` | Supported paper sizes, dictionary allowlists/capacities, limits, defaults, and board-type metadata |
| `POST /api/v2/preview` | Strict v2 request to `image/png`; returns configuration hash headers |
| `POST /api/v2/exports/pdf` | Same request to an attachment PDF with exact physical page dimensions |
| `POST /api/v2/exports/config` | Same request to a deterministic v2 JSON manifest |
| `GET /api/v2/health` | Lightweight readiness response used by Docker and CI |

- Model requests as a discriminated union containing `schema_version`, `page`, board-specific `board`, `print_compensation`, `annotations`, and `coordinate_frame`.
- Board variants:
  - ArUco: dictionary, rows, columns, marker size, separation, and ArUco-only ID-label settings.
  - ChArUco: dictionary, square counts, square size, and marker size.
  - Checkerboard: square counts, square size, and border size.
- Retain current paper sizes and dictionary catalogs. Enforce finite values, grid limits of 100, physical dimensions up to 200 mm, checkerboard border up to 100 mm, dictionary capacity, `marker_size < square_size` for ChArUco, page fit, and annotation fit. Reject unknown and extra fields.
- Use the currently visible defaults: A4 portrait; ArUco `DICT_5X5_100`, 5×7, 30 mm markers, 10 mm separation; ChArUco `DICT_5X5_250`, 5×7, 30/18 mm; Checkerboard 5×8, 30 mm squares, 20 mm border; ruler and parameters enabled; frame disabled; compensation 100%.
- Export JSON with the normalized request, page and target bounds, final feature coordinates, marker/corner IDs, page placement, frame convention, and optional board-to-base matrix/quaternion. Omit timestamps so identical inputs produce identical JSON.
- Return structured `422` errors with stable codes, field paths, messages, and required-versus-available dimensions. Unexpected failures return a generic request ID while logging technical detail server-side.
- Generate checked-in TypeScript API types from FastAPI's OpenAPI document and make CI fail if regeneration produces a diff.

## Implementation and Playwright Iteration

1. **Bootstrap and characterization**
   - Record the existing functional settings/defaults as fixtures, scaffold backend/frontend/test packages, pin Python and npm lockfiles, and configure development proxying.
   - Add `@playwright/test`, install Chromium, and configure Playwright to start the real combined application on port `8501`.
2. **Core and first vertical slice**
   - Implement schemas, layout primitives, transforms, error model, ArUco rendering, capabilities, and preview API.
   - Build the branded application shell and complete the default ArUco workflow end to end.
3. **Remaining boards**
   - Add detector-verified ChArUco and Checkerboard scene generation, board-specific forms, relational validation, and per-board draft preservation.
4. **Annotations and exports**
   - Add safe annotation packing, print compensation, coordinate-frame controls, vector PDF generation, deterministic JSON, downloads, stale-state handling, and network recovery.
5. **Production cutover**
   - Run the production build through Playwright, replace the Streamlit entry point, remove obsolete dependencies/configuration, update Docker/Compose and documentation, and retain the existing GHCR tagging/signing flow.

After every vertical slice:

- Run targeted Python and frontend unit/type/lint checks.
- Start the real application and use Playwright interactively to inspect its accessibility snapshot, operate the controls, capture screenshots, and inspect console and network activity.
- Add or extend the corresponding scripted Playwright test, fix all observed issues, and proceed only when the targeted test passes without console errors or failed requests.
- Review visual diffs before updating snapshots; use explicit status/hash waits rather than sleeps.

## Test Plan, Acceptance Criteria, and Assumptions

- Backend tests cover every schema branch, NaN/infinity, dictionary capacity, ChArUco relationships, page/annotation fit, compensation, known pose matrices/quaternions, feature coordinates, and deterministic hashes.
- Renderer tests verify PDF media boxes and physical geometry, rasterize representative PDFs in test code, and use OpenCV detectors to confirm expected ArUco IDs, ChArUco corners, and checkerboard corners.
- API tests verify content types, filenames, structured errors, health, identical geometry across PNG/PDF/JSON, and safe handling of malformed requests.
- Frontend tests cover conditional controls, shared versus board-specific state, debounce/cancellation, field-error mapping, stale previews, and export enablement.
- Desktop-Chromium Playwright coverage includes initial load, all three board types, orientation and annotation changes, coordinate poses, invalid-fit recovery, stale-response races, PDF/JSON downloads, keyboard navigation, and visual snapshots at 1440×1000 and 1024×768. Add `axe-core` checks with no serious or critical violations.
- CI gates linting, type checks, unit/integration coverage, Chromium Playwright tests, production-image smoke testing, and only then image publishing.
- Completion requires detector-valid outputs for representative configurations, exact PDF page dimensions, agreement among all three render targets, no annotation/target intersections, no browser console errors, and successful startup through the existing port-8501 Docker workflow.
- Explicitly out of scope: legacy v1 compatibility, configuration import, presets/reset workflows, URL persistence, authentication, saved projects, batch generation, CLI support, new board families, mobile-specific acceptance, and Firefox/WebKit testing.
- Remove the ineffective ChArUco “show IDs” behavior; marker-ID labels remain ArUco-grid-only.
- Reuse the existing logo/favicon and brand colors. The current untracked `uv.lock` is user-owned: reconcile it during dependency changes rather than deleting it, then commit the resulting Python and npm lockfiles.
