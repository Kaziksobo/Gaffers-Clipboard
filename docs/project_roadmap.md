# Project Roadmap: The Gaffer's Clipboard

This document outlines the phased development plan for the FIFA Career Mode stats extractor and analyser.

---

## Phase 1: Core OCR Engine (Proof of Concept) ✔️

**Status: Complete**

The primary goal of this phase was to prove that we can reliably identify a single digit from a static screenshot. This has been successfully achieved using an OpenCV template matching algorithm.

### Key Achievements:
- [x] Isolated a single digit from a screenshot.
- [x] Pre-processed the image into a clean, binary format.
- [x] Used `cv2.matchTemplate` with a set of template images to correctly identify the digit.

---

## Phase 2: The Application Skeleton ✔️

**Status: Complete**

The goal of this phase was to build the basic application framework around the proven OCR logic. This involves creating the project structure and a simple user interface. This has been successfully completed, using `Tkinter` to create the basic GUI, and integrating the OCR logic to read a digit from a static image when a button is pressed.

### Key Achievements:
- [x] A working `Tkinter` window with a button and label.
- [x] Integrated OCR logic to read a digit from a static image.
- [x] The label updates correctly when the button is pressed.
- [x] GitHub repository and file structure created.
- [x] Documentation for project planning written out.

---

## Phase 3: GUI development ✔️

**Status: Complete**

The goal of this phase was to build out the GUI to guide the user through capturing all the applications screens, capturing screenshots when needed, that can then be analysed with OCR. This has been successfully completed, transitioning to `customtkinter`, creating all frames needed for the OCR features, and including buttons to transition between frames and take screenshots.

### Key Achievements:
- [x] The 5 main frames that make up the main application are created and working.
- [x] Stats capture screens have editable text fields with placeholder values.
- [x] Buttons to switch between frames work, allowing the user to navigate thru the application.

---
## Phase 4: Full Data Extraction & Screen Capture ✔️

**Status: Complete**

The goal of this phase is to expand the application to handle all the required stats from every screen and ensure the data is accurate before saving.

### To-Do List:
- [x] **Implement Screenshot Workflow**
	- [x] integrate `pyautogui` and `time` into `gui.py`.
	- [x] Create generalised controller methods for taking screenshots after a delay
	- [x] Connect the "done" buttons in all appropriate frames.
- [x] **Map All Coordinates:**
	- [x] Create a new configuration file for storing stat coordinates.
    - [x] For each stats screen (Team, Player, etc.), store the coordinates of all required stats in the config file.
- [x] **Multi-digit OCR**
	- [x] transition from pure template matching to a contouring based method to split multi-digit numbers into their separate digits
	- [x] Ensure the algorithm works robustly on all necessary digits, including the coloured digits on the player attribute screens
- [x] **Integrate OCR with Screenshots**
	- [x] Create a main processing function in the controller.
	- [x] This function should:
		- [x] Load the coordinates from the config file.
		- [x] For each stat, call the `ocr.get_stat_roi()` function with the correct coordinates to extract the digit region from the screenshot.
		- [x] Pass the extracted RIO to `ocr.recognise_digit()` to get the value.
		- [x] Store all recognised stats in a temporary dictionary.
- [x] **Connect OCR Results to the GUI**
	- [x] Pass the dictionary of recognized stats from the controller to the appropriate view (`MatchStatsFrame` or `PlayerStatsFrame`).
	- [x] In the view, create a method to update the `StringVar` for each stat entry box with the values from the dictionary. This will auto-fill the UI.

**End Goal for Phase 4:** The user can click through the entire "Add Match" workflow. The application successfully takes screenshots, runs OCR on all defined coordinates, and populates the `MatchStatsFrame` and `PlayerStatsFrame` with the recognized (or placeholder) data, ready for user validation.

---

## Phase 5: Data Persistence ✔️

**Status: Complete**

The goal of this phase is to finish end-to-end capture: Complete match/player performance saving, and schema-aligned output files.

### To-Do List:
- [x] **Player Performance Capture Flow**
	- [x] Add player selection (dropdown) in `PlayerStatsFrame`, populated from saved players with IDs.
	- [x] Wire OCR for `player_performance` ROIs to prefill per-player stats; allow manual edits before saving.
	- [x] Buffer multiple player performances and associate them with `player_id` on save.
- [x] **Match Save Pipeline**
	- [x] Gather validated match overview + player performances and call `DataManager.add_match` to write `matches.json`.
	- [x] Align field names between UI and `coordinates.json` (e.g., `fouls_comitted` vs. `fouls_committed`, `def_aware` → `defensive_awareness`).
	- [x] Structure saved data to match the planned template (home/away stats, linked player performances).

