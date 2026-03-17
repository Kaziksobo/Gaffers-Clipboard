import customtkinter as ctk
from typing import Callable, Any, Optional, List, Dict

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
        pass
    
    def _clear_rows(self) -> None:
        """Remove and destroy all currently displayed row frames"""
        pass
    
    def _add_dynamic_row(self, item_id: str, display_values: List[str]) -> None:
        """Contruct a row with dynamic labels and an optional delete button.

        Args:
            item_id (str): The unique ID for the callback
            display_values (List[str]): The pre-extracted and pre-formatted values to display as labels in the row, 
                in the same order as display_keys
        """
        pass
    
    def _on_delete_pressed(self, item_id: str) -> None:
        """Trigger the injected remove calback if one exists.

        Args:
            item_id (str): The unique ID of the item to remove
        """
        self._remove_callback(item_id)