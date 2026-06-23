# Gaffer's Clipboard — Project Context for Claude Code

## What This Project Is

Gaffer's Clipboard is a desktop companion app for EA FC / FIFA Career Mode. It uses a custom OpenCV KNN-based OCR engine to extract match and player statistics directly from game screenshots, storing them in a strictly validated, JSON-backed local database. The end goal (Phase 9) is a distributable standalone `.exe` for non-technical gamers.

**Current status: Phase 8 — Analytics Engine & Squad Hub.** The core data capture, validation, persistence, and UI are complete. The focus now is building analytics features on top of the accumulated data.

---

## Architecture: Three-Controller MVC with Interface-Driven Design

This is a **strict MVC application** built around three controllers, each owning a distinct domain. The separation is non-negotiable and must be maintained in all new code.

```
Views (src/views/)
    ↓ only interact with
App (src/app.py)                    ← sole view interactor, sole orchestrator
    ├─ delegates persistence to
    │   DataManager (src/data_manager.py)
    │       └─ delegates to Data Services (src/services/data/)
    │              CareerService · JSONService · MatchService · PlayerService
    ├─ delegates analytics to
    │   AnalyticsEngine (src/analytics_engine.py)
    │       └─ delegates to Analytics Services (src/services/analytics/)
    │              MatchRatingsService · [future services]
    └─ delegates app logic to App Services (src/services/app/)
           BufferService · CareerService · MatchService
           OCRService · PlayerService · ScreenshotService
```

### Controller Ownership Rules

**`src/app.py`** is the sole orchestrator and the only class views may call.
- Owns a `DataManager` instance (`self._data_manager`) — never accessed directly by services or views
- Owns an `AnalyticsEngine` instance (`self._analytics_engine`) — never accessed directly by services or views
- Owns six App Services that handle business logic; many `app.py` public methods are intentional thin wrappers around these
- `App.PROJECT_ROOT = Path(__file__).parent.parent` is the canonical project root

**`src/data_manager.py`** is the sole disk I/O layer.
- All JSON reads and writes go through DataManager — no exceptions
- Delegates its internals to four Data Services in `src/services/data/`
- Data Services may only be called by DataManager, not by App Services or app.py directly

**`src/analytics_engine.py`** is the sole analytics orchestrator.
- Lazy-loads config from `config/performance_weights.json` and `config/performance_means_stds.json` on first use
- Delegates to Analytics Services in `src/services/analytics/`
- Analytics Services may only be called by AnalyticsEngine, not by app.py or DataManager directly
- Currently has one service: `MatchRatingsService`. New analytics features add new services here.

### The Five Golden Rules

1. **Views only call `app.py`.** `src/views/` contains pure CustomTkinter UI. No business logic, no data manipulation, no service calls of any kind. Views receive data from the controller and emit user actions to it. Preliminary UI-layer validation (e.g. disabling a button when a field is empty) is acceptable.

2. **Only DataManager reads and writes disk.** No service, view, utility, or controller may open a file directly except DataManager. If new analytics features need to persist data, that goes through DataManager.

3. **Only AnalyticsEngine calls Analytics Services.** `app.py` calls `analytics_engine.calculate_match_rating()` etc. It never imports or instantiates `MatchRatingsService` directly.

4. **Data Services are internal to DataManager.** App Services and app.py never call `src/services/data/` directly.

5. **Contracts define boundaries.** `src/contracts/` contains Protocol and TypedDict definitions for all cross-layer interactions. When adding a new payload shape between layers, it goes in contracts, not inline.

---

## Public Interfaces

### `App` (`src/app.py`) — what views call

**UI navigation:**
- `show_frame(page_class)` — navigate to a registered frame
- `get_frame_class(name)` — look up a frame class by string name
- `get_sidebar_collapse_state(sidebar_id)` / `set_sidebar_collapse_state(sidebar_id, collapsed)`
- `has_unsaved_work()` → `bool`
- `clear_session_buffers()`

**Career management:**
- `get_all_career_names()` → `list[str]`
- `save_new_career(...)` — create and persist a new career
- `activate_career(career_name)` — load an existing career into session
- `get_current_career_details()` → `CareerMetadata | None`
- `update_career_metadata(updates: CareerMetadataUpdate)`
- `add_competition(competition)` / `remove_competition(competition)`