**End Goal for Phase 5:** The user can capture match overview and player performances, review/edit them, and save a complete match record (with linked player IDs) to JSON with reliable OCR

---
## Phase 6: Multi-Career Support & Data Architecture ✔️

**Status: Complete**

The goal of this phase is to refactor the application's architecture to support "Multi-Tenancy." This allows the user to manage multiple simultaneous FIFA careers (e.g., one for "Arsenal", one for "Wrexham") without mixing up their stats and player records.

### To-Do List:
- [x] **Implement career gate**
	- [x] Create a new `CareerSelectFrame` to be the first screen shown on application launch.
	- [x] Build UI to list existing careers found in the `data/careers/` directory.
	- [x] Add a "Create New Career" form (Career Name, Team Name, Manager Name).
- [x] **Refactor Data Management Architecture**
	- [x] Modify `App` class to delay `DataManager` initialization until a career is selected.
	- [x] Update `DataManager` to accept a dynamic `career_path` argument instead of using a hardcoded global path.
	- [x] Ensure all subsequent reads/writes (Players, Matches) are scoped to `data/careers/<career_id>/`.
- [x] **Career Metadata & Persistence**
	- [x] Define a `meta.json` schema for each career folder (storing career-specific settings like difficulty, match length, or current season).
	- [x] Implement directory creation logic: when a new career is added, generate the folder structure and empty `players.json` and `matches.json` files automatically.
- [x] **Session Context**
	- [x] Update the main GUI controller to hold the "Current Career Context" and display the active career name in the sidebar or title bar.

**End Goal for Phase 6:** When the user launches the app, they are prompted to select or create a career. Once selected, all subsequent data entry, OCR lookups, and file saving occur strictly within that specific career's folder, ensuring complete data isolation between different save files.

---
## Phase 7: Refactoring, Usability & Robustness 

**Status: Complete**

The goal of this phase is to "harden" the application by improving stability, formalizing architecture boundaries, and introducing a modern engineering baseline (tooling, typing, and tests) before diving into advanced analytics.

### To-Do List: 
- [x] **Codebase Refactoring**
	- [x] Rename `gui.py` to `app.py` to better reflect its role as the main application controller.
	- [x] Clean up screenshot storage logic to automatically delete old files (keep only the last X screenshots) to save disk space. 
	- [x] Make data manager save keys in snake case
	- [x] Look at fixing OCR digit ordering for cases like 0.4 being returned as 4.0.
	- [x] Implement `pydantic` across the data manager for more rigorous data structuring
		- [x] Possibly implement across the rest of the application for documentation purposes?
	- [x] Refactor application orchestration to use service-layer abstractions (`src/services/app` and `src/services/data`) so business logic is less tightly coupled to UI and persistence details.
- [x] **Synchronisation**
	- [x] Transition from using `time.sleep` for the screenshot delay to a different method that doesn't freeze the application.
- [x] **Dependency & Environment Management**
	- [x] Standardize project setup and dependency management with `uv` (runtime + dev groups in `pyproject.toml`, lockfile-based installs via `uv.lock`).
	- [x] Move away from legacy `requirements.txt`/ad-hoc `pip` workflows to reproducible, project-level commands.
- [x] **Linting, Types & Quality Gates**
	- [x] Configure `ruff` as the primary linting and style gate (imports, docstrings, complexity, naming, annotation coverage, and correctness/security rule families).
	- [x] Configure `ty` for strict static type analysis over `src/`, with explicit rule severities and managed third-party typing exceptions.
	- [x] Tighten typing conventions around contracts/service boundaries and enforce cleaner absolute import organization (`src.*`).
- [x] **Testing Infrastructure**
	- [x] Expand the `pytest` suite to cover service behavior, data contracts, integration flows, and OCR regression paths.
	- [x] Add `pytest-cov` + coverage thresholds for core logic to prevent silent quality regressions.
- [x] **Implement Logging**
	- [x] Replace all `print()` statements with the Python `logging` module to generate well-formatted, timestamped log files for easier debugging.
- [x] **Error Handling & Feedback** 
	- [x] Implement robust `try/except` blocks across the entire program (especially OCR and file I/O).
	- [x] Use `tkinter.messagebox` to display friendly error popups to the user instead of silent console failures.
	- [x] Add extra warning popups to validate inputted stats before they are submitted
- [x] **Resolution Independence** 
	- [x] Move from hardcoded pixel coordinates to relative scale factors in `coordinates.json`.
	- [x] Implement logic to detect screen resolution and scale OCR regions dynamically (supporting 1080p, 4k, etc.).
