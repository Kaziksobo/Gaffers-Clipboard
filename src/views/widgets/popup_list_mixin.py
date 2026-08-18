"""Shared CTkToplevel popup mechanics for filterable/selectable list widgets."""

import logging
import tkinter as tk

import customtkinter as ctk

from src.contracts.ui import PopupListMixinHostProtocol

logger = logging.getLogger(__name__)


class PopupListMixin:
    """Shared CTkToplevel popup rendering, positioning, and outside-click-close logic.

    Consumers must be a `ctk.CTkFrame` exposing `dropdown_popup`,
    `dropdown_height`, and `_outside_click_bind_id`, and must implement
    `_popup_anchor`, `_popup_values`, and `_on_popup_select`. See
    `PopupListMixinHostProtocol` for the full required surface. Used by
    `ScrollableDropdown` (click-to-toggle) and `AutocompleteEntry`
    (filter-as-you-type) to share popup geometry/render/close code without
    duplicating it.
    """

    def _popup_option_style(self) -> dict[str, str]:
        """Return extra CTkButton kwargs applied to each rendered option.

        Returns:
            dict[str, str]: Empty by default; override to match a trigger
                widget's theme colors (see `ScrollableDropdown`).
        """
        return {}

    def _popup_takes_focus(self) -> bool:
        """Return whether opening the popup should force keyboard focus onto it.

        Returns:
            bool: True by default, matching the original click-to-open
                behavior where the user isn't mid-typing when the popup
                appears. Override to False for a popup that must not steal
                focus from an entry the user is actively typing in (see
                `AutocompleteEntry`).
        """
        return True

    def _render_popup(self: PopupListMixinHostProtocol) -> None:
        """Ensure the popup window exists, then (re)render its option buttons."""
        self._ensure_popup_open()
        self._render_popup_options()

    def _ensure_popup_open(self: PopupListMixinHostProtocol) -> None:
        # sourcery skip: extract-method
        """Create and position the popup Toplevel window, if not already open.

        Deliberately a no-op when the popup is already open, rather than
        destroying and recreating it — recreating the window on every call
        (e.g. once per keystroke for a live-filtering caller) churns through
        real OS windows and re-triggers `focus_force`, which fights typing
        focus and can leave outside-click detection reading stale geometry.
        """
        if self.dropdown_popup is not None:
            return

        anchor = self._popup_anchor()
        logger.debug(
            f"_ensure_popup_open called. anchor_exists={anchor.winfo_exists()}"
        )

        try:
            self.dropdown_popup = ctk.CTkToplevel(self)
            self.dropdown_popup.overrideredirect(True)
            self.dropdown_popup.attributes("-topmost", True)

            x: int = anchor.winfo_rootx()
            y: int = anchor.winfo_rooty() + anchor.winfo_height()
            width: int = anchor.winfo_width()
            height: int = self.dropdown_height

            logger.debug(
                f"Computed popup geometry x={x}, y={y}, "
                f"width={width}, height={height}, "
                f"anchor_exists={anchor.winfo_exists()}, "
                f"anchor_mapped={anchor.winfo_ismapped()}"
            )

            self.dropdown_popup.geometry(f"{width}x{height}+{x}+{y}")

            container = ctk.CTkFrame(
                self.dropdown_popup, fg_color=self.cget("fg_color")
            )
            container.pack(fill="both", expand=True)

            self._popup_scroll = ctk.CTkScrollableFrame(
                container, fg_color=self.cget("fg_color"), width=width, height=height
            )
            self._popup_scroll.pack(fill="both", expand=True)

            # FocusOut on overrideredirect windows can fire immediately on Windows.
            # Use global outside-click close instead.
            self.dropdown_popup.bind("<Escape>", lambda _e: self._close_popup())
            if self._popup_takes_focus():
                self.dropdown_popup.focus_force()
            self._bind_outside_click_close()

            logger.debug("Popup window created successfully.")
        except Exception as exc:
            logger.exception(f"Failed to open popup. error='{exc}'")
            self._close_popup()

    def _render_popup_options(self: PopupListMixinHostProtocol) -> None:
        """Clear and repopulate the popup's option buttons from `_popup_values`."""
        if self._popup_scroll is None:
            return

        for child in self._popup_scroll.winfo_children():
            child.destroy()

        values: list[str] = self._popup_values()
        logger.debug(f"Rendering popup options. rendered_values_count={len(values)}")

        option_style = self._popup_option_style()
        for name in values:
            btn = ctk.CTkButton(
                self._popup_scroll,
                text=name,
                fg_color=self.cget("fg_color"),
                anchor="w",
                command=lambda n=name: self._on_popup_select(n),
                **option_style,
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _bind_outside_click_close(self: PopupListMixinHostProtocol) -> None:
        """Bind a click handler that closes only when clicking outside."""
        if self._outside_click_bind_id is not None:
            logger.debug("Outside-click handler already bound; skipping rebind.")
            return

        root: ctk.CTk = self.winfo_toplevel()
        self._outside_click_bind_id = root.bind(
            "<Button-1>", self._on_global_click, add="+"
        )
        logger.debug(
            f"Bound outside-click handler. bind_id='{self._outside_click_bind_id}'"
        )

    def _unbind_outside_click_close(self: PopupListMixinHostProtocol) -> None:
        """Unbind this widget's outside-click handler only."""
        if self._outside_click_bind_id is None:
            return

        try:
            root: ctk.CTk = self.winfo_toplevel()
            root.unbind("<Button-1>", self._outside_click_bind_id)
            logger.debug(
                f"Unbound outside-click handler. "
                f"bind_id='{self._outside_click_bind_id}'"
            )
        except Exception as exc:
            logger.exception(f"Failed to unbind outside-click handler. error='{exc}'")
        finally:
            self._outside_click_bind_id = None

    def _on_global_click(self: PopupListMixinHostProtocol, event: tk.Event) -> None:
        """Close popup only when click is outside the anchor and popup bounds."""
        if self.dropdown_popup is None or not self.dropdown_popup.winfo_exists():
            return

        ex: int = event.x_root
        ey: int = event.y_root

        px: int = self.dropdown_popup.winfo_rootx()
        py: int = self.dropdown_popup.winfo_rooty()
        pw: int = self.dropdown_popup.winfo_width()
        ph: int = self.dropdown_popup.winfo_height()

        anchor = self._popup_anchor()
        bx: int = anchor.winfo_rootx()
        by: int = anchor.winfo_rooty()
        bw: int = anchor.winfo_width()
        bh: int = anchor.winfo_height()

        in_popup: bool = (px <= ex <= px + pw) and (py <= ey <= py + ph)
        in_anchor: bool = (bx <= ex <= bx + bw) and (by <= ey <= by + bh)

        logger.debug(
            f"Global click ex={ex}, ey={ey}, "
            f"in_popup={in_popup}, in_anchor={in_anchor}, "
            f"popup_bounds=({px},{py},{pw},{ph}), anchor_bounds=({bx},{by},{bw},{bh})"
        )

        if not in_popup and not in_anchor:
            logger.debug("Click outside popup/anchor detected. Closing popup.")
            self._close_popup()

    def _close_popup(self: PopupListMixinHostProtocol) -> None:
        """Destroy the popup Toplevel window if it exists."""
        logger.debug(
            f"_close_popup called. popup_exists={self.dropdown_popup is not None}"
        )
        self._unbind_outside_click_close()
        if self.dropdown_popup is not None:
            self.dropdown_popup.destroy()
            self.dropdown_popup = None
            self._popup_scroll = None
            logger.debug("Popup destroyed.")
