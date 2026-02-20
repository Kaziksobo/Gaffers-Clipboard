import customtkinter as ctk
import logging
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)

class ScrollableDropdown(ctk.CTkFrame):
    """A custom scrollable dropdown widget using a CTkToplevel window.
    
    Designed to replace standard OptionMenus for long lists, providing a 
    scrollable frame that perfectly aligns beneath the trigger button.
    """
    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: Dict[str, Any],
        values: Optional[List[str]] = None,
        variable: Optional[ctk.StringVar] = None,
        width: int = 350,
        dropdown_height: int = 200,
        placeholder: str = "Click here to select player",
        command: Optional[Callable[[str], None]] = None
    ) -> None:
        """Initialize the custom scrollable dropdown.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            theme (Dict[str, Any]): The application theme configuration.
            values (Optional[List[str]]): The list of strings to display.
            variable (Optional[ctk.StringVar]): A Tkinter string variable to sync with.
            width (int): The width of the dropdown button and popup.
            dropdown_height (int): The maximum height of the scrollable popup.
            placeholder (str): The default text to display when no value is selected.
            command (Optional[Callable[[str], None]]): Callback triggered on selection.
        """
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.theme = theme
        self.values: List[str] = values or []
        self.variable = variable or ctk.StringVar(value=placeholder)
        self.placeholder = placeholder
        self.command = command
        self.dropdown_height = dropdown_height
        self.dropdown_popup: Optional[ctk.CTkToplevel] = None
        self._outside_click_bind_id: Optional[str] = None

        self.button = ctk.CTkButton(
            self,
            text=self.variable.get(),
            font=theme["fonts"]["body"],
            fg_color=theme["colors"]["dropdown_fg"],
            text_color=theme["colors"]["primary_text"],
            hover_color=theme["colors"]["button_fg"],
            width=width,
            command=self._open_dropdown
        )
        self.button.pack()

        logger.debug(
            f"ScrollableDropdown initialized with placeholder='{self.placeholder}', "
            f"values_count={len(self.values)}, dropdown_height={self.dropdown_height}"
        )

    def set_values(self, values: List[str]) -> None:
        """Update the list of available options in the dropdown.
        
        Args:
            values (List[str]): The new list of string options.
        """
        self.values = values or []
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

    def _open_dropdown(self) -> None:
        """Calculate geometry and render the dropdown Toplevel window."""
        logger.debug(
            f"_open_dropdown called. popup_exists={self.dropdown_popup is not None}, "
            f"button_text='{self.button.cget('text')}', values_count={len(self.values)}"
        )

        if self.dropdown_popup is not None:
            logger.debug("Dropdown already open. Closing existing popup instead of opening new one.")
            self._close_dropdown()
            return

        try:
            values = self.values or ["No players found"]
            logger.debug(f"Resolved dropdown values. rendered_values_count={len(values)}")

            self.dropdown_popup = ctk.CTkToplevel(self)
            self.dropdown_popup.overrideredirect(True)
            self.dropdown_popup.attributes("-topmost", True)

            x = self.button.winfo_rootx()
            y = self.button.winfo_rooty() + self.button.winfo_height()
            width = self.button.winfo_width()
            height = self.dropdown_height

            logger.debug(
                f"Computed dropdown geometry x={x}, y={y}, width={width}, height={height}, "
                f"button_exists={self.button.winfo_exists()}, button_mapped={self.button.winfo_ismapped()}"
            )

            self.dropdown_popup.geometry(f"{width}x{height}+{x}+{y}")

            container = ctk.CTkFrame(self.dropdown_popup, fg_color=self.cget("fg_color"))
            container.pack(fill="both", expand=True)

            scroll = ctk.CTkScrollableFrame(
                container,
                fg_color=self.cget("fg_color"),
                width=width,
                height=height
            )
            scroll.pack(fill="both", expand=True)

            for name in values:
                btn = ctk.CTkButton(
                    scroll,
                    text=name,
                    fg_color=self.cget("fg_color"),
                    text_color=self.button.cget("text_color"),
                    hover_color=self.button.cget("hover_color"),
                    anchor="w",
                    command=lambda n=name: self._select_value(n)
                )
                btn.pack(fill="x", padx=4, pady=2)

            # FocusOut on overrideredirect windows can fire immediately on Windows.
            # Use global outside-click close instead.
            self.dropdown_popup.bind("<Escape>", lambda _e: self._close_dropdown())
            self.dropdown_popup.focus_force()
            self._bind_outside_click_close()

            logger.debug("Dropdown popup created and focused successfully.")
        except Exception as exc:
            logger.exception(f"Failed to open dropdown popup. error='{exc}'")
            self._close_dropdown()
    
    def _bind_outside_click_close(self) -> None:
        """Bind a click handler that closes only when clicking outside."""
        if self._outside_click_bind_id is not None:
            logger.debug("Outside-click handler already bound; skipping rebind.")
            return

        root = self.winfo_toplevel()
        self._outside_click_bind_id = root.bind("<Button-1>", self._on_global_click, add="+")
        logger.debug(f"Bound outside-click handler. bind_id='{self._outside_click_bind_id}'")

    def _unbind_outside_click_close(self) -> None:
        """Unbind this widget's outside-click handler only."""
        if self._outside_click_bind_id is None:
            return

        try:
            root = self.winfo_toplevel()
            root.unbind("<Button-1>", self._outside_click_bind_id)
            logger.debug(f"Unbound outside-click handler. bind_id='{self._outside_click_bind_id}'")
        except Exception as exc:
            logger.exception(f"Failed to unbind outside-click handler. error='{exc}'")
        finally:
            self._outside_click_bind_id = None

    def _on_global_click(self, event: Any) -> None:
        """Close dropdown only when click is outside button and popup bounds."""
        if self.dropdown_popup is None or not self.dropdown_popup.winfo_exists():
            return

        ex, ey = event.x_root, event.y_root

        px = self.dropdown_popup.winfo_rootx()
        py = self.dropdown_popup.winfo_rooty()
        pw = self.dropdown_popup.winfo_width()
        ph = self.dropdown_popup.winfo_height()

        bx = self.button.winfo_rootx()
        by = self.button.winfo_rooty()
        bw = self.button.winfo_width()
        bh = self.button.winfo_height()

        in_popup = (px <= ex <= px + pw) and (py <= ey <= py + ph)
        in_button = (bx <= ex <= bx + bw) and (by <= ey <= by + bh)

        logger.debug(
            f"Global click ex={ex}, ey={ey}, in_popup={in_popup}, in_button={in_button}, "
            f"popup_bounds=({px},{py},{pw},{ph}), button_bounds=({bx},{by},{bw},{bh})"
        )

        if not in_popup and not in_button:
            logger.debug("Click outside popup/button detected. Closing dropdown.")
            self._close_dropdown()

    def _close_dropdown(self) -> None:
        """Destroy the dropdown Toplevel window if it exists."""
        logger.debug(f"_close_dropdown called. popup_exists={self.dropdown_popup is not None}")
        self._unbind_outside_click_close()
        if self.dropdown_popup is not None:
            self.dropdown_popup.destroy()
            self.dropdown_popup = None
            logger.debug("Dropdown popup destroyed.")

    def _select_value(self, name: str) -> None:
        """Handle a selection event from inside the dropdown."""
        logger.debug(f"Dropdown option selected: '{name}'")
        self.set_value(name)
        if self.command:
            logger.debug(f"Invoking dropdown command callback with value '{name}'")
            self.command(name)
        self._close_dropdown()