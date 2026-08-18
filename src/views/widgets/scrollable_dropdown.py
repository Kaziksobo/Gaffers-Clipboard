"""Scrollable dropdown widget for long option lists in CustomTkinter forms."""

import logging
from collections.abc import Callable

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol
from src.views.widgets.popup_list_mixin import PopupListMixin

logger = logging.getLogger(__name__)


class ScrollableDropdown(ctk.CTkFrame, PopupListMixin):
    """A custom scrollable dropdown widget using a CTkToplevel window.

    Designed to replace standard OptionMenus for long lists, providing a
    scrollable frame that perfectly aligns beneath the trigger button.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: BaseViewThemeProtocol,
        fonts: dict[str, ctk.CTkFont],
        values: list[str] | None = None,
        variable: ctk.StringVar | None = None,
        width: int = 350,
        dropdown_height: int = 200,
        placeholder: str = "Click here to select player",
        command: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the custom scrollable dropdown.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            theme (BaseViewThemeProtocol): The application theme configuration.
            values (Optional[list[str]]): The list of strings to display.
            variable (Optional[ctk.StringVar]): A Tkinter string variable to sync with.
            width (int): The width of the dropdown button and popup.
            dropdown_height (int): The maximum height of the scrollable popup.
            placeholder (str): The default text to display when no value is selected.
            command (Optional[Callable[[str], None]]): Callback triggered on selection.
        """
        super().__init__(parent)
        self.theme: BaseViewThemeProtocol = theme
        self.fonts: dict[str, ctk.CTkFont] = fonts
        self.values: list[str] = values or []
        self.variable: ctk.StringVar = variable or ctk.StringVar(value=placeholder)
        self.placeholder: str = placeholder
        self.command: Callable[[str], None] | None = command
        self.dropdown_height: int = dropdown_height
        self.dropdown_popup: ctk.CTkToplevel | None = None
        self._popup_scroll: ctk.CTkScrollableFrame | None = None
        self._outside_click_bind_id: str | None = None

        self.button = ctk.CTkButton(
            self,
            text=self.variable.get(),
            font=self.fonts["body"],
            width=width,
            command=self._open_dropdown,
        )
        self.button.pack()

        logger.debug(
            f"ScrollableDropdown initialized with placeholder='{self.placeholder}', "
            f"values_count={len(self.values)}, dropdown_height={self.dropdown_height}"
        )

    def set_values(self, values: list[str]) -> None:
        """Update the list of available options in the dropdown.

        Args:
            values (list[str]): The new list of string options.
        """
        self.values: list[str] = values or []
        logger.debug(f"Dropdown values updated. values_count={len(self.values)}")

    def set_value(self, value: str) -> None:
        """Programmatically set the selected value of the dropdown.

        Args:
            value (str): The string value to select.
        """
        if self.variable:
            self.variable.set(value)
        self.button.configure(text=value)
        logger.debug(f"Dropdown value set to '{value}'")

    def get_value(self) -> str:
        """Retrieve the currently selected value.

        Returns:
            str: The currently selected text.
        """
        return self.variable.get() if self.variable else self.button.cget("text")

    def _popup_anchor(self) -> ctk.CTkBaseClass:
        """Return the trigger button the popup positions itself under.

        Returns:
            ctk.CTkBaseClass: The dropdown's trigger button.
        """
        return self.button

    def _popup_values(self) -> list[str]:
        """Return the configured option list, or a placeholder when empty.

        Returns:
            list[str]: The current option strings, or a single "No items
                found" placeholder if none are configured.
        """
        return self.values or ["No items found"]

    def _popup_option_style(self) -> dict[str, str]:
        """Match each option button's colors to the trigger button's theme.

        Returns:
            dict[str, str]: `text_color`/`hover_color` kwargs copied from the
                trigger button.
        """
        return {
            "text_color": self.button.cget("text_color"),
            "hover_color": self.button.cget("hover_color"),
        }

    def _on_popup_select(self, name: str) -> None:
        """Handle a selection event from inside the dropdown.

        Args:
            name (str): The selected option's text.
        """
        self._select_value(name)

    def _open_dropdown(self) -> None:
        """Toggle the dropdown popup open, or closed if it is already open."""
        logger.debug(
            f"_open_dropdown called. popup_exists={self.dropdown_popup is not None}, "
            f"button_text='{self.button.cget('text')}', values_count={len(self.values)}"
        )

        if self.dropdown_popup is not None:
            logger.debug(
                (
                    "Dropdown already open. ",
                    "Closing existing popup instead of opening new one.",
                )
            )
            self._close_popup()
            return

        self._render_popup()

    def _select_value(self, name: str) -> None:
        """Handle a selection event from inside the dropdown.

        Args:
            name (str): The selected option's text.
        """
        logger.debug(f"Dropdown option selected: '{name}'")
        self.set_value(name)
        if self.command:
            logger.debug(f"Invoking dropdown command callback with value '{name}'")
            self.command(name)
        self._close_popup()
