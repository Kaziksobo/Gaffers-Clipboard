"""UI frame for player-library workflow navigation.

This module defines PlayerLibraryFrame, the roster-management hub where users
can launch OCR-assisted player profile capture, update financial or injury
records, and navigate to transfer-management flows.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, PlayerLibraryFrameControllerProtocol
from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)


class PlayerLibraryFrame(BaseViewFrame):
    """Navigation hub for player profile, finance, and transfer workflows.

    The frame groups high-frequency roster actions into a single screen and
    routes user intent into specialized views or OCR-driven capture flows.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: PlayerLibraryFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the player-library navigation interface.

        Creates section headings, instructional text, and grouped action
        buttons for player OCR capture, financial and injury updates, transfer
        management, and return navigation to the main menu.

        Args:
            parent (ctk.CTkFrame): Parent container widget hosting this frame.
            controller (PlayerLibraryFrameControllerProtocol): Controller used
                for OCR orchestration and frame navigation.
            theme (BaseViewThemeProtocol): Theme tokens used for visual
                appearance and typography.
        """
        super().__init__(parent, controller, theme)
        self.controller: PlayerLibraryFrameControllerProtocol = controller

        logger.info("Initializing PlayerLibraryFrame")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(2, weight=1)
        for i in range(7):
            self.grid_rowconfigure(i, weight=1 if i in [0, 6] else 0)

        self.title = ctk.CTkLabel(
            self, text="Welcome to your player library", font=self.fonts["title"]
        )
        self.title.grid(row=1, column=1, pady=(20, 10))
        self.register_wrapping_widget(self.title, width_ratio=0.8)

        self.delay_seconds: int = getattr(self.controller, "screenshot_delay", 3)
        self.info_label = ctk.CTkLabel(
            self,
            text=(
                "Manage your roster below. Use the 'Auto-Fill' buttons to "
                "auto-capture attributes directly from your game."
            ),
            font=self.fonts["body"],
        )
        self.info_label.grid(row=2, column=1, pady=(10, 20))
        self.register_wrapping_widget(self.info_label, width_ratio=0.6)

        # Add-player-buttons subgrid
        self.ocr_buttons_grid = ctk.CTkFrame(self)
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
            font=self.fonts["button"],
            command=lambda: self._on_add_gk_button_press(),
        )
        self.add_gk_button.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.add_outfield_button = ctk.CTkButton(
            self.ocr_buttons_grid,
            text="Auto-Fill Outfield Player Profile",
            font=self.fonts["button"],
            command=lambda: self._on_add_outfield_button_press(),
        )
        self.add_outfield_button.grid(row=1, column=2, padx=10, pady=5, sticky="ew")

        self.lower_buttons_grid = ctk.CTkFrame(self)
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
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("AddFinancialFrame")
            ),
        )
        self.add_financial_button.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.add_injury_button = ctk.CTkButton(
            self.lower_buttons_grid,
            text="Log Player Injury",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("AddInjuryFrame")
            ),
        )
        self.add_injury_button.grid(row=1, column=2, padx=10, pady=5, sticky="ew")

        self.leave_button = ctk.CTkButton(
            self.lower_buttons_grid,
            text="Manage Transfers and Loans",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("LeftPlayerFrame")
            ),
        )
        self.leave_button.grid(row=1, column=3, padx=10, pady=5, sticky="ew")

        self.home_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("MainMenuFrame")
            ),
        )
        self.home_button.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

    def _on_add_gk_button_press(self) -> None:
        """Launch the goalkeeper auto-fill OCR workflow.

        Prompts the user with pre-scan instructions, then triggers controller
        OCR processing for first-page goalkeeper attributes. On successful OCR,
        navigates to the goalkeeper entry frame; otherwise surfaces an error
        and keeps the user on the current screen.
        """
        check = self.show_info(
            "Prepare\nGoalkeeper Scan",
            (
                f"Please navigate to the correct screen in EA FC before "
                "starting the scanning process:\n- Open the Squad Hub and "
                "select your goalkeeper.\n- Tab over to the Attributes section."
                "\n- Ensure you are on the 1st page (showing Diving, Handling, etc.)."
                "\nWhen ready, click 'Start Scan' and keep the game window open and "
                f"unobstructed.\nThe scan will start in {self.delay_seconds} seconds."
            ),
            options=["Start Scan", "Cancel"],
        )
        if not check or check == "Cancel":
            return
        try:
            self.controller.process_player_attributes(
                is_goalkeeper=True, is_first_page=True
            )
            self.controller.show_frame(self.controller.get_frame_class("AddGKFrame"))
        except Exception as e:
            # Catch the UIPopulationError from the Controller to prevent
            # navigating to a broken frame
            logger.error(f"Goalkeeper OCR process aborted. Navigation cancelled: {e}")
            self.show_error(
                "OCR Process Aborted",
                (
                    "An error occurred while processing the goalkeeper "
                    f"attributes:\n{e!s}\n\nPlease try again."
                ),
            )
            return

    def _on_add_outfield_button_press(self) -> None:
        """Launch the outfield-player auto-fill OCR workflow.

        Prompts the user with pre-scan instructions, then triggers controller
        OCR processing for first-page outfield attributes. On successful OCR,
        navigates to the first outfield entry frame; otherwise surfaces an
        error and leaves the user on this frame.
        """
        check = self.show_info(
            "Prepare Outfield\nPlayer Scan",
            (
                f"Please navigate to the correct screen in EA FC before starting the "
                "scanning process:\n- Open the Squad Hub and select your outfield "
                "player.\n- Tab over to the Attributes section.\n- Switch to the 3rd "
                "page (showing Physical and Mental attributes).\n\nWhen ready, click "
                "'Start Scan' and keep the game window open and unobstructed.\nThe "
                f"scan will start in {self.delay_seconds} seconds."
            ),
            options=["Start Scan", "Cancel"],
        )
        if not check or check == "Cancel":
            return
        try:
            self.controller.process_player_attributes(
                is_goalkeeper=False, is_first_page=True
            )
            self.controller.show_frame(
                self.controller.get_frame_class("AddOutfieldFrame1")
            )
        except Exception as e:
            logger.error(f"Outfield OCR process aborted. Navigation cancelled: {e}")
            self.show_error(
                "OCR Process Aborted",
                (
                    f"An error occurred while processing the outfield player "
                    f"attributes:\n{e!s}\n\nPlease try again."
                ),
            )
            return
