"""Free-text entry with a live-filtered suggestion popup for CustomTkinter forms."""

import logging
import tkinter as tk

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol
from src.views.widgets.popup_list_mixin import PopupListMixin

logger = logging.getLogger(__name__)


class AutocompleteEntry(ctk.CTkFrame, PopupListMixin):
    """A free-text entry that suggests matching values as the user types.

    Unlike `ScrollableDropdown`, selection never restricts what can be typed
    — the suggestion popup is purely an aid for picking a previously-seen
    value, and any free text (e.g. a brand-new value) remains valid input.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: BaseViewThemeProtocol,
        fonts: dict[str, ctk.CTkFont],
        variable: ctk.StringVar,
        values: list[str] | None = None,
        width: int = 200,
        dropdown_height: int = 200,
    ) -> None:
        """Initialize the autocomplete entry.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            theme (BaseViewThemeProtocol): The application theme configuration.
            fonts (dict[str, ctk.CTkFont]): The application's font registry.
            variable (ctk.StringVar): The Tkinter string variable to sync with.
            values (Optional[list[str]]): The candidate strings to suggest from.
            width (int): The width of the entry and popup.
            dropdown_height (int): The maximum height of the suggestion popup.
        """
        super().__init__(parent)
        self.theme: BaseViewThemeProtocol = theme
        self.fonts: dict[str, ctk.CTkFont] = fonts
        self.variable: ctk.StringVar = variable
        self.values: list[str] = values or []
        self.dropdown_height: int = dropdown_height
        self.dropdown_popup: ctk.CTkToplevel | None = None
        self._popup_scroll: ctk.CTkScrollableFrame | None = None
        self._outside_click_bind_id: str | None = None
        self._current_matches: list[str] = []

        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.variable,
            width=width,
            font=self.fonts["body"],
        )
        self.entry.pack()
        self.entry.bind("<KeyRelease>", self._on_key_release)
        # The popup never takes keyboard focus (see _popup_takes_focus), so
        # Escape must be caught here on the entry instead of on the popup.
        self.entry.bind("<Escape>", lambda _e: self._close_popup())

        logger.debug(
            f"AutocompleteEntry initialized with values_count={len(self.values)}, "
            f"dropdown_height={self.dropdown_height}"
        )

    def set_values(self, values: list[str]) -> None:
        """Update the list of candidate strings suggestions are filtered from.

        Args:
            values (list[str]): The new list of candidate strings.
        """
        self.values = values or []
        logger.debug(f"Autocomplete values updated. values_count={len(self.values)}")

    def _popup_anchor(self) -> ctk.CTkBaseClass:
        """Return the entry the popup positions itself under.

        Returns:
            ctk.CTkBaseClass: This widget's entry field.
        """
        return self.entry

    def _popup_values(self) -> list[str]:
        """Return the current substring matches computed for the popup.

        Returns:
            list[str]: The candidate strings matching the current query.
        """
        return self._current_matches

    def _popup_takes_focus(self) -> bool:
        """Prevent the popup from stealing keyboard focus while the user types.

        Returns:
            bool: Always False — the entry must keep focus so typing isn't
                interrupted by the popup grabbing the OS input focus.
        """
        return False

    def _on_popup_select(self, name: str) -> None:
        """Fill the entry with the selected suggestion and close the popup.

        Args:
            name (str): The selected suggestion's text.
        """
        logger.debug(f"Autocomplete suggestion selected: '{name}'")
        self.variable.set(name)
        self._close_popup()

    def _on_key_release(self, event: tk.Event) -> None:
        """Re-filter suggestions and refresh the popup contents on every keystroke.

        The popup window itself is created once, the first time there are
        matches to show, and left open across subsequent keystrokes — only
        its option buttons are refreshed (via `_render_popup`, which is a
        no-op on the window itself once open). Destroying and recreating the
        Toplevel on every keystroke previously fought the entry for keyboard
        focus and could leave outside-click detection reading stale geometry.

        Args:
            event (tk.Event): The key-release event (unused; current text is
                read from `self.variable`).
        """
        del event
        query = self.variable.get().strip().lower()
        if not query:
            self._close_popup()
            return

        self._current_matches = [v for v in self.values if query in v.lower()]
        if not self._current_matches:
            self._close_popup()
            return

        self._render_popup()
