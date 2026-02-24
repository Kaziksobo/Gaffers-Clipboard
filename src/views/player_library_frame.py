import customtkinter as ctk
import logging
from src.views.widgets.custom_alert import CustomAlert
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PlayerLibraryFrame(ctk.CTkFrame):
    """The central navigation hub for managing player attributes, finances, and transfers."""
    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Dict[str, Any]) -> None:
        """Initialize the Player Library frame and its navigation buttons.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            controller (Any): The main application controller.
            theme (Dict[str, Any]): The application's theme dictionary containing colors and fonts.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.controller = controller
        self.theme = theme

        logger.info("Initializing PlayerLibraryFrame")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        for i in range(6):
            self.grid_rowconfigure(i, weight=1 if i in [0, 5] else 0)

        self.title = ctk.CTkLabel(
            self,
            text="Welcome to your player library",
            font=self.theme["fonts"]["title"],
            text_color=self.theme["colors"]["primary_text"]
        )
        self.title.grid(row=1, column=1, pady=(20, 10))

        delay_seconds = getattr(self.controller, "screenshot_delay", 3)
        self.info_label = ctk.CTkLabel(
            self,
            text=f"Upon clicking each button, you have {delay_seconds} seconds to take a screenshot.",
            font=self.theme["fonts"]["body"],
            text_color=self.theme["colors"]["secondary_text"]
        )
        self.info_label.grid(row=2, column=1, pady=(10, 20))

        # Add-player-buttons subgrid
        self.buttons_grid = ctk.CTkFrame(self, fg_color=self.theme["colors"]["background"])
        self.buttons_grid.grid(row=3, column=1, pady=(0, 20), sticky="nsew")
        self.buttons_grid.grid_columnconfigure(0, weight=1)
        self.buttons_grid.grid_columnconfigure(1, weight=1)
        self.buttons_grid.grid_columnconfigure(2, weight=1)
        self.buttons_grid.grid_columnconfigure(3, weight=1)
        self.buttons_grid.grid_columnconfigure(4, weight=1)
        self.buttons_grid.grid_rowconfigure(0, weight=1)

        self.add_gk_button = ctk.CTkButton(
            self.buttons_grid,
            text="Add Goalkeeper",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_add_gk_button_press()
        )
        self.add_gk_button.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        self.add_outfield_button = ctk.CTkButton(
            self.buttons_grid,
            text="Add Outfield Player",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.on_add_outfield_button_press()
        )
        self.add_outfield_button.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.add_financial_button = ctk.CTkButton(
            self.buttons_grid,
            text="Add Player Financial Data",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("AddFinancialFrame"))
        )
        self.add_financial_button.grid(row=0, column=2, padx=10, pady=5, sticky="ew")

        self.add_injury_button = ctk.CTkButton(
            self.buttons_grid,
            text="Add Player Injury Record",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("AddInjuryFrame"))
        )
        self.add_injury_button.grid(row=0, column=3, padx=10, pady=5, sticky="ew")

        self.leave_button = ctk.CTkButton(
            self.buttons_grid,
            text="Sell/loan Player",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("LeftPlayerFrame"))
        )
        self.leave_button.grid(row=0, column=4, padx=10, pady=5, sticky="ew")


        self.home_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            fg_color=self.theme["colors"]["button_fg"],
            text_color=self.theme["colors"]["primary_text"],
            font=self.theme["fonts"]["button"],
            command=lambda: self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame"))
        )
        self.home_button.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

    def on_add_gk_button_press(self) -> None:
        """Handle the Add Goalkeeper button press by triggering OCR and navigating on success."""
        try:
            self.controller.process_player_attributes(gk=True, first=True)
            self.controller.show_frame(self.controller.get_frame_class("AddGKFrame"))
        except Exception as e:
            # Catch the UIPopulationError from the Controller to prevent navigating to a broken frame
            logger.error(f"Goalkeeper OCR process aborted. Navigation cancelled: {e}")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="OCR Process Aborted",
                message=f"The OCR process for adding a goalkeeper was aborted: {str(e)}. Please try again.",
                alert_type="error",
            )
            return

    def on_add_outfield_button_press(self) -> None:
        """Handle the Add Outfield Player button press by triggering OCR and navigating on success."""
        try:
            self.controller.process_player_attributes(gk=False, first=True)
            self.controller.show_frame(self.controller.get_frame_class("AddOutfieldFrame1"))
        except Exception as e:
            logger.error(f"Outfield OCR process aborted. Navigation cancelled: {e}")
            CustomAlert(
                parent=self,
                theme=self.theme,
                title="OCR Process Aborted",
                message=f"The OCR process for adding an outfield player was aborted: {str(e)}. Please try again.",
                alert_type="error",
            )
            return