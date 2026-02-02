import customtkinter as ctk

class ScrollableDropdown(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        theme: dict,
        values=None,
        variable: ctk.StringVar | None = None,
        width: int = 350,
        dropdown_height: int = 200,
        placeholder: str = "Click here to select player",
        command=None
    ) -> None:
        super().__init__(parent, fg_color=theme["colors"]["background"])
        self.theme = theme
        self.values = values or []
        self.variable = variable or ctk.StringVar(value=placeholder)
        self.placeholder = placeholder
        self.command = command
        self.dropdown_height = dropdown_height
        self.dropdown_popup = None

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

    def set_values(self, values: list[str]) -> None:
        self.values = values or []

    def set_value(self, value: str) -> None:
        self.variable.set(value)
        self.button.configure(text=value)

    def get_value(self) -> str:
        return self.variable.get()

    def _open_dropdown(self) -> None:
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
        self.set_value(name)
        if self.command:
            self.command(name)
        self._close_dropdown()

    def _close_dropdown(self) -> None:
        if self.dropdown_popup is not None:
            self.dropdown_popup.destroy()
            self.dropdown_popup = None