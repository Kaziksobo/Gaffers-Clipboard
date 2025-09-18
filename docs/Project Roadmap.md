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

**Status: In Progress**

The goal of this phase is to build the basic application framework around the proven OCR logic. This involves creating the project structure and a simple user interface.

### To-Do List:
- [x] Create the main project repository (`Gaffers-Clipboard`).
- [x] Initialize Git (`git init`).
- [x] Create the project file structure (`src`, `docs`, `assets`).
- [x] Set up Obsidian vault in the `docs` folder.
- [x] Create a virtual environment (`venv`) with system-site-packages.
- [ ] **Move OCR Logic:**
    - [ ] Create `src/ocr.py`.
    - [ ] Move the template matching code into a reusable function within this file (e.g., `recognize_digit()`).
- [ ] **Build the Basic GUI:**
    - [ ] Create `src/gui.py`.
    - [ ] Using Tkinter, create a simple window with a text label and a "Capture" button, based on the [initial mock-up](basic_mockup.png).
- [ ] **Create Main Entry Point:**
    - [ ] Create `src/__main__.py`.
    - [ ] Write the code to launch the GUI from this file.
- [ ] **Integrate Logic:**
    - [ ] Connect the "Capture" button to a function that:
        1.  Loads the static screenshot (`fifa_screenshot.png`).
        2.  Crops to the pre-defined ROI for a single digit.
        3.  Passes the cropped image to the `recognize_digit()` function.
        4.  Updates the GUI's text label with the returned digit.

**🏁 End Goal for Phase 2:** A working desktop application with a button that can read a digit from a saved image and display the result in the window.

---

## Phase 3: Full Data Extraction & Validation

**Status: Not Started**

The goal of this phase is to expand the application to handle all the required stats from every screen and ensure the data is accurate before saving.

### To-Do List:
- [ ] **Implement Live Screen Capture:**
    - [ ] Integrate the `mss` library to replace `cv2.imread()`.
    - [ ] Allow the application to capture a screen region in a loop.
- [ ] **Map All Coordinates:**
    - [ ] For each stats screen (Team, Player, etc.), create a configuration file or dictionary that maps every stat to its pixel coordinates on the screen.
- [ ] **Expand OCR Capabilities:**
    - [ ] Create datasets for letters and symbols.
    - [ ] Implement color masking to handle text that isn't white (e.g., player attributes).
- [ ] **Build the Validator GUI:**
    - [ ] Create a new window that appears after a screen is captured.
    - [ ] Display all the extracted stats in editable text fields.
    - [ ] Include "Confirm" and "Cancel" buttons.
- [ ] **Save to JSON:**
    - [ ] Upon confirmation, save the validated data to a new JSON file, using the structure from `Templates.json`.

**🏁 End Goal for Phase 3:** The core application is feature-complete. The user can be guided through each stats screen, capture the data, validate it, and save a complete match file.

---

## Phase 4: Analysis and Insights

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