- [x] **Feature Expansions**
	- [x] **Financial Data:** Create a new, dedicated frame for inputting player financial data, and saving it with the player attributes.
	- [x] **Injuries:** Create a new frame for inputting player injury data, allowing the user to attach it to a player in the library.
	- [x] **Separate Injuries and Financial Data:** Keep these two separate from the player attributes, so they can be directly accessed from the player library frame.
	- [x] **Sales and Loans:** Add functionality to mark players as sold or loaned out
	- [x] **GK Performance Frame:** Create a dedicated UI for entering/OCR-ing Goalkeeper match performance stats.
	- [x] **Optional Player Stats:** Add a toggle or logic to allow saving a match result *without* needing to enter individual player performances.
	- [x] **Position Capture (Match Performance):** Add a dedicated positions-played input for performance frames with comma-separated multi-position support, strict validation against allowed position codes, and auto-fill from selected player bio when available..
	- [x] **In-Game date**: Add in-game date fields across the app in all screens that need it.
	- [x] **Update Player**: On the screens to add or update player attributes, next to the entry box to enter the player name, add a player dropdown to select from already saved players to update them easier.
	- [x] **Performance Sidebar:** Add a scrollable, collapsible staging sidebar to `PlayerStatsFrame` and `GKStatsFrame` that shows buffered players (name + positions played), supports per-row remove actions, and keeps collapse state synchronized while switching between those frames.
	- [x] **Theme & UX Flourishes:** Integrate the application's defined accent colour to improve visual feedback. Implement active focus borders for `CTkEntry` widgets (highlighting the box currently being typed in), update button hover states, and explore any other theming changes.
- [x] **User Experience & Documentation**
	- [x] Add an "Instructions" or "Help" tab/modal within the app explaining how to capture data. 
	- [x] Thoroughly review all docstrings, annotations, and comments for PEP compliance and readability.
	- [x] Refresh `README.md` so setup and daily workflows match the current stack (`uv`, `ruff`, `ty`, and `pytest`).

**End Goal for Phase 7:** The application is stable, resolution-independent, self-cleaning, and user-friendly, with a service-oriented architecture and an enforceable engineering baseline (managed dependencies, strict lint/type checks, and automated tests).

----
## Phase 8: Analytics Engine & Squad Hub

**Status: In progress**

The goal of this phase is to transform the application from a raw data-entry tool into a living "Backroom Staff." This involves building a modular analytics engine using pure math and NumPy at runtime (any model training happens offline in `workshop/` with Scikit-Learn, and only the resulting weights ship as JSON config) to generate actionable insights, and creating immersive UI dashboards to visualize this data.

### To-Do List: 
- [ ] **Core Analytics Engine (`src/services/analytics/`):**
	- [ ] Implement **Custom Match Ratings**: Use weighted positional heuristics to calculate true player performances, bypassing the game's native rating system. *(largely complete — final tweaks and documentation remaining)*
	- [ ] Implement **Form Scores**: A descriptive recent-form indicator. An EMA of match ratings (alpha ~0.3, seeded with the position prior) is compared against a shrunk baseline and converted into a colour band using noise-aware thresholds (neutral below |z| of 1, soft tint from 1 to 2, strong colour from 2). Descriptive only: backtests show recent form does not predict future ratings, so it must not feed the Lineup Optimizer or any predictive model.
		- [ ] Return the full EMA series (not just the latest value) so the Deep-Dive charts can reuse it; show the series from 3 rated appearances and colours from ~5; alpha, thresholds, `sigma_within` and the shrinkage constants are constants at the top of `form_scores_service.py` (no JSON config file for this service), fitted offline from the final ratings and hard-coded.
		- [ ] Expose the shrunk baseline ("reliable rating"): (n x player mean + k x position mean) / (n + k), k ~6, for ranking players (top performers, optimiser) instead of form.
