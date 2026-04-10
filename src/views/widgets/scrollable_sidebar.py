"""Scrollable sidebar widget for rendering buffered rows and quick actions.

This module defines ScrollableSidebar, a reusable CustomTkinter component that
displays controller-formatted row data with optional per-row removal actions
and responsive collapse behavior.
"""

import contextlib
import logging
import tkinter as tk
from collections.abc import Callable
from typing import Literal

import customtkinter as ctk

from src.contracts.ui import BaseViewThemeProtocol, PlaceGeometryValue

logger = logging.getLogger(__name__)


class ScrollableSidebar(ctk.CTkFrame):
    """Render a reusable, collapsible sidebar of controller-supplied row data.

    The widget renders selected dictionary keys as aligned columns, optionally
    attaches a per-row remove action, and recalculates column widths as the
    viewport changes. It remains presentation-only and delegates all business
    logic and state mutation to injected controller callbacks.
    """

    import contextlib

    def __init__(
        self,
        parent: ctk.CTkFrame,
        theme: BaseViewThemeProtocol,
        fonts: dict[str, ctk.CTkFont],
        display_keys: list[str],
        remove_button: bool = False,
        remove_callback: Callable[[str], None] | None = None,
        id_key: str = "id",
        width: int = 375,
        max_height: int = 400,
        column_proportions: list[float] | None = None,
        min_column_width: int = 60,
        remove_button_width: int = 92,
        responsive: bool = False,
        title: str | None = None,
        state_callback: Callable[[bool], None] | None = None,
    ) -> None:
        """Initialize sidebar configuration, sizing, and rendering state.

        Configures fixed or responsive layout behavior, validates width
        distribution inputs, captures callback dependencies, and prepares
        internal caches used for row rendering and resize handling.

        Args:
            parent (ctk.CTkFrame): The parent container widget.
            display_keys (list[str]): Dictionary keys to render as display
                columns in each row.
            remove_button (bool, optional): Whether to render a Remove button
                for each row. Defaults to False.
            remove_callback (Callable[[str], None] | None, optional): Callback
                invoked when Remove is pressed, receiving item_id. Required
                when remove_button is True. Defaults to None.
            id_key (str, optional): Key used as the unique row identifier.
                Defaults to "id".
            width (int, optional): Sidebar width in pixels for fixed mode.
                Defaults to 375.
            max_height (int, optional): Sidebar height in pixels for fixed
                mode. Defaults to 400.
            column_proportions (list[float] | None, optional): Column width
                proportions that should sum to approximately 1.0. If omitted,
                columns are distributed evenly. Defaults to None.
            min_column_width (int, optional): Minimum width for each data
                column in pixels. Defaults to 60.
            remove_button_width (int, optional): Fixed width for the remove
                button column in pixels. Defaults to 92.
            responsive (bool, optional): Whether layout size should be driven
                by parent geometry instead of fixed width and height.
                Defaults to False.
            title (str | None, optional): Sidebar title shown on the collapse
                toggle button. Defaults to None.
            state_callback (Callable[[bool], None] | None, optional): Optional
                callback invoked with collapse state changes. Defaults to None.

        Raises:
            ValueError: If column_proportions length does not match
                display_keys, proportions do not sum to approximately 1.0, or
                remove_button is enabled without remove_callback.
        """
        if responsive:
            super().__init__(parent)
        else:
            super().__init__(parent, width=width, height=max_height)

        self.parent: ctk.CTkFrame = parent
        self.theme: BaseViewThemeProtocol = theme
        self.fonts: dict[str, ctk.CTkFont] = fonts
        # store sizing/responsiveness for later layout adjustments
        self._responsive: bool = responsive
        self._width: int = width
        self._max_height: int = max_height
        self._display_keys: list[str] = display_keys
        self._remove_button: bool = remove_button
        self._remove_callback: Callable[[str], None] | None = remove_callback
        self._id_key: str = id_key
        self.title: str | None = title
        self._column_proportions: list[float] | None = column_proportions
        self._min_column_width: int = min_column_width
        self._remove_button_width: int = remove_button_width
        self._is_collapsed: bool = True

        if self._column_proportions is not None and len(
            self._column_proportions
        ) != len(self._display_keys):
            raise ValueError(
                "Length of column_proportions must match length of display_keys"
            )
        if (
            self._column_proportions is not None
            and abs(sum(self._column_proportions) - 1.0) > 0.001
        ):
            raise ValueError(
                "Values in column_proportions must sum to ~1.0 for proportional widths"
            )

        self._rows: list[tuple[ctk.CTkFrame, ctk.CTkFrame]] = []
        self._computed_column_widths: list[int] = []
        self._collapsed_height = 50  # Height when collapsed (just button)
        self._expanded_relheight = 0.85  # Height when expanded (relative)
        self._initial_place_geometry: dict[
            str, PlaceGeometryValue
        ] = {}  # Store initial place() params for collapse/expand
        # Cache last observed content viewport size to avoid thrashing updates
        self._last_viewport_size: tuple[int, int] = (0, 0)
        # Optional callback to notify controller of collapse state changes
        self._state_callback: Callable[[bool], None] | None = state_callback

        if self._remove_button and not self._remove_callback:
            raise ValueError(
                "remove_callback must be provided if remove_button is True"
            )

        self._setup_frame()

    def _setup_frame(self) -> None:
        """Build base sidebar widgets and bind resize listeners.

        Creates the collapse toggle, initializes the scrollable content area,
        applies initial collapsed state behavior, and attaches configure-event
        handlers for viewport and responsive layout updates.
        """
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Title row
        self.grid_rowconfigure(1, weight=1)  # Scrollable content row

        title_button = ctk.CTkButton(
            self,
            text=f"{self.title} ▶" if self._is_collapsed else f"{self.title} ▼",
            font=self.fonts["body"],
            command=self._toggle_collapse,
        )
        title_button.grid(row=0, column=0, pady=(10, 5))
        self._title_button = title_button

        # Create the CTkScrollableFrame with an explicit viewport size for
        # fixed-mode, and dynamic resizing for responsive mode.
        if self._responsive:
            self.content_frame = ctk.CTkScrollableFrame(self)
        else:
            self.content_frame = ctk.CTkScrollableFrame(
                self, width=self._width, height=self._max_height
            )

        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.content_frame.grid_columnconfigure(0, weight=1)

        # If the sidebar should start collapsed, hide the content frame now so
        # the initial visual state matches `self._is_collapsed`.
        if self._is_collapsed:
            try:
                self.content_frame.grid_remove()
            except Exception:
                logger.debug("Failed to grid_remove initial content_frame")
            with contextlib.suppress(Exception):
                self.configure(height=self._collapsed_height)
        # Append our resize handler without replacing CTkScrollableFrame's
        # internal scrollregion binding.
        self.content_frame.bind(
            "<Configure>", self._on_content_frame_configure, add="+"
        )

        # For responsive sidebars, listen to parent size changes and update
        # the scrollable viewport so the scrollbar reflects actual content.
        if self._responsive:
            self.bind("<Configure>", self._on_self_configure)

    def store_place_geometry(self, **kwargs: PlaceGeometryValue) -> None:
        """Store baseline place geometry used during collapse and expand.

        Call this after place() so later toggle actions can restore the
        original placement configuration.

        Args:
            **kwargs: place() geometry values such as relx, rely, relwidth,
                relheight, anchor, x, and y.
        """
        self._initial_place_geometry: dict[str, PlaceGeometryValue] = kwargs

    def get_collapse_state(self) -> bool:
        """Return whether the sidebar is currently collapsed.

        Returns:
            bool: True when collapsed; False when expanded.
        """
        return self._is_collapsed

    def set_collapse_state(self, collapse: bool) -> None:
        """Set sidebar collapse state programmatically.

        Args:
            collapse (bool): True to collapse the sidebar, False to expand it.
        """
        if collapse != self._is_collapsed:
            self._toggle_collapse()

    def populate(self, data: list[dict[str, str]]) -> None:
        """Render sidebar rows from controller-prepared data.

        Extracts display-safe values, handles optional identifier wiring for
        remove callbacks, clears prior rows, renders new rows, and reapplies
        width calculations after population.

        Args:
            data (list[dict[str, str]]): Row dictionaries to display. Each row
                should provide all keys listed in display_keys and include id_key
                when remove_button is enabled.
        """
        # remove keys not in self._display_keys
        cleaned_data: list[dict[str, str]] = []
        for item in data:
            try:
                cleaned_item: dict[str, str] = {
                    key: item[key] for key in self._display_keys
                }
                if self._remove_button:
                    cleaned_item[self._id_key] = item[self._id_key]
                cleaned_data.append(cleaned_item)
            except KeyError as e:
                missing_key: str = e.args[0]
                logger.warning(
                    f"Item {item} is missing required key "
                    f"'{missing_key}' and will be skipped."
                )

        for i in range(len(cleaned_data)):
            self.content_frame.grid_rowconfigure(i, weight=0)

        # call _add_dynamic_row with the corrected dict for each dict in the list
        self._clear_rows()
        for i, item in enumerate(cleaned_data):
            # Extract id_key if it's NOT in display_keys; otherwise keep it for display
            if self._id_key not in self._display_keys:
                item_id: str | None = item.pop(self._id_key, None)
            else:
                item_id: str | None = item.get(self._id_key, None)

            # Only pass item_id for callback if remove_button is enabled
            if not self._remove_button:
                item_id: str | None = None

            self._add_dynamic_row(item, item_id, row_index=i)

        # Recompute and apply widths after adding all rows
        self._compute_column_widths()
        self._update_row_widths()

    def _clear_rows(self) -> None:
        """Remove and destroy all currently displayed row frames."""
        for row, _ in self._rows:
            row.destroy()
        self._rows.clear()

    def _add_dynamic_row(
        self, data: dict[str, str], item_id: str | None = None, row_index: int = 0
    ) -> None:
        """Create and render one sidebar row with optional remove action.

        Builds a row container, renders each configured display column, and
        optionally appends a remove button bound to the provided item_id.

        Args:
            data (dict[str, str]): Display-key dictionary for the row.
                Must include a value for each key in display_keys.
            item_id (str | None): Unique row identifier passed to
                remove_callback when remove_button is enabled. Defaults to None.
            row_index (int): Grid row index in content_frame. Defaults to 0.

        Raises:
            ValueError: If remove_button is True but item_id is None or falsy.
        """
        if self._remove_button and not item_id:
            raise ValueError(
                "A non-null value for item_id must be "
                "given when a remove button is required"
            )

        if not data:
            return

        # Compute widths if not already computed
        if not self._computed_column_widths:
            self._compute_column_widths()

        # Create a container row frame with no internal grid layout
        row = ctk.CTkFrame(self.content_frame)
        row.grid(row=row_index, column=0, sticky="ew", padx=0, pady=2)

        # Render display columns with explicit widths
        row.grid_columnconfigure(0, weight=1)  # Single column that spans all content

        # Create internal frame to hold all cells in a row
        cells_frame = ctk.CTkFrame(row)
        cells_frame.grid(row=0, column=0, sticky="ew")

        col_idx = 0
        for key in self._display_keys:
            width: int = (
                self._computed_column_widths[col_idx]
                if col_idx < len(self._computed_column_widths)
                else 100
            )

            label = ctk.CTkLabel(
                master=cells_frame,
                text=data.get(key, ""),
                font=self.fonts["sidebar_body"],
                width=width,
                anchor="w",
            )
            label.grid(row=0, column=col_idx, sticky="w", padx=(0, 4))
            col_idx += 1

        if self._remove_button:
            if item_id is None:
                raise ValueError(
                    "A non-null value for item_id must be "
                    "given when a remove button is required"
                )
            remove_item_id: str = item_id
            remove_button = ctk.CTkButton(
                master=cells_frame,
                text="Remove",
                font=self.fonts["sidebar_button"],
                width=self._remove_button_width,
                hover_color=self.theme.semantic_colors.remove_hover,
                command=lambda current_id=remove_item_id: self._on_delete_pressed(
                    current_id
                ),
            )
            remove_button.grid(row=0, column=col_idx, sticky="e", padx=(4, 0))

        self._rows.append((row, cells_frame))

    def _on_delete_pressed(self, item_id: str) -> None:
        """Invoke the injected remove callback for the selected item.

        Args:
            item_id (str): Unique identifier of the item to remove.
        """
        if self._remove_callback:
            self._remove_callback(item_id)
        else:
            logger.error(
                "Delete button was pressed but no remove_callback is configured."
            )

    def _toggle_collapse(self) -> None:
        """Toggle collapsed state and re-apply stored placement geometry.

        Updates title-arrow affordance, shows or hides scrollable content, and
        notifies external listeners when the collapse state changes.
        """
        self._is_collapsed: bool = not self._is_collapsed

        arrow: Literal["▶", "▼"] = "▶" if self._is_collapsed else "▼"
        self._title_button.configure(text=f"{self.title} {arrow}")

        # Completely clear existing geometry constraints to prevent merging conflicts
        self.place_forget()

        # Base placement arguments that are always applied
        place_args: dict[str, float | int | str] = {
            "relx": self._initial_place_geometry.get("relx", 1.0),
            "rely": self._initial_place_geometry.get("rely", 0.0),
            "anchor": self._initial_place_geometry.get("anchor", "ne"),
            "x": self._initial_place_geometry.get("x", 0),
            "y": self._initial_place_geometry.get("y", 0),
        }

        # Safely re-apply relwidth if it was originally provided
        if "relwidth" in self._initial_place_geometry:
            place_args["relwidth"] = self._initial_place_geometry["relwidth"]

        if self._is_collapsed:
            self.content_frame.grid_remove()
            # Set the exact absolute height using CTk's approved method
            self.configure(height=self._collapsed_height)
        else:
            self.content_frame.grid()
            # Re-apply the relative height constraint for the expanded state
            if "relheight" in self._initial_place_geometry:
                place_args["relheight"] = self._initial_place_geometry["relheight"]

        # Re-place the widget (relheight is completely omitted)
        self.place(**place_args)
        # Notify external observer (controller) about the new collapsed state
        try:
            if getattr(self, "_state_callback", None):
                self._state_callback(self._is_collapsed)
        except Exception as exc:
            logger.debug(f"State callback raised an exception: {exc}")

    def _on_content_frame_configure(self, event: tk.Event) -> None:
        """Handle content frame resize by recomputing column widths.

        This handler prefers the underlying canvas viewport width (when
        available) and only triggers a recompute when the viewport size
        actually changes. This avoids repeated widget reconfigure calls
        during scroll operations which can cause the content to jump back
        to the top.
        """
        # Determine observed viewport size from the event, falling back
        # to widget queries when needed.
        try:
            event_w = int(event.width)
            event_h = int(event.height)
        except Exception:
            event_w = int(self.content_frame.winfo_width() or 0)
            event_h = int(self.content_frame.winfo_height() or 0)

        # Prefer the canvas width if CTkScrollableFrame exposes it.
        viewport_w = event_w
        with contextlib.suppress(Exception):
            parent_canvas: ctk.CTkFrame | None = getattr(
                self.content_frame, "_parent_canvas", None
            )
            if parent_canvas and parent_canvas.winfo_exists():
                canvas_w = int(parent_canvas.winfo_width() or 0)
                if canvas_w > 0:
                    viewport_w: int = canvas_w
        viewport_size: tuple[int, int] = (viewport_w, event_h)
        if viewport_size == self._last_viewport_size:
            return
        self._last_viewport_size: tuple[int, int] = viewport_size

        self._compute_column_widths()
        self._update_row_widths()

    def _on_self_configure(self, event: tk.Event) -> None:
        """Update the CTkScrollableFrame viewport when the parent frame is resized.

        This keeps the internal canvas viewport in sync with the visible area so
        the scrollbar length and scrollregion behave correctly in responsive mode.
        """
        try:
            # Title button vertical space (includes pady)
            header_h = self._title_button.winfo_height()
        except Exception:
            header_h = 30

        # Account for title padding and content_frame bottom pady
        top_padding = 15  # title pady (10 top + 5 bottom)
        bottom_padding = 10

        desired_height: int = max(
            0, event.height - header_h - top_padding - bottom_padding
        )
        desired_width: int = max(0, event.width - 20)

        try:
            self.content_frame.configure(height=desired_height, width=desired_width)
        except Exception as exc:
            logger.debug(f"Failed to configure content_frame size: {exc}")

        # Recompute column widths after viewport change
        self._compute_column_widths()
        self._update_row_widths()

    def _compute_column_widths(self) -> None:
        """Compute pixel widths for display columns from available viewport space.

        Stores computed widths in self._computed_column_widths.
        Uses configured proportions when provided, otherwise applies equal
        distribution. Enforces minimum column widths and accounts for padding,
        inter-column gaps, and remove-button column allocation.
        """
        if not self.content_frame.winfo_exists():
            return

        # Account for horizontal padding
        horizontal_pad = 20  # padx=10 on content_frame + internal spacing
        col_gap = 4  # Small gap between columns

        # Prefer the canvas viewport width (more stable inside CTkScrollableFrame)
        available_width: int | None = None
        try:
            parent_canvas: ctk.CTkFrame | None = getattr(
                self.content_frame, "_parent_canvas", None
            )
            if parent_canvas and parent_canvas.winfo_exists():
                available_width: int | None = (
                    parent_canvas.winfo_width() - horizontal_pad
                )
        except Exception:
            available_width: int | None = None

        if available_width is None or available_width <= 0:
            try:
                available_width: int | None = (
                    self.content_frame.winfo_width() - horizontal_pad
                )
            except Exception:
                available_width: int | None = None

        if not available_width or available_width <= 0:
            # fallback to configured width or a sensible default
            available_width: int | None = (
                self._width if getattr(self, "_width", None) else 375
            ) - horizontal_pad

        num_display_cols: int = len(self._display_keys)
        total_gaps: int = (
            (num_display_cols - 1) * col_gap if num_display_cols > 0 else 0
        )
        space_for_cols: int = available_width - total_gaps

        if self._remove_button:
            space_for_cols -= self._remove_button_width + col_gap

        # Compute widths based on proportions or equal distribution
        widths: list[int] = []
        if self._column_proportions:
            widths.extend(
                max(int(space_for_cols * proportion), self._min_column_width)
                for proportion in self._column_proportions
            )
        elif num_display_cols > 0:
            col_width: int = max(
                space_for_cols // num_display_cols, self._min_column_width
            )
            widths: list[int] = [col_width] * num_display_cols

        self._computed_column_widths: list[int] = widths

    def _update_row_widths(self) -> None:
        """Apply current computed widths to every rendered row."""
        for row, _ in self._rows:
            self._apply_widths_to_row(row)

    def _apply_widths_to_row(self, row: ctk.CTkFrame) -> None:  # noqa: C901
        """Apply computed column widths to a single rendered row.

        Args:
            row (ctk.CTkFrame): Row frame containing cells and optional
                remove button widgets.
        """
        if not self._computed_column_widths:
            self._compute_column_widths()

        # row is the outer frame, find cells_frame child
        children: list[ctk.CTkFrame] = list(row.winfo_children())
        if not children:
            return

        cells_frame: ctk.CTkFrame = children[
            0
        ]  # cells_frame is the first (and only) child
        cell_widgets: list[ctk.CTkFrame] = list(cells_frame.winfo_children())
        label_count: int = len(self._display_keys)

        for col_idx in range(label_count):
            if col_idx < len(cell_widgets):
                widget: ctk.CTkFrame = cell_widgets[col_idx]
                width: int = self._computed_column_widths[col_idx]
                # Avoid reconfiguring if the width is already set to reduce
                # layout churn which can interfere with canvas scrolling.
                try:
                    cur_w: int | None = widget.cget("width")
                except Exception:
                    cur_w: int | None = None

                should_set = True
                if cur_w is not None:
                    try:
                        cur_w_int = int(cur_w)
                        should_set: bool = cur_w_int != width
                    except Exception:
                        should_set = True

                if should_set:
                    try:
                        widget.configure(width=width)
                    except Exception as exc:
                        logger.debug(f"Failed to configure widget width: {exc}")

        # Update remove button if present
        if self._remove_button and len(cell_widgets) > label_count:
            remove_widget: ctk.CTkFrame = cell_widgets[label_count]
            try:
                cur_w: int | None = remove_widget.cget("width")
            except Exception:
                cur_w: int | None = None

            try:
                if cur_w is None or int(cur_w) != self._remove_button_width:
                    remove_widget.configure(width=self._remove_button_width)
            except Exception:
                try:
                    remove_widget.configure(width=self._remove_button_width)
                except Exception as exc:
                    logger.debug(f"Failed to configure remove button width: {exc}")