**Player management:**
- `get_all_player_names(...)` → `list[str]`
- `get_player_bio(name)` → `PlayerBioDict | None`
- `process_player_attributes(...)` — OCR + prefill attributes
- `buffer_player_attributes(...)` — stage attributes for save
- `save_player()` — persist buffered player
- `save_financial_data(...)` — persist financial snapshot
- `add_injury_record(...)` — persist injury record
- `loan_out_player(player_name)` / `return_loan_player(player_name)` / `sell_player(player_name, in_game_date)`

**Match workflow:**
- `process_match_stats()` — OCR the match overview screen
- `buffer_match_overview(overview_data)` — stage match overview
- `process_player_stats(is_goalkeeper)` — OCR a player performance screen
- `buffer_player_performance(...)` — stage a player performance
- `get_buffered_player_performances()` → buffer contents
- `remove_player_from_buffer(player_name)`
- `get_live_match_rating(...)` → `float | None` — calculate rating without saving
- `get_match_review_context()` — retrieve staged match for review
- `submit_match_corrections(...)` — apply user edits from review frame
- `cancel_match_review()`
- `save_buffered_match(force_save)` — validate and persist the staged match
- `get_latest_match_in_game_date()` → `datetime | None`

### `DataManager` (`src/data_manager.py`) — what app.py calls

**Career:**
- `create_new_career(...)` → `CareerCreationArtifacts`
- `get_all_career_names()` → `list[str]`
- `get_career_details(career_name)` → `CareerMetadata | None`
- `load_career(career_name)` → `bool`
- `get_current_career_metadata()` → `CareerMetadata | None`
- `update_career_metadata(updates)` / `add_competition(...)` / `remove_competition(...)`

**Players:**
- `find_player_by_name(name)` → `Player | None`
- `add_or_update_player(...)` — upsert a player record
- `add_financial_data(...)` / `add_injury_record(...)`
- `sell_player(...)` / `loan_out_player(...)` / `return_loan_player(...)`
- `refresh_players()` — reload players from disk into memory cache

**Matches:**
- `add_match(...)` — validate and persist a complete match record
- `get_latest_match_in_game_date()` → `datetime | None`
- `refresh_matches()` — reload matches from disk into memory cache

### `AnalyticsEngine` (`src/analytics_engine.py`) — what app.py calls

- `calculate_match_rating(performance, match_overview, half_length, team_name)` → `float | None`
  - Routes to `MatchRatingsService.calculate_gk_rating()` or `.calculate_outfield_rating()` based on `performance_type`
  - Lazy-loads config on first call; caches the service instance
  - Returns `None` if config is unavailable or player minutes are insufficient

---

## Tech Stack

**Runtime (ship these):**
- Python 3.13+
- `customtkinter` — UI framework. Never suggest PyQt, standard Tkinter, or web-based alternatives.
- `opencv-python` (cv2) — OCR and image processing
- `pillow`, `pyautogui` — screenshot capture and image handling
- `numpy` — math and array operations
- `pydantic` v2 — strict data validation everywhere

**Package manager: `uv`.** Never use `pip` directly. All installs go through `uv add` (runtime) or `uv add --dev` (dev-only). Run scripts with `uv run`.

**Dev-only (never import in production `src/` code):**
- `jupyter`, `pandas`, `matplotlib`, `seaborn`, `scikit-learn`, `scipy`, `statsmodels` — data science and notebooks, used in `workshop/` only
- `pytest`, `pytest-cov`, `pytest-mock` — testing
- `ruff` — linting and formatting
- `ty` — static type analysis

**Critical constraint for Phase 8/9:** The analytics engine must stay lightweight. Use `numpy` and pure Python math in `src/`. Heavy libraries (`scikit-learn`, `pandas`) are dev-only and must never be imported in production code — the final executable must stay small. If an algorithm needs heavy computation, do it offline in `workshop/` notebooks and store the output (e.g. trained weights as JSON).

---

## Code Quality Standards

All code must pass `ruff` and `ty` before merging. Run them with:
```bash
uv run ruff check .
uv run ruff format .
uv run ty check
```

### Ruff rules enforced
The full rule set is in `pyproject.toml`. Key families:
- **D** — PEP 257 docstrings required on all public functions, classes, and modules
- **ANN** — type annotations required on all function signatures
- **N** — PEP 8 naming (snake_case functions/variables, PascalCase classes)
- **T20** — no `print()` statements in `src/` — use `logging` instead
- **B** — no bug-prone patterns (mutable defaults, etc.)
- **S** — security checks
- **C90** — cyclomatic complexity capped at 10

