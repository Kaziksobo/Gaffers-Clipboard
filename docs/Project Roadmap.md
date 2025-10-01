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

***Status: In Progress***

The goal of this phase is to build out the GUI to guide the user through capturing all the required stats from each screen, validating the data, and saving it to a JSON file. 

### To-Do List:
- [ ] **Create the home screen**
    - [x] Use Tkinter to create a window like shown in [Home Screen Mock-up](homescreen_mockup.png).
    - [x] Create buttons, function not required yet
- [ ] **Create the stats capture screens**
    - [ ] Use the following mock-ups as a reference for a overall match stats capture screen, and a player stats capture screen:
        - [Overall Match Stats Capture Mock-up](overall_stats_mockup.png)
        - [Player Stats Capture Mock-up](player_stats_mockup.png)
    - [ ] Each stat should be a text field, auto-filled with the recognised value, but editable by the user.
    - [ ] Any stats the OCR fails to read should be left blank for the user to fill in.
- [ ] **Implement navigation between screens**
    - [ ] Use Tkinter frames to switch between different screens.
    - [ ] Use buttons to start the capture process, and then start by using timers to allow the user to switch to the correct screen in FIFA.

**End Goal for Phase 3:** The interface is designed and implemented. The user can navigate between screens, and placeholders for the OCR results are in place inside the editable text fields.

## Phase 4: Full Data Extraction & Screen Capture

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
    - [ ] Ensure multiple digit numbers can be read.
- [ ] **Connect the results to the GUI:**
    - [ ] Update the GUI to display the extracted stats as placeholders in the editable text fields.
    - [ ] Ensure the user can edit any incorrectly read stats.
- [ ] **Save to JSON:**
    - [ ] Upon confirmation, save the validated data to a new JSON file, using the structure from `Templates.json`.

**End Goal for Phase 4:** The core application is feature-complete. The user can be guided through each stats screen, capture the data, validate it, and save a complete match file.

---

## Phase 5: Analysis and Insights

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