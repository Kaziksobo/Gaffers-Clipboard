"""UI frame for creating a new career profile.

This module defines CreateCareerFrame, a startup workflow view that collects
core career metadata, supports league selection from defaults or custom input,
validates required fields, and delegates persistence and activation to the
controller.
"""

import contextlib
import json
import logging
from pathlib import Path

import customtkinter as ctk

from src.contracts.ui import (
    BaseViewThemeProtocol,
    CreateCareerFrameControllerProtocol,
)
from src.utils import safe_int_conversion
from src.views.base_view_frame import BaseViewFrame
from src.views.mixins import EntryFocusMixin
from src.views.widgets.scrollable_dropdown import ScrollableDropdown

logger = logging.getLogger(__name__)


class CreateCareerFrame(BaseViewFrame, EntryFocusMixin):
    """Form-driven frame for creating a new career save.

    The frame captures club, manager, season, match settings, and league data
    before validating and forwarding the payload to the controller.
    """

    _show_main_menu_nav = False

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: CreateCareerFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the create-career form interface.

        Constructs all entry widgets and selectors required to create a career,
        including optional league defaults loaded from configuration. The
        layout is split into a dedicated entry grid and action controls so the
        creation flow remains clear and guided for first-time users.

        Args:
            parent (ctk.CTkFrame): The parent container.
            controller (CreateCareerFrameControllerProtocol): The main
                application controller.
            theme (BaseViewThemeProtocol): The application's theme
                configuration.
        """
        super().__init__(parent, controller, theme)
        self.controller: CreateCareerFrameControllerProtocol = controller

        logger.info("Initializing CreateCareerFrame")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)

        # Main Heading
        self.main_heading = ctk.CTkLabel(
            self, text="Create New Career", font=self.fonts["title"]
        )
        self.main_heading.grid(row=1, column=1)

        # Entry grid
        self.entry_frame = ctk.CTkFrame(self)
        self.entry_frame.grid(row=2, column=1, pady=20)
        self.entry_frame.grid_columnconfigure(0, weight=1)
        self.entry_frame.grid_columnconfigure(1, weight=0)
        self.entry_frame.grid_columnconfigure(2, weight=0)
        self.entry_frame.grid_columnconfigure(3, weight=1)
        self.entry_frame.grid_rowconfigure(0, weight=1)
        self.entry_frame.grid_rowconfigure(1, weight=0)
        self.entry_frame.grid_rowconfigure(2, weight=0)
        self.entry_frame.grid_rowconfigure(3, weight=0)
        self.entry_frame.grid_rowconfigure(4, weight=0)
        self.entry_frame.grid_rowconfigure(5, weight=0)
        self.entry_frame.grid_rowconfigure(6, weight=1)

        # Club Name
        self.club_name_label = ctk.CTkLabel(
            self.entry_frame, text="Club Name:", font=self.fonts["body"]
        )
        self.club_name_label.grid(row=1, column=1, sticky="e", pady=5, padx=(0, 10))
        self.club_name_entry = ctk.CTkEntry(
            self.entry_frame, font=self.fonts["body"], width=200
        )
        self.club_name_entry.grid(row=1, column=2, sticky="w", pady=5)

        # Manager Name
        self.manager_name_label = ctk.CTkLabel(
            self.entry_frame, text="Manager Name:", font=self.fonts["body"]
        )
        self.manager_name_label.grid(row=2, column=1, sticky="e", pady=5, padx=(0, 10))
        self.manager_name_entry = ctk.CTkEntry(
            self.entry_frame, font=self.fonts["body"], width=200
        )
        self.manager_name_entry.grid(row=2, column=2, sticky="w", pady=5)

        # Starting Year
        self.starting_season_label = ctk.CTkLabel(
            self.entry_frame, text="Starting Season:", font=self.fonts["body"]
        )
        self.starting_season_label.grid(
            row=3, column=1, sticky="e", pady=5, padx=(0, 10)
        )
        self.starting_season_entry = ctk.CTkEntry(
            self.entry_frame,
            font=self.fonts["body"],
            width=200,
            placeholder_text="e.g. 24/25",
        )
        self.starting_season_entry.grid(row=3, column=2, sticky="w", pady=5)

        # Half Length
        self.half_length_label = ctk.CTkLabel(
            self.entry_frame, text="Half Length (mins):", font=self.fonts["body"]
        )
        self.half_length_label.grid(row=4, column=1, sticky="e", pady=5, padx=(0, 10))
        self.half_length_entry = ctk.CTkEntry(
            self.entry_frame, font=self.fonts["body"], width=200
        )
        self.half_length_entry.grid(row=4, column=2, sticky="w", pady=5)

        # Match Difficulty
        self.match_difficulty_label = ctk.CTkLabel(
            self.entry_frame, text="Match Difficulty:", font=self.fonts["body"]
        )
        self.match_difficulty_label.grid(
            row=5, column=1, sticky="e", pady=5, padx=(0, 10)
        )
        # Dropdown for match difficulty, with options: Beginner, Amateur, Semi-Pro,
        # Professional, World Class, Legendary, Ultimate
        self.match_difficulty_var = ctk.StringVar(value="Select Difficulty")
        self.match_difficulty_dropdown = ctk.CTkOptionMenu(
            self.entry_frame,
            variable=self.match_difficulty_var,
            values=[
                "Beginner",
                "Amateur",
                "Semi-Pro",
                "Professional",
                "World Class",
                "Legendary",
                "Ultimate",
            ],
            font=self.fonts["body"],
        )
        self.match_difficulty_dropdown.grid(row=5, column=2, sticky="w", pady=5)

        # League selection (required)
        self.league_label = ctk.CTkLabel(
            self.entry_frame, text="League:", font=self.fonts["body"]
        )
        self.league_label.grid(row=6, column=1, sticky="e", pady=5, padx=(0, 10))

        # Attempt to load league defaults from config
        leagues: list[str] = []
        config_path: Path = (
            self.controller.PROJECT_ROOT / "config" / "league_competitions.json"
        )
        try:
            if config_path.exists():
                with Path.open(config_path, encoding="utf-8") as f:
                    defaults: dict[str, list[str] | dict[str, list[str]]] = json.load(f)
                    # Support two formats: either {"League Name": [...]}
                    # or {"leagues": { ... }}
                    if isinstance(defaults, dict):
                        if "leagues" in defaults and isinstance(
                            defaults["leagues"], dict
                        ):
                            defaults: dict[str, list[str]] = defaults["leagues"]
                        leagues: list[str] = sorted(
                            k for k in defaults if isinstance(k, str)
                        )
        except Exception as e:
            logger.debug(
                "Failed to load league defaults from %s: %s",
                config_path,
                e,
                exc_info=True,
            )
            leagues: list[str] = []

        self.league_var = ctk.StringVar(value="Select League")
        # Create a small ScrollableDropdown and allow adding a custom league
        if leagues:
            dropdown_values: list[str] = [*leagues, "Add custom league..."]
            self.league_dropdown = ScrollableDropdown(
                self.entry_frame,
                theme=self.theme,
                fonts=self.fonts,
                variable=self.league_var,
                values=dropdown_values,
                width=250,
                dropdown_height=150,
                placeholder="Select League",
                command=self._on_league_selected,
            )
            self.league_dropdown.grid(row=6, column=2, sticky="w", pady=5)
            # Hidden custom entry (only shown when user selects Add custom league...)
            self.custom_league_entry = ctk.CTkEntry(
                self.entry_frame,
                font=self.fonts["body"],
                width=200,
                placeholder_text="Enter custom league name",
            )
        else:
            # Fallback to free-text entry if no defaults available
            self.league_entry = ctk.CTkEntry(
                self.entry_frame,
                font=self.fonts["body"],
                width=200,
                placeholder_text="Enter league name",
            )
            self.league_entry.grid(row=6, column=2, sticky="w", pady=5)

    def on_show(self) -> None:
        """Reset form fields whenever the frame becomes active.

        Clears all career input widgets, restores placeholders and default
        dropdown selections, and hides temporary custom-league controls where
        relevant so each visit starts from a clean state.
        """
        self.club_name_entry.delete(0, "end")
        self.manager_name_entry.delete(0, "end")
        self.starting_season_entry.delete(0, "end")
        self.starting_season_entry.configure(placeholder_text="e.g. 24/25")
        self.half_length_entry.delete(0, "end")
        self.match_difficulty_var.set("Select Difficulty")
        # Reset league widgets
        if hasattr(self, "league_var"):
            with contextlib.suppress(Exception):
                self.league_var.set("Select League")
                if (
                    hasattr(self, "custom_league_entry")
                    and self.custom_league_entry.winfo_ismapped()
                ):
                    self.custom_league_entry.grid_forget()
        if hasattr(self, "league_entry"):
            with contextlib.suppress(Exception):
                self.league_entry.delete(0, "end")

    def _on_league_selected(self, value: str) -> None:
        """Handle league dropdown selection state transitions.

        When ``Add custom league...`` is selected, this callback reveals a
        custom league entry field and redirects validation to free-text input.
        For standard selections, any custom-entry UI is hidden.

        Args:
            value (str): Newly selected dropdown value.
        """
        with contextlib.suppress(Exception):
            if value == "Add custom league...":
                # show custom entry under the dropdown
                self.custom_league_entry.grid(row=7, column=2, sticky="w", pady=(4, 8))
                self.custom_league_entry.focus()
                # set variable to empty so validation forces custom input
                self.league_var.set("")
            elif (
                hasattr(self, "custom_league_entry")
                and self.custom_league_entry.winfo_ismapped()
            ):
                self.custom_league_entry.grid_forget()

        # Button subgrid (return to main menu, create career)
        button_subgrid = ctk.CTkFrame(self)
        button_subgrid.grid(row=3, column=1, pady=20)
        button_subgrid.grid_columnconfigure(0, weight=1)
        button_subgrid.grid_columnconfigure(1, weight=0)
        button_subgrid.grid_columnconfigure(2, weight=0)
        button_subgrid.grid_columnconfigure(3, weight=1)
        button_subgrid.grid_rowconfigure(0, weight=1)
        button_subgrid.grid_rowconfigure(1, weight=0)
        button_subgrid.grid_rowconfigure(2, weight=1)

        # Return to Main Menu Button
        self.return_button = ctk.CTkButton(
            button_subgrid,
            text="Return to Career Selection",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("CareerSelectFrame")
            ),
        )
        self.return_button.grid(row=1, column=1, padx=10)

        # Create Career Button
        self.create_career_button = ctk.CTkButton(
            button_subgrid,
            text="Start Career",
            font=self.fonts["button"],
            command=self._on_create_career_button_press,
        )
        self.create_career_button.grid(row=1, column=2, padx=10)
        self.style_submit_button(self.create_career_button)

        self.apply_focus_flourishes(self)

    def _on_create_career_button_press(self) -> None:
        """Validate form input and prepare career creation payload.

        This method is the main submit pipeline for CreateCareerFrame. It
        collects all user-entered values, validates season format and half
        length constraints, checks required fields including league selection,
        and halts with contextual warnings when validation fails.

        On successful validation, creation proceeds through helper methods that
        persist and activate the new career context.
        """
        club: str = self.club_name_entry.get().strip()
        manager: str = self.manager_name_entry.get().strip()
        season: str = self.starting_season_entry.get().strip()
        length: int | None = safe_int_conversion(self.half_length_entry.get().strip())
        difficulty: str = self.match_difficulty_var.get()

        # Check if the season is in a valid format (e.g. "24/25")
        season: str | None = self.validate_season(season)
        if season is None:
            return

        self.missing_fields: list[str] = []
        if not club:
            self.missing_fields.append("Club Name")
        if not manager:
            self.missing_fields.append("Manager Name")
        if not season:
            self.missing_fields.append("Starting Season")
        if not length:
            self.missing_fields.append("Half Length")
        if difficulty in {"Select Difficulty", ""}:
            self.missing_fields.append("Difficulty")
        # League required
        self._check_league()

        if self.missing_fields:
            logger.warning(
                "Career creation blocked. Missing fields: %s",
                ", ".join(self.missing_fields),
            )
            self.show_warning(
                "Missing Information",
                (
                    f"The following required fields are "
                    f"missing: {', '.join(self.missing_fields)}.\n\n"
                    "Please fill them in before proceeding."
                ),
            )
            return

        if not self.validate_half_length(length):
            return

        if not self._save_and_activate(
            club=club,
            manager=manager,
            season=season,
            length=length,
            difficulty=difficulty,
            league_value=self.league_var.get()
            if hasattr(self, "league_var")
            else self.league_entry.get(),
        ):
            return

    def _check_league(self) -> None:
        """Validate league selection and record missing-state errors.

        Resolves league value from either dropdown or fallback entry mode and
        appends ``League`` to the missing-fields collection when no usable
        value is present.
        """
        if hasattr(self, "league_var"):
            league_value: str = self.league_var.get()
            # If user selected Add custom league...,
            # the var may be empty and custom entry shown
            if (
                not league_value
                and hasattr(self, "custom_league_entry")
                and self.custom_league_entry.winfo_ismapped()
            ):
                league_value: str = self.custom_league_entry.get().strip()
            if league_value in {"Select League", ""}:
                self.missing_fields.append("League")
        else:
            league_value: str = self.league_entry.get().strip()
            if not league_value:
                self.missing_fields.append("League")

    def _save_and_activate(
        self,
        club: str,
        manager: str,
        season: str,
        length: int | None,
        difficulty: str,
        league_value: str,
    ) -> bool:
        """Persist a new career and switch application context to it.

        Normalizes league naming for storage consistency, delegates career
        creation to the controller, and navigates to the main menu when save
        succeeds. Errors are logged and surfaced through user-facing dialogs.

        Args:
            club (str): Club name for the new career.
            manager (str): Manager name for the new career.
            season (str): Starting season token (for example ``24/25``).
            length (int | None): Match half length in minutes.
            difficulty (str): Selected match difficulty label.
            league_value (str): League selection from dropdown or custom input.

        Returns:
            bool: True when creation and navigation succeed; False otherwise.
        """
        try:
            # Difficulty is cast to the DifficultyLevel literal type
            self.controller.save_new_career(
                club_name=club,
                manager_name=manager,
                starting_season=season,
                half_length=length,
                match_difficulty=difficulty,
                league=league_value,
            )

            logger.info(
                "Successfully created career for %s. Navigating to Main Menu.",
                club,
            )
            self.show_success(
                "Career Created",
                f"Your new career with {club} has been successfully created!",
            )
            self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
            return True

        except Exception as e:
            logger.error("Failed to create new career: %s", e, exc_info=True)
            self.show_error(
                "Error Creating Career",
                (
                    f"An error occurred while creating your career: \n{e!s}\n\n"
                    "Please try again."
                ),
            )
            return False
