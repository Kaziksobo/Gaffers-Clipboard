import customtkinter as ctk
import logging
from typing import Callable, Any, Optional, List, Dict

logger = logging.getLogger(__name__)

class ScrollableSidebar(ctk.CTkScrollableFrame):
    """A reusable, scrollable sidebar widget for displaying lists of items with optional deletion.

    This generic widget renders rows of pre-formatted data by displaying specified dictionary keys
    as columns in each row. It supports an optional unique identifier field (id_key) for tracking
    and callback purposes, which can be displayed as a column or hidden from view. An optional
    Remove button can be added to each row, firing a callback with the item's unique identifier.

    The widget maintains strict MVC separation: it only renders controller-prepared string data
    and emits item-id callbacks on user actions. All data transformation, business logic, and
    state management remain in the controller layer.
    """
    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: Dict[str, Any],
        fonts: Dict[str, ctk.CTkFont],
        display_keys: List[str],
        remove_button: bool = False,
        remove_callback: Optional[Callable[[str], None]] = None,
        id_key: str = "id",
        width: int = 375,
        height: int = 400,
        title: Optional[str] = None,
    ) -> None:
        """Initialise the ScrollableSidebar.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            display_keys (List[str]): Dictionary keys to render as display columns in each row.
            remove_button (bool, optional): Whether to display a Remove button for each row. Defaults to False.
            remove_callback (Optional[Callable[[str], None]], optional): Callback invoked when Remove is pressed, 
                receiving the item_id as argument. Required if remove_button is True. Defaults to None.
            id_key (str, optional): Dictionary key used as the unique item identifier. If present in display_keys, 
                it will be shown as a column; otherwise it is hidden but still used for deletion callbacks. Defaults to "id".
            width (int, optional): Width of the sidebar in pixels. Defaults to 375.
            height (int, optional): Height of the sidebar in pixels. Defaults to 400.
            title (Optional[str], optional): Optional title label displayed at the top of the sidebar. Defaults to None.
        """
        super().__init__(parent, width=width, height=height, fg_color=theme["colors"]["background"], label_text=title)
        self.parent = parent
        self.theme = theme
        self.fonts = fonts
        self._display_keys = display_keys
        self._remove_button = remove_button
        self._remove_callback = remove_callback
        self._id_key = id_key
        self.title = title
        
        self._rows: List[ctk.CTkFrame] = []
        
        if self._remove_button and not self._remove_callback:
            raise ValueError("remove_callback must be provided if remove_button is True")
    
    def populate(self, data: List[Dict[str, str]]) -> None:
        """Populate the sidebar with rows, rendering specified keys and handling the unique identifier.

        The id_key is always extracted for callback use (if remove_button is True),
        and is rendered as a display column if present in display_keys, otherwise hidden.
        Rows with missing required keys are logged and skipped; rendering continues for valid rows.

        Args:
            data (List[Dict[str, str]]): List of dictionaries to render as sidebar rows.
                Each dict must contain all keys in display_keys and id_key (when remove_button is enabled).
                The controller MUST ensure all values are pre-formatted strings ready for display.
        """
        # remove keys not in self._display_keys
        cleaned_data = []
        for item in data:
            try:
                cleaned_item = {key: item[key] for key in self._display_keys}
                if self._remove_button:
                    cleaned_item[self._id_key] = item[self._id_key]
                cleaned_data.append(cleaned_item)
            except KeyError as e:
                missing_key = e.args[0]
                logger.warning(f"Item {item} is missing required key '{missing_key}' and will be skipped.")
            
        # call _add_dynamic_row with the corrected dict for each dict in the list
        self._clear_rows()
        for item in cleaned_data:
            # Extract id_key if it's NOT in display_keys; otherwise keep it for display
            if self._id_key not in self._display_keys:
                item_id = item.pop(self._id_key, None)
            else:
                item_id = item.get(self._id_key, None)
            
            # Only pass item_id for callback if remove_button is enabled
            if not self._remove_button:
                item_id = None
            
            self._add_dynamic_row(item, item_id)

    def _clear_rows(self) -> None:
        """Remove and destroy all currently displayed row frames"""
        for row in self._rows:
            row.destroy()
        self._rows.clear()
    
    def _add_dynamic_row(self, data: Dict[str, str], item_id: Optional[str] = None) -> None:
        """Construct and render a single row with labels for each display key and optional remove button.

        Creates a grid-based row frame, renders one label per display key from the provided data,
        and appends an optional Remove button if remove_button is enabled. The row is then packed
        into the sidebar and tracked for future cleanup.

        Args:
            data (Dict[str, str]): Dictionary containing display-key-only data for rendering.
                Must include a value for each key in display_keys.
            item_id (Optional[str]): Unique identifier passed to the remove callback if
                remove_button is True. Defaults to None.

        Raises:
            ValueError: If remove_button is True but item_id is None or falsy.
        """
        if self._remove_button and not item_id:
            raise ValueError("A non-null value for item_id must be given when a remove button is required")

        if not data:
            return
        
        row = ctk.CTkFrame(
            self,
            fg_color=self.theme["colors"]["background"]
        )
        
        if self._remove_button:
            for i in range(len(self._display_keys) + 1):
                row.grid_columnconfigure(i, weight=1)
        else:
            for i in range(len(self._display_keys)):
                row.grid_columnconfigure(i, weight=1)
        row.grid_rowconfigure(0, weight=1)

        for col, key in enumerate(self._display_keys):
            label = ctk.CTkLabel(
                master=row,
                text=data.get(key, ""),
                font=self.fonts["sidebar_body"],
                text_color=self.theme["colors"]["primary_text"]
            )
            label.grid(row=0, column=col, sticky="w")

        if self._remove_button:
            remove_button = ctk.CTkButton(
                master=row,
                text="Remove",
                fg_color=self.theme["colors"]["button_fg"],
                text_color=self.theme["colors"]["primary_text"],
                font=self.fonts["sidebar_button"],
                command=lambda current_id=item_id: self._on_delete_pressed(current_id)
            )
            remove_button.grid(row=0, column=len(self._display_keys))

        self._rows.append(row)
        row.pack(fill="both", padx=4, pady=2)
    
    def _on_delete_pressed(self, item_id: str) -> None:
        """Trigger the injected remove calback if one exists.

        Args:
            item_id (str): The unique ID of the item to remove
        """
        if self._remove_callback:
            self._remove_callback(item_id)
        else:
            logger.error("Delete button was pressed but no remove_callback is configured.")