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

The goal of this phase was to build the basic application framework around the proven OCR logic. This involves creating the project structure and a simple user interface. This has been successfully completed, using Tkinter to create the basic GUI, and integrating the OCR logic to read a digit from a static image when a button is pressed.

### Key Achievements:
- [x] A working Tkinter window with a button and label.
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

***Status: In Progress*** The goal of this phase is to "harden" the application—improving stability, cleaning up the codebase, and adding essential Quality of Life features for the end user before diving into advanced analytics. 

### To-Do List: 
- [x] **Codebase Refactoring**
	- [x] Rename `gui.py` to `app.py` to better reflect its role as the main application controller.
	- [x] Clean up screenshot storage logic to automatically delete old files (keep only the last X screenshots) to save disk space. 
	- [x] Make data manager save keys in snake case
 - [ ] Look at fixing OCR digit ordering for cases like 0.4 being returned as 4.0.
	- [x] Implement `pydantic` across the data manager for more rigorous data structuring
		- [x] Possibly implement across the rest of the application for documentation purposes?
- [ ] **Synchronisation**
 - [ ] Transition from using time.sleep for the screenshot delay to a different method that doesn't freeze the application.
- [ ] **Dependency Management**
	- [ ] Transition from standard `pip` and `requirements.txt` to `Poetry` for deterministic builds and dependency grouping, setting up a clean environment for final `.exe` packaging.
- [x] **Implement Logging**
	- [x] Replace all `print()` statements with the Python `logging` module to generate well-formatted, timestamped log files for easier debugging.
- [x] **Error Handling & Feedback** 
	- [x] Implement robust `try/except` blocks across the entire program (especially OCR and file I/O).
	- [x] Use `tkinter.messagebox` to display friendly error popups to the user instead of silent console failures.
- [ ] **Resolution Independence** 
	- [ ] Move from hardcoded pixel coordinates to relative scale factors in `coordinates.json`.
	- [ ] Implement logic to detect screen resolution and scale OCR regions dynamically (supporting 1080p, 4k, etc.).
- [x] **Feature Expansions**
	- [x] **Financial Data:** Create a new, dedicated frame for inputting player financial data, and saving it with the player attributes.
	- [x] **Injuries:** Create a new frame for inputting player injury data, allowing the user to attach it to a player in the library.
	- [x] **Separate Injuries and Financial Data:** Keep these two separate from the player attributes, so they can be directly accessed from the player library frame.
	- [x] **Sales and Loans:** Add functionality to mark players as sold or loaned out
	- [x] **GK Performance Frame:** Create a dedicated UI for entering/OCR-ing Goalkeeper match performance stats.
	- [x] **Optional Player Stats:** Add a toggle or logic to allow saving a match result *without* needing to enter individual player performances.
- [ ] **User Experience & Documentation**
	- [ ] Add an "Instructions" or "Help" tab/modal within the app explaining how to capture data. 
	- [ ] Write a comprehensive `README.md` for the GitHub repository detailing installation and usage. 

**End Goal for Phase 7:** The application is stable, resolution-independent, self-cleaning, and user-friendly enough for someone other than the developer to use without crashing. 

----
## Phase 8: Analytics Engine & Squad Hub

**Status: Not Started**

The goal of this phase is to transform the application from a raw data-entry tool into a living "Backroom Staff." This involves building a modular analytics engine using pure math, NumPy, and Scikit-Learn to generate actionable insights, and creating immersive UI dashboards to visualize this data.

### To-Do List: 
- [ ] **Core Analytics Engine (`src/analytics/`):**
	- [ ] Implement **Custom Match Ratings**: Use weighted positional heuristics to calculate true player performances, bypassing the game's native rating system.
	- [ ] Implement **Form Scores**: Create an Exponential Moving Average (EMA) algorithm to track highly reactive player form.
	- [ ] Implement **Monte-Carlo Season Predictor**: Use `numpy` probability distributions to simulate remaining fixtures and predict league finish probabilities.
- [ ] **Predictive & Tactical ML (Scikit-Learn):**
	- [ ] **Win-Condition Extraction**: Train a Random Forest model on historical match data to extract feature importances (e.g., discovering that pass accuracy dictates 70% of win probability).
	- [ ] **Red Zone Injury Flags**: Build a Logistic Regression model to flag players at high risk of injury based on recent sprint distance, rest days, and stamina.
	- [ ] **Tactical Fingerprinting**: Use K-Means clustering to group historical matches/opponents by playstyle (e.g., High-Press, Possession).
- [ ] **UI Overhaul: The Manager's Office & Squad Hub:**
	- [ ] Refactor `player_library_frame.py` into a dynamic, split-screen `Squad Hub`.
	- [ ] Build the **Manager's Office Dashboard** to display top-level widgets upon loading a career (Title odds, Squad Value, Top Performers, Red Zone warnings).
	- [ ] Create **Deep-Dive Profiles** (modals/sub-frames) for players, featuring radar charts for attributes and line graphs for growth/regression trajectories.
- [ ] **Update the Match Loop:**
	- [ ] Inject the Analytics Engine into the post-match save flow to provide instant feedback widgets (e.g., Custom Ratings display and Win-Condition feedback).
	- [ ] Create a **Match Day Prep** screen displaying historical context against upcoming opponents and a Lineup Optimizer suggesting XIs based on form and fitness.
- [ ] **Scouting & Recruitment:**
	- [ ] Build a "Shortlist Comparison" feature utilizing Cosine Similarity to mathematically compare prospective transfers against an ideal positional profile.

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