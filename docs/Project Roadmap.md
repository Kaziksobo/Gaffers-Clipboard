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

## Phase 2: The Application Skeleton

**Status: Complete**

The goal of this phase was to build the basic application framework around the proven OCR logic. This involves creating the project structure and a simple user interface. This has been successfully completed, using Tkinter to create the basic GUI, and integrating the OCR logic to read a digit from a static image when a button is pressed.

### Key Achievements:
- [x] A working Tkinter window with a button and label.
- [x] Integrated OCR logic to read a digit from a static image.
- [x] The label updates correctly when the button is pressed.
- [x] GitHub repository and file structure created.
- [x] Documentation for project planning written out.

---

## Phase 3: GUI development

**Status: Complete**

The goal of this phase was to build out the GUI to guide the user through capturing all the applications screens, capturing screenshots when needed, that can then be analysed with OCR. This has been successfully completed, transitioning to `customtkinter`, creating all frames needed for the OCR features, and including buttons to transition between frames and take screenshots.

### Key Achievements:
- [x] The 5 main frames that make up the main application are created and working.
- [x] Stats capture screens have editable text fields with placeholder values.
- [x] Buttons to switch between frames work, allowing the user to navigate thru the application.

---
## Phase 4: Full Data Extraction & Screen Capture

***Status: In progress***

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

## Phase 5: Data Persistence

**Status: Next Up (Not Started)**

The goal of this phase is to finish end-to-end capture: Complete match/player performance saving, and schema-aligned output files.

### To-Do List:
- [ ] **Player Performance Capture Flow**
	- [ ] Add player selection (dropdown) in `PlayerStatsFrame`, populated from saved players with IDs.
	- [ ] Wire OCR for `player_performance` ROIs to prefill per-player stats; allow manual edits before saving.
	- [ ] Buffer multiple player performances and associate them with `player_id` on save.
- [ ] **Match Save Pipeline**
	- [ ] Gather validated match overview + player performances and call `DataManager.add_match` to write `matches.json`.
	- [ ] Align field names between UI and `coordinates.json` (e.g., `fouls_comitted` vs. `fouls_committed`, `def_aware` → `defensive_awareness`).
	- [ ] Structure saved data to match the planned template (home/away stats, linked player performances).

**End Goal for Phase 5:** The user can capture match overview and player performances, review/edit them, and save a complete match record (with linked player IDs) to JSON with reliable OCR

---

## Phase 6: 

**Status: Not Started**

The goal of this phase is to integrate the OCR tool with the existing analysis scripts and build out the machine learning features.

### To-Do List:
- [ ] **Integrate with Analysis Notebook:**
    - [ ] Point the `analysis.ipynb` to the folder where the OCR tool saves its output.
- [ ] **Implement ML Insights:**
    - [ ] Develop the custom "Form Score" calculation.
    - [ ] Use clustering to identify player roles automatically.
    - [ ] Build the performance vs. potential tracking system.
- [ ] **Build Dashboards:**
    - [ ] Create the Player Comparison view.
    - [ ] Design the in-depth, automated Match Reports.
- [ ] **Package for Distribution:**
    - [ ] Use PyInstaller to create a standalone `.exe` file.