- [ ] **Predictive & Tactical ML (trained offline with Scikit-Learn, numpy at runtime):**
	- [ ] **Win-Condition Extraction** *(deferred until there is more data, particularly from the lower-win-rate Ipswich career)*: Fit a ridge regression offline on goal difference using per-minute team-stat differentials (controllable stats only; xG, shots and saves excluded). Ship signed, standardised coefficients as JSON, and cross-check against Random Forest permutation importance offline.
	- [ ] **Red Zone Injury Flags** *(last in the order)*: Rule-based workload heuristic (rolling minutes and sprint load against each player's own baseline). Logistic Regression is shelved until there are enough labelled injuries (~200–500 needed, ~30–60 available).
	- [ ] **Tactical Fingerprinting**: Use K-Means clustering to group historical matches/opponents by playstyle (e.g., High-Press, Possession). Features are normalised per minute (shared with the Win-Condition feature extraction); centroids ship with their scaler means/stds.
	- [ ] **Expected Rating** *(shelved until after Tactical Fingerprinting and the other Phase 8 analytics; plan in `docs/expected_rating_plan.md`)*: Predict a player's rating for the upcoming match, displayed as a range with its components rather than a single number.
		- [ ] Aim for the most comprehensive candidate feature set drawn from **existing data only** (no new capture such as fitness or morale screenshots): shrunk player baseline, opponent effect, opponent archetype x position group, attributes and age, workload, season stage, match context; every feature must earn its place in walk-forward backtests.
		- [ ] Model choice stays open: a hierarchical (mixed-effects) linear model first, gradient-boosted trees as a challenger. Training libraries are workshop-only; the shipped model is exported to JSON and evaluated with numpy.
		- [ ] Findings so far (refit after any ratings change): the shrunk player mean (k ~6, ~8% error reduction vs the position average) and an opponent effect (r ~ +0.15) help; recent form, rest days, recent minutes, home/away, competition and return from injury showed no detectable effect. Rating variance is ~80% match-to-match noise, so expect modest gains.
- [ ] **Additional Analytics:**
	- [ ] **Luck Gauge & Expected Points**: Convert each match's xG for and against into win/draw/loss probabilities (Poisson) and compare expected points with actual points. No training or standings data required.
	- [ ] **Contract & Value Planner**: Expiry timeline, rating-per-wage efficiency, and sell-high flags (older, high value, declining form), built from the financial snapshots.
	- [ ] **Progression Watch**: Trend fit over attribute history to flag players developing or regressing faster than their age suggests; feeds the Deep-Dive trajectory charts.
	- [ ] **Best-Position Finder**: Show which position each versatile player rates best in, reusing the multi-position logic in the ratings service.
	- [ ] **Matchup Matrix**: Record which opponent archetypes you beat or struggle against (depends on Tactical Fingerprinting); core input for Match Day Prep.
	- [ ] **Season Review**: End-of-season summary (record, top performers, xPts vs points, biggest risers) exported as a shareable image.
- [ ] **UI Overhaul: The Manager's Office & Squad Hub:**
	- [ ] Refactor `player_library_frame.py` into a dynamic, split-screen `Squad Hub`.
	- [ ] Build the **Manager's Office Dashboard** to display top-level widgets upon loading a career (form table, recent results, Squad Value, Top Performers, contract expiries, and win-condition insights once available).
	- [ ] Create **Deep-Dive Profiles** (modals/sub-frames) for players, featuring radar charts for attributes and line graphs for growth/regression trajectories.
- [ ] **Update the Match Loop:**
	- [ ] Inject the Analytics Engine into the post-match save flow to provide instant feedback widgets (e.g., Custom Ratings display and Win-Condition feedback once that feature exists).
	- [ ] Create a **Match Day Prep** screen displaying historical context against the next opponent (entered manually; head-to-head drawn from past results) and a Lineup Optimizer suggesting XIs based on shrunk season rating (Expected Rating once built) and availability (injuries, suspensions, sold/loaned status).
- [ ] **Scouting & Recruitment:**
	- [ ] Build a "Shortlist Comparison" feature using per-position mean-centred similarity plus a separate level term to compare prospective transfers against an ideal positional profile built from the user's own best players in that position. Requires a shortlist data model so scouted players never enter the squad library.

**End Goal for Phase 8:** The application automatically transforms raw OCR data into deep, actionable insights. The user interacts with highly visual dashboards that provide tactical feedback, injury warnings, and transfer advice, deeply enriching the realism of their career mode save.

----
## Phase 9: Distribution & Packaging 

**Status: Not Started**

The final goal of the project is to compile the Python application and its lightweight analytics libraries into a single, user-friendly executable so non-technical gamers can easily install and run it.

### To-Do List: 
- [ ] **Executable Generation:** 
	- [ ] Configure `PyInstaller` (or Auto-py-to-exe) to package the application.
	- [ ] Implement PyInstaller hooks to specifically exclude massive, unused modules from `scikit-learn` and `scipy` to keep the `.exe` file size lightweight.
	- [ ] Ensure `customtkinter` assets, internal template images, and dynamic JSON paths resolve correctly within the packaged environment.
- [ ] **Testing & Optimization:**
	- [ ] Test the packaged executable on a separate, fresh machine to guarantee no external Python dependencies or ML libraries need to be installed by the end user.
	- [ ] Final optimization of application boot times and memory usage.

**End Goal for Phase 9:** "Gaffer's Clipboard" is a distributable, standalone `.exe` desktop program. Anyone can download it, click run, and immediately start utilizing advanced OCR and machine learning analytics for their saves without opening a terminal.