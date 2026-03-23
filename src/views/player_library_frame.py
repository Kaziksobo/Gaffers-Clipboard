import customtkinter as ctk
import logging
from typing import Dict, Any

from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)

class PlayerLibraryFrame(BaseViewFrame):
    """The central navigation hub for managing player attributes, finances, and transfers."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        """Initialize the Player Library frame and its navigation buttons.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme dictionary containing colors and fonts.
        """
        super().__init__(parent, controller, theme)

        logger.info("Initializing PlayerLibraryFrame")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)

        self.title = ctk.CTkLabel(
            self,
            text="Welcome to your player library",
            font=self.fonts["title"],
            text_color=self.theme.colors.primary_text
        )
        self.title.grid(row=1, column=1, pady=(20, 10))
        self.register_wrapping_widget(self.title, width_ratio=0.8)

        self.delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.info_label = ctk.CTkLabel(
            self,
            text="Manage your roster below. Use the 'Auto-Fill' buttons to auto-capture attributes directly from your game.",
            font=self.fonts["body"],
            text_color=self.theme.colors.secondary_text,
        )
        self.info_label.grid(row=2, column=1, pady=(10, 20))
        self.register_wrapping_widget(self.info_label, width_ratio=0.6)

        # Add-player-buttons subgrid
        self.ocr_buttons_grid = ctk.CTkFrame(self, fg_color=self.theme.colors.background)
        self.ocr_buttons_grid.grid(row=3, column=1, pady=(0, 20), sticky="nsew")
        self.ocr_buttons_grid.grid_columnconfigure(0, weight=1)
        self.ocr_buttons_grid.grid_columnconfigure(1, weight=0)
        self.ocr_buttons_grid.grid_columnconfigure(2, weight=0)
        self.ocr_buttons_grid.grid_columnconfigure(3, weight=1)
        self.ocr_buttons_grid.grid_rowconfigure(0, weight=1)
        self.ocr_buttons_grid.grid_rowconfigure(1, weight=0)
        self.ocr_buttons_grid.grid_rowconfigure(2, weight=1)

        self.add_gk_button = ctk.CTkButton(
            self.ocr_buttons_grid,
            text="Auto-Fill Goalkeeper Profile",
            fg_color=self.theme.colors.button_fg,
            text_color=self.theme.colors.primary_text,
            font=self.fonts["button"],
            command=lambda: self.on_add_gk_button_press()
        )
        self.add_gk_button.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.add_outfield_button = ctk.CTkButton(
            self.ocr_buttons_grid,
            text="Auto-Fill Outfield Player Profile",
            fg_color=self.theme.colors.button_fg,
            text_color=self.theme.colors.primary_text,
            font=self.fonts["button"],
            command=lambda: self.on_add_outfield_button_press()
        )
        self.add_outfield_button.grid(row=1, column=2, padx=10, pady=5, sticky="ew")

        self.lower_buttons_grid = ctk.CTkFrame(self, fg_color=self.theme.colors.background)
        self.lower_buttons_grid.grid(row=4, column=1, pady=(0, 20), sticky="nsew")
        self.lower_buttons_grid.grid_columnconfigure(0, weight=1)
        self.lower_buttons_grid.grid_columnconfigure(1, weight=0)
        self.lower_buttons_grid.grid_columnconfigure(2, weight=0)
        self.lower_buttons_grid.grid_columnconfigure(3, weight=0)
        self.lower_buttons_grid.grid_columnconfigure(4, weight=1)
        self.lower_buttons_grid.grid_rowconfigure(0, weight=1)
        self.lower_buttons_grid.grid_rowconfigure(1, weight=0)
        self.lower_buttons_grid.grid_rowconfigure(2, weight=1)

        self.add_financial_button = ctk.CTkButton(
            self.lower_buttons_grid,
            text="Update Player Financials",
            fg_color=self.theme.colors.button_fg,
            text_color=self.theme.colors.primary_text,
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("AddFinancialFrame"))
        )
        self.add_financial_button.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.add_injury_button = ctk.CTkButton(
            self.lower_buttons_grid,
            text="Log Player Injury",
            fg_color=self.theme.colors.button_fg,
            text_color=self.theme.colors.primary_text,
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("AddInjuryFrame"))
        )
        self.add_injury_button.grid(row=1, column=2, padx=10, pady=5, sticky="ew")

        self.leave_button = ctk.CTkButton(
            self.lower_buttons_grid,
            text="Manage Transfers and Loans",
            fg_color=self.theme.colors.button_fg,
            text_color=self.theme.colors.primary_text,
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("LeftPlayerFrame"))
        )
        self.leave_button.grid(row=1, column=3, padx=10, pady=5, sticky="ew")


        self.home_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            fg_color=self.theme.colors.button_fg,
            text_color=self.theme.colors.primary_text,
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        )
        self.home_button.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

    def on_add_gk_button_press(self) -> None:
        """Handle the Add Goalkeeper button press by triggering OCR and navigating on success."""
        check = self.show_info(
            "Prepare\nGoalkeeper Scan",
            f"Please navigate to the correct screen in EA FC before starting the scanning process:\n- Open the Squad Hub and select your goalkeeper.\n- Tab over to the Attributes section.\n- Ensure you are on the 1st page (showing Diving, Handling, etc.).\nWhen ready, click 'Start Scan' and keep the game window open and unobstructed.\nThe scan will start in {self.delay_seconds} seconds.",
            options=["Start Scan", "Cancel"]
        )
        if not check or check == "Cancel":
            return
        try:
            self.controller.process_player_attributes(gk=True, first=True)
            self.controller.show_frame(self.controller.get_frame_class("AddGKFrame"))
        except Exception as e:
            # Catch the UIPopulationError from the Controller to prevent navigating to a broken frame
            logger.error(f"Goalkeeper OCR process aborted. Navigation cancelled: {e}")
            self.show_error("OCR Process Aborted", f"An error occurred while processing the goalkeeper attributes:\n{str(e)}\n\nPlease try again.")
            return

    def on_add_outfield_button_press(self) -> None:
        """Handle the Add Outfield Player button press by triggering OCR and navigating on success."""
        check = self.show_info(
            "Prepare Outfield\nPlayer Scan",
            f"Please navigate to the correct screen in EA FC before starting the scanning process:\n- Open the Squad Hub and select your outfield player.\n- Tab over to the Attributes section.\n- Switch to the 3rd page (showing Physical and Mental attributes).\n\nWhen ready, click 'Start Scan' and keep the game window open and unobstructed.\nThe scan will start in {self.delay_seconds} seconds.",
            options=["Start Scan", "Cancel"]
        )
        if not check or check == "Cancel":
            return
        try:
            self.controller.process_player_attributes(gk=False, first=True)
            self.controller.show_frame(self.controller.get_frame_class("AddOutfieldFrame1"))
        except Exception as e:
            logger.error(f"Outfield OCR process aborted. Navigation cancelled: {e}")
            self.show_error("OCR Process Aborted", f"An error occurred while processing the outfield player attributes:\n{str(e)}\n\nPlease try again.")    
            return