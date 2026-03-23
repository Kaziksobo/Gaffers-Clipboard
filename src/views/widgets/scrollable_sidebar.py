import customtkinter as ctk
import logging
from typing import Callable, Any, Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

class ScrollableSidebar(ctk.CTkFrame):
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
        theme: Any,
        fonts: Dict[str, ctk.CTkFont],
        display_keys: List[str],
        remove_button: bool = False,
        remove_callback: Optional[Callable[[str], None]] = None,
        id_key: str = "id",
        width: int = 375,
        max_height: int = 400,
        column_proportions: Optional[List[float]] = None,
        min_column_width: int = 60,
        remove_button_width: int = 92,
        responsive: bool = False,
        title: Optional[str] = None,
    ) -> None:
        """Initialise the ScrollableSidebar.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            title (str, optional): Title label displayed at the top of the sidebar. Defaults to None.
            display_keys (List[str]): Dictionary keys to render as display columns in each row.
            remove_button (bool, optional): Whether to display a Remove button for each row. Defaults to False.
            remove_callback (Optional[Callable[[str], None]], optional): Callback invoked when Remove is pressed, 
                receiving the item_id as argument. Required if remove_button is True. Defaults to None.
            id_key (str, optional): Dictionary key used as the unique item identifier. If present in display_keys, 
                it will be shown as a column; otherwise it is hidden but still used for deletion callbacks. Defaults to "id".
            width (int, optional): Width of the sidebar in pixels. Ignored if responsive=True. Defaults to 375.
            max_height (int, optional): Maximum height of the sidebar in pixels. Ignored if responsive=True. Defaults to 400.
            column_proportions (Optional[List[float]], optional): Proportional widths for each display column 
                (must sum to ~1.0). If None, all columns get equal width. Defaults to None.
            min_column_width (int, optional): Minimum pixel width enforced for display columns. Defaults to 60.
            remove_button_width (int, optional): Fixed pixel width for the remove button column. Defaults to 92.
            responsive (bool, optional): If True, width and height are not constrained; use place() with relwidth/relheight. 
                Defaults to False.
        """
        if responsive:
            super().__init__(parent, fg_color=theme.colors.background)
        else:
            super().__init__(parent, width=width, height=max_height, fg_color=theme.colors.background)
        
        self.parent = parent
        self.theme = theme
        self.fonts = fonts
        self._display_keys = display_keys
        self._remove_button = remove_button
        self._remove_callback = remove_callback
        self._id_key = id_key
        self.title = title
        self._column_proportions = column_proportions
        self._min_column_width = min_column_width
        self._remove_button_width = remove_button_width
        self._is_collapsed = True
        
        if self._column_proportions is not None and len(self._column_proportions) != len(self._display_keys):
            raise ValueError("Length of column_proportions must match length of display_keys")
        if self._column_proportions is not None and abs(sum(self._column_proportions) - 1.0) > 0.001:
            raise ValueError("Values in column_proportions must sum to ~1.0 for proportional widths")

        self._rows: List[Tuple[ctk.CTkFrame, ctk.CTkFrame]] = []
        self._computed_column_widths: List[int] = []
        self._collapsed_height = 50  # Height when collapsed (just button)
        self._expanded_relheight = 0.85  # Height when expanded (relative)
        self._initial_place_geometry: Dict[str, Any] = {}  # Store initial place() params for collapse/expand
        
        if self._remove_button and not self._remove_callback:
            raise ValueError("remove_callback must be provided if remove_button is True")
        
        self.setup_frame()
    
    def setup_frame(self) -> None:
        """Configure the grid, add the title label, and bind resize events."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Title row
        self.grid_rowconfigure(1, weight=1)  # Scrollable content row

        title_button = ctk.CTkButton(
            self,
            text=f"{self.title} ▶" if self._is_collapsed else f"{self.title} ▼",
            font=self.fonts["body"],
            text_color=self.theme.colors.primary_text,
            fg_color=self.theme.colors.button_fg,
            bg_color=self.theme.colors.button_bg,
            command=self._toggle_collapse
        )
        title_button.grid(row=0, column=0, pady=(10, 5))
        self._title_button = title_button
        
        self.content_frame = ctk.CTkScrollableFrame(self, fg_color=self.theme.colors.background)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # Bind configure event to recompute widths when frame resizes
        self.content_frame.bind("<Configure>", self._on_content_frame_configure)
    
    def _toggle_collapse(self) -> None:
        self._is_collapsed = not self._is_collapsed
        
        arrow = "▶" if self._is_collapsed else "▼"
        self._title_button.configure(text=f"{self.title} {arrow}")
        
        # Completely clear existing geometry constraints to prevent merging conflicts
        self.place_forget()
        
        # Base placement arguments that are always applied
        place_args = {
            'relx': self._initial_place_geometry.get('relx', 1.0),
            'rely': self._initial_place_geometry.get('rely', 0.0),
            'anchor': self._initial_place_geometry.get('anchor', 'ne'),
            'x': self._initial_place_geometry.get('x', 0),
            'y': self._initial_place_geometry.get('y', 0)
        }
        
        # Safely re-apply relwidth if it was originally provided
        if 'relwidth' in self._initial_place_geometry:
            place_args['relwidth'] = self._initial_place_geometry['relwidth']
        
        if self._is_collapsed:
            self.content_frame.grid_remove()
            # Set the exact absolute height using CTk's approved method
            self.configure(height=self._collapsed_height)
            # Re-place the widget (relheight is completely omitted)
            self.place(**place_args)
        else:
            self.content_frame.grid()
            # Re-apply the relative height constraint for the expanded state
            if 'relheight' in self._initial_place_geometry:
                place_args['relheight'] = self._initial_place_geometry['relheight']
            
            self.place(**place_args)
    
    def store_place_geometry(self, **kwargs: Any) -> None:
        """Store the initial place geometry for later use during collapse/expand.
        
        Call this method after calling place() to capture the geometry parameters.
        
        Args:
            **kwargs: Place geometry parameters (relx, rely, relwidth, relheight, anchor, x, y, etc.)
        """
        self._initial_place_geometry = kwargs
    
    def get_collapse_state(self) -> bool:
        """Returns True if the sidebar is currently collapsed, False if expanded."""
        return self._is_collapsed
    
    def set_collapse_state(self, collapse: bool) -> None:
        """Programmatically set the collapse state of the sidebar.

        Args:
            collapse (bool): True to collapse the sidebar, False to expand it.
        """
        if collapse != self._is_collapsed:
            self._toggle_collapse()
    
    def _on_content_frame_configure(self, event: Any) -> None:
        """Handle content frame resize by recomputing column widths."""
        self._compute_column_widths()
        self._update_row_widths()
    
    def _compute_column_widths(self) -> None:
        """Compute pixel widths for each display column based on available space and proportions.
        
        Stores computed widths in self._computed_column_widths.
        Uses proportional widths if provided, otherwise equal distribution.
        Enforces minimum width per column and accounts for padding/gaps.
        """
        if not self.content_frame.winfo_exists():
            return

        # Account for horizontal padding
        HORIZONTAL_PAD = 20  # padx=10 on content_frame + internal spacing
        COL_GAP = 4  # Small gap between columns

        available_width = self.content_frame.winfo_width() - HORIZONTAL_PAD
        if available_width <= 0:
            available_width = 375 - HORIZONTAL_PAD

        num_display_cols = len(self._display_keys)
        total_gaps = (num_display_cols - 1) * COL_GAP if num_display_cols > 0 else 0
        space_for_cols = available_width - total_gaps

        if self._remove_button:
            space_for_cols -= self._remove_button_width + COL_GAP

        # Compute widths based on proportions or equal distribution
        widths: List[int] = []
        if self._column_proportions:
            widths.extend(
                max(int(space_for_cols * proportion), self._min_column_width)
                for proportion in self._column_proportions
            )
        elif num_display_cols > 0:
            col_width = max(space_for_cols // num_display_cols, self._min_column_width)
            widths = [col_width] * num_display_cols

        self._computed_column_widths = widths
    
    def _update_row_widths(self) -> None:
        """Update all existing row widgets with newly computed column widths."""
        for row, cells_frame in self._rows:
            self._apply_widths_to_row(row)
    
    def _apply_widths_to_row(self, row: ctk.CTkFrame) -> None:
        """Apply computed column widths to a single row's child widgets.
        
        Args:
            row: The row frame containing label and optional button widgets.
        """
        if not self._computed_column_widths:
            self._compute_column_widths()
        
        # row is the outer frame, find cells_frame child
        children = list(row.winfo_children())
        if not children:
            return
        
        cells_frame = children[0]  # cells_frame is the first (and only) child
        cell_widgets = list(cells_frame.winfo_children())
        label_count = len(self._display_keys)
        
        for col_idx in range(label_count):
            if col_idx < len(cell_widgets):
                widget = cell_widgets[col_idx]
                width = self._computed_column_widths[col_idx]
                widget.configure(width=width)
        
        # Update remove button if present
        if self._remove_button and len(cell_widgets) > label_count:
            remove_widget = cell_widgets[label_count]
            remove_widget.configure(width=self._remove_button_width)
        
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
        
        for i in range(len(cleaned_data)):
            self.content_frame.grid_rowconfigure(i, weight=0)
            
        # call _add_dynamic_row with the corrected dict for each dict in the list
        self._clear_rows()
        for i, item in enumerate(cleaned_data):
            # Extract id_key if it's NOT in display_keys; otherwise keep it for display
            if self._id_key not in self._display_keys:
                item_id = item.pop(self._id_key, None)
            else:
                item_id = item.get(self._id_key, None)
            
            # Only pass item_id for callback if remove_button is enabled
            if not self._remove_button:
                item_id = None
            
            self._add_dynamic_row(item, item_id, row_index=i)
        
        # Recompute and apply widths after adding all rows
        self._compute_column_widths()
        self._update_row_widths()

    def _clear_rows(self) -> None:
        """Remove and destroy all currently displayed row frames"""
        for row, _ in self._rows:
            row.destroy()
        self._rows.clear()
    
    def _add_dynamic_row(self, data: Dict[str, str], item_id: Optional[str] = None, row_index: int = 0) -> None:
        """Construct and render a single row with labels for each display key and optional remove button.

        Creates widgets for each display column with explicit computed widths, and places them on
        the content_frame grid for strict alignment. The row frame is tracked for future cleanup and width updates.

        Args:
            data (Dict[str, str]): Dictionary containing display-key-only data for rendering.
                Must include a value for each key in display_keys.
            item_id (Optional[str]): Unique identifier passed to the remove callback if
                remove_button is True. Defaults to None.
            row_index (int): Grid row index for placement on content_frame. Defaults to 0.

        Raises:
            ValueError: If remove_button is True but item_id is None or falsy.
        """
        if self._remove_button and not item_id:
            raise ValueError("A non-null value for item_id must be given when a remove button is required")

        if not data:
            return
        
        # Compute widths if not already computed
        if not self._computed_column_widths:
            self._compute_column_widths()
        
        # Create a container row frame with no internal grid layout
        row = ctk.CTkFrame(
            self.content_frame,
            fg_color=self.theme.colors.background
        )
        row.grid(row=row_index, column=0, sticky="ew", padx=0, pady=2)
        
        # Render display columns with explicit widths
        num_cols = len(self._display_keys) + (1 if self._remove_button else 0)
        row.grid_columnconfigure(0, weight=1)  # Single column that spans all content
        
        # Create internal frame to hold all cells in a row
        cells_frame = ctk.CTkFrame(row, fg_color=self.theme.colors.background)
        cells_frame.grid(row=0, column=0, sticky="ew")
        
        col_idx = 0
        for key in self._display_keys:
            width = self._computed_column_widths[col_idx] if col_idx < len(self._computed_column_widths) else 100
            
            label = ctk.CTkLabel(
                master=cells_frame,
                text=data.get(key, ""),
                font=self.fonts["sidebar_body"],
                text_color=self.theme.colors.primary_text,
                width=width,
                anchor="w"
            )
            label.grid(row=0, column=col_idx, sticky="w", padx=(0, 4))
            col_idx += 1

        if self._remove_button:
            remove_button = ctk.CTkButton(
                master=cells_frame,
                text="Remove",
                fg_color=self.theme.colors.button_fg,
                text_color=self.theme.colors.primary_text,
                font=self.fonts["sidebar_button"],
                width=self._remove_button_width,
                command=lambda current_id=item_id: self._on_delete_pressed(current_id)
            )
            remove_button.grid(row=0, column=col_idx, sticky="e", padx=(4, 0))

        self._rows.append((row, cells_frame))
    
    def _on_delete_pressed(self, item_id: str) -> None:
        """Trigger the injected remove calback if one exists.

        Args:
            item_id (str): The unique ID of the item to remove
        """
        if self._remove_callback:
            self._remove_callback(item_id)
        else:
            logger.error("Delete button was pressed but no remove_callback is configured.")
    