### Import style
Always use absolute `src.*` imports:
```python
# Correct
from src.schemas import Player, Match
from src.contracts.backend import OutfieldPerformancePayload

# Wrong
from schemas import Player
from ..schemas import Player
```

The `workshop/` directory is excluded from ruff and ty — notebooks can be messy.

### Type checking
`ty` analyses `src/` strictly. `cv2`, `customtkinter`, `pyautogui`, and `PIL` are treated as `Any` due to weak stubs — don't fight this, it's configured intentionally in `pyproject.toml`.

---

## Data Layer: Pydantic Schemas

**`src/schemas.py` is the single source of truth for all persistent data.**

Key models:
- `Player` — player identity, positions, attribute/financial/injury history (polymorphic via discriminated union)
- `Match` — fixture context, scoreline, team stats, player performances (polymorphic)
- `OutfieldPlayerPerformance` / `GoalkeeperPerformance` — discriminated by `performance_type`
- `MatchStats` — team-level match statistics
- `CareerMetadata` / `CareerDetail` — career save configuration

Key validation rules already enforced:
- `distance_sprinted` cannot exceed `distance_covered`
- `shots_on_target` cannot exceed `shots_against`; `saves` cannot exceed `shots_on_target`
- `tackles_won` cannot exceed `tackles`
- Goals cannot exceed shots (enforced in app service layer)
- Dates accept both UI format (`dd/mm/yy`, `dd/mm/yyyy`) and ISO format for JSON round-tripping
- `match_rating: float | None` stores the custom algorithm output (0.0–10.0), not EA's native rating

**The `match_rating` field in persisted data is the output of the custom analytics algorithm, not EA's built-in system.** Never conflate these.

### Contracts (`src/contracts/`)
- `backend.py` — cross-layer TypedDicts and type aliases for payloads, buffers, and generic types
- `coordinates.py` — OCR region bounds (normalised and pixel variants)
- `ocr.py` — OCR preprocessing and debug payload types
- `ui.py` — UI-layer Protocol definitions for controller/view interactions

---

## Analytics Engine (Phase 8 Focus)

**Entry point:** `src/analytics_engine.py` — `AnalyticsEngine` class
**Services:** `src/services/analytics/` — currently `MatchRatingsService` only

### Pattern for adding new analytics features

Every new analytics capability follows the same pattern:
1. Create a new service class in `src/services/analytics/` (e.g. `form_score_service.py`)
2. Add it to `AnalyticsEngine` with lazy initialisation matching the existing `_get_match_rating_service()` pattern
3. Expose a public method on `AnalyticsEngine` for `app.py` to call
4. `app.py` calls the engine method — never the service directly

### Match ratings algorithm

`src/services/analytics/match_ratings_service.py` (~2000 lines)
- Implements a 0.0–10.0 player rating system for EA FC Career Mode
- Fully documented in `docs/Quantitative Design of the Gaffers Clipboard Rating Algorithm.md` (and PDF)
- **Offline-weight, online-inference pattern:** heavy computation (PCA, MCD estimator) was done once in `workshop/ratings_creation/` notebooks; the live engine uses only numpy and pure Python
- Weight vectors loaded from `config/performance_weights.json`
- Historical means/stds loaded from `config/performance_means_stds.json`
- `match_rating` stored on `OutfieldPlayerPerformance` and `GoalkeeperPerformance` is this algorithm's output, not EA's native rating

### Workshop notebooks (`workshop/ratings_creation/`)
Offline calibration only — excluded from ruff and ty:
- `*_weights_calculations.ipynb` — PCA + MCD weight derivation per position
- `*_ratings_calculations.ipynb` — ratings testing per position
- `ratings_testing.ipynb` — stress tests and real Valencia CF match validation

### Upcoming Phase 8 features (from roadmap)
All must follow the offline-weight / online-inference pattern:
- **Form Scores** — EMA-based player form tracking
- **Monte-Carlo Season Predictor** — numpy probability distributions
- **Win-Condition Extraction** — Random Forest feature importances (train offline, load weights at runtime)
- **Red Zone Injury Flags** — Logistic Regression (train offline, load weights at runtime)
- **Tactical Fingerprinting** — K-Means clustering (train offline, store centroids)

The constraint: no scikit-learn, pandas, or scipy in `src/`. These are trained in `workshop/` and their outputs (weights, centroids, coefficients) are stored as JSON in `config/` for the live engine to use.

---

## Testing

```bash
uv run pytest --cov=src --cov-report=html
```

Tests live in `tests/`. Coverage threshold is 60% — do not let it drop below this.

**Coverage exclusions** (configured in `pyproject.toml`):
- `src/views/*` — UI code not under test
- `src/app.py`, `src/__main__.py` — entry points
- `src/theme.py`, `src/contracts/ui.py`

**Test fixtures:**
- `tests/fixtures/screenshots/` — real screenshot PNGs for OCR regression tests
- `tests/fixtures/testing_data/` — a `valencia_cf_1` career save with real match, player, and metadata JSON

**Existing test files:** buffer service, competition name normalisation, contract name uniqueness, coordinates, data player service, integration flow, and full OCR tests.

Use `pytest-mock` for mocking service dependencies. Never mock `DataManager` in integration tests — use the fixture career data instead.

---

## Project Structure (Key Paths)

```
src/
├── contracts/          # Protocol/TypedDict definitions — layer boundaries
│   ├── backend.py      # Cross-layer payload types and type aliases
│   ├── coordinates.py  # OCR region bound types
│   ├── ocr.py          # OCR preprocessing types
│   └── ui.py           # UI-layer Protocol definitions
├── services/
│   ├── analytics/      # Analytics engine (Phase 8)
│   │   └── match_ratings_service.py
│   ├── app/            # Business logic services (buffer, career, match, OCR, player, screenshot)
│   └── data/           # Data persistence services (career, json, match, player)
├── views/              # Pure CustomTkinter UI — no business logic
│   ├── widgets/        # Reusable UI components
│   ├── base_view_frame.py  # Base class for all view frames
│   └── mixins.py       # Shared view behaviour mixins
├── app.py              # Main controller — sole orchestrator, sole view interactor
├── analytics_engine.py # Analytics entry point
├── data_manager.py     # Sole disk I/O layer
├── schemas.py          # Single source of truth for all data models
├── ocr.py              # OpenCV OCR pipeline
├── exceptions.py       # Custom exception hierarchy
├── logging_config.py   # Logging setup
├── theme.py            # CustomTkinter theming
└── utils.py            # Shared utilities

docs/                   # Whitepapers, roadmap, mockups (Obsidian vault)
workshop/               # Dev-only notebooks and scratch files (excluded from lint/type)
config/                 # Runtime config JSON (weights, means/stds, coordinates)
scripts/                # One-off migration and utility scripts
tests/                  # Pytest suite
model/                  # KNN OCR model training scripts and artefacts
```

---

## Common Pitfalls — Don't Do These

- **Don't import scikit-learn, pandas, scipy, or statsmodels in `src/`.** Dev-only. They bloat the Phase 9 executable.
- **Don't write to disk anywhere except DataManager.** No service, view, or utility opens a file directly.
- **Don't call Analytics Services directly from `app.py` or anywhere outside `AnalyticsEngine`.** `app.py` calls `analytics_engine.calculate_match_rating()` — never `MatchRatingsService` directly.
- **Don't call Data Services directly from `app.py` or App Services.** All data access goes through `DataManager`'s public methods.
- **Don't put logic in views.** If you're writing a conditional or transformation in a view file, it belongs in a service.
- **Don't use `print()`.** Use `logging.getLogger(__name__)` and the appropriate log level.
- **Don't use `pip install`.** Use `uv add` (runtime) or `uv add --dev` (dev).
- **Don't create new TypedDicts or Protocol definitions outside `src/contracts/`.** All cross-layer shapes live there.
- **Don't treat `match_rating` in persisted JSON as EA's native rating.** It's the custom algorithm output stored after `AnalyticsEngine.calculate_match_rating()` runs.
- **Don't use relative imports.** Always `from src.x import y`.
- **Don't add heavy computation to the live analytics path.** Pre-compute in `workshop/` notebooks, store outputs as JSON in `config/`, load at runtime.
- **Don't instantiate DataManager, AnalyticsEngine, or App Services in views.** They are owned by `app.py`.

---

## Running the App

```bash
uv run gaffer
```