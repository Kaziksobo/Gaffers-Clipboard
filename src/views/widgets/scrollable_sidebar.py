import customtkinter as ctk
import logging
from typing import Callable, Any, Optional, List, Dict

logger = logging.getLogger(__name__)

class ScrollableSidebar(ctk.CTkScrollableFrame):
    """A generic, resuable scrollable sidebar widget for siaplying buffered items.

    This widget dynamically generates row labels based on a provided list of keys.
    It supports optional titles and optional deletion callbacks, maintaining strict 
    MVC separation by relying purely on Controller-formatted string data.
    """
    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: Dict[str, Any],
        display_keys: List[str],
        remove_button: bool = False,
        remove_callback: Optional[Callable[[str], None]] = None,
        id_key: str = "id",
        width: int = 200,
        height: int = 400,
        title: Optional[str] = None,
    ) -> None:
        """Initialise the ScollableSidebar

        Args:
            parent (ctk.CTkFrame): The parent container widget
            display_keys (List[str]): The exact dictionary keys from the data to display as labels
            remove_button (bool, optional): Whether to display a remove button for each item. Defaults to False.
            remove_callback (Optional[Callable[[str], None]], optional): The callback function to call when an item is removed (required if remove_button is True). Defaults to None.
            id_key (str, optional): The dictionary key to use as the unique identifier for each item. Defaults to "id".
            width (int, optional): The width of the sidebar. Defaults to 200.
            height (int, optional): The height of the sidebar. Defaults to 400.
            title (Optional[str], optional): The title of the sidebar. Defaults to None.
        """
        super().__init__(parent, width=width, height=height, fg_color=theme["colors"]["background"], label_text=title)
        self.parent = parent
        self.theme = theme
        self._display_keys = display_keys
        self._remove_button = remove_button
        self._remove_callback = remove_callback
        self._id_key = id_key
        self.title = title
        
        self._rows: List[ctk.CTkFrame] = []
        
        if self._remove_button and not self._remove_callback:
            raise ValueError("remove_callback must be provided if remove_button is True")
    
    def populate(self, data: List[Dict[str, str]]) -> None:
        """Populate the sidebar dynamically based on the configured keys

        Args:
            data (List[Dict[str, str]]): A list of dictionaries containing the data to display.
                Each dictionary should contain the keys specified in display_keys and id_key.
                The controller MUST ensure all data values are pre-formatted strings ready for display.
        """
        # Check if every dict has self._display_keys. if  not, remove the offending dict and log a warning

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
            item_id = item.pop(self._id_key, None) if self._remove_button else None
            self._add_dynamic_row(item, item_id)

    def _clear_rows(self) -> None:
        """Remove and destroy all currently displayed row frames"""
        for row in self._rows:
            row.destroy()
        self._rows.clear()
    
    def _add_dynamic_row(self, data: Dict[str, str], item_id: Optional[str] = None) -> None:
        """Contruct a row with dynamic labels and an optional delete button.

        Args:
            data (Dict[str, str]): The data dict containing only the keys specified in display_keys
            item_id (Optional[str]): The unique ID for the callback, required if remove_button is True
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
                font=self.theme["fonts"]["body"],
                text_color=self.theme["colors"]["primary_text"]
            )
            label.grid(row=0, column=col, sticky="w")

        if self._remove_button:
            remove_button = ctk.CTkButton(
                master=row,
                text="Remove",
                fg_color=self.theme["colors"]["button_fg"],
                text_color=self.theme["colors"]["primary_text"],
                font=self.theme["fonts"]["button"],
                command=lambda current_id=item_id: self._on_delete_pressed(current_id)
            )
            remove_button.grid(row=0, column=len(self._display_keys))

        self._rows.append(row)
        row.pack(fill="x", padx=4, pady=2)
    
    def _on_delete_pressed(self, item_id: str) -> None:
        """Trigger the injected remove calback if one exists.

        Args:
            item_id (str): The unique ID of the item to remove
        """
        if self._remove_callback:
            self._remove_callback(item_id)
        else:
            logger.error("Delete button was pressed but no remove_callback is configured.")