import customtkinter as ctk
from typing import Dict, Any, List, Optional, Callable

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

    def set_values(self, values: List[str]) -> None:
        """Update the list of available options in the dropdown.
        
        Args:
            values (List[str]): The new list of string options.
        """
        self.values = values or []

    def set_value(self, value: str) -> None:
        """Programmatically set the selected value of the dropdown.
        
        Args:
            value (str): The string value to select.
        """
        if self.variable:
            self.variable.set(value)
        self.button.configure(text=value)

    def get_value(self) -> str:
        """Retrieve the currently selected value.
        
        Returns:
            str: The currently selected text.
        """
        return self.variable.get() if self.variable else self.button.cget("text")

    def _open_dropdown(self) -> None:
        """Calculate geometry and render the dropdown Toplevel window."""
        if self.dropdown_popup is not None:
            self._close_dropdown()
            return

        values = self.values or ["No players found"]

        self.dropdown_popup = ctk.CTkToplevel(self)
        self.dropdown_popup.overrideredirect(True)
        self.dropdown_popup.attributes("-topmost", True)

        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height()
        width = self.button.winfo_width()
        height = self.dropdown_height
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

        self.dropdown_popup.bind("<FocusOut>", lambda _e: self._close_dropdown())
        self.dropdown_popup.bind("<Escape>", lambda _e: self._close_dropdown())
        self.dropdown_popup.focus_set()

    def _select_value(self, name: str) -> None:
        """Handle a selection event from inside the dropdown.
        
        Args:
            name (str): The name of the option clicked by the user.
        """
        self.set_value(name)
        if self.command:
            self.command(name)
        self._close_dropdown()

    def _close_dropdown(self) -> None:
        """Destroy the dropdown Toplevel window if it exists."""
        if self.dropdown_popup is not None:
            self.dropdown_popup.destroy()
            self.dropdown_popup = None