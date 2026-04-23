"""UI confirmation frame shown after successful match persistence.

This module defines MatchAddedFrame, a lightweight success view used at the
end of the match-entry workflow. It confirms completion and offers a direct
navigation path back to the main menu.
"""

import logging

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, MatchAddedFrameControllerProtocol
from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)


class MatchAddedFrame(BaseViewFrame):
    """Success confirmation frame for completed match save flows.

    The frame intentionally keeps interaction minimal: acknowledge success and
    return the user to the main navigation hub.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: MatchAddedFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the post-save confirmation interface.

        Creates a centered success message and a single action button that
        returns the user to MainMenuFrame.

        Args:
            parent (ctk.CTkFrame): The parent CTk window/frame.
            controller (MatchAddedFrameControllerProtocol):
                The main application controller.
            theme (BaseViewThemeProtocol):
                The theme dictionary containing colors and fonts.
        """
        super().__init__(parent, controller, theme)
        self.controller: MatchAddedFrameControllerProtocol = controller

        logger.info("Initializing MatchAddedFrame")

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct and arrange widgets for the match-added confirmation view.

        Builds a centered success message and a single navigation button so
        users can acknowledge the saved match and return to the main menu.
        """
        self.label = ctk.CTkLabel(
            self,
            text="Match successfully recorded",
            font=self.fonts["title"],
            anchor="center",
        )
        self.label.pack(expand=True)

        self.done_button = ctk.CTkButton(
            self,
            text="Return to Main Menu",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("MainMenuFrame")
            ),
        )
        self.done_button.pack(pady=10)
