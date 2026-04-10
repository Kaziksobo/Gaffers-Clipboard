"""UI frame for editing career metadata and competition settings.

This module defines CareerConfigFrame, a CustomTkinter settings view used to
manage competition lists and key career metadata fields. It provides guarded
update flows with confirmation prompts, lightweight undo affordances, and
controller-delegated persistence operations.
"""

import contextlib
import logging

import customtkinter as ctk

from src.contracts.ui import (
    BaseViewThemeProtocol,
    CareerConfigFrameControllerProtocol,
)
from src.schemas import CareerMetadata
from src.utils import capitalize_competition_name, safe_int_conversion
from src.views.base_view_frame import BaseViewFrame

logger = logging.getLogger(__name__)


class CareerConfigFrame(BaseViewFrame):
    """Settings frame for career metadata and competition management.

    The frame exposes controls for manager identity, half length, and match
    difficulty, alongside add/remove competition operations. Persistence is
    delegated to the controller while this view handles validation, prompts,
    and user feedback.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        controller: CareerConfigFrameControllerProtocol,
        theme: BaseViewThemeProtocol,
    ) -> None:
        """Build and configure the career settings interface.

        Creates metadata editors, competition list rendering controls, add/
        delete actions, and navigation controls. The constructor also
        initializes single-step undo buffers used by competition and metadata
        update flows.

        Args:
            parent (ctk.CTkFrame): Parent container that hosts this frame.
            controller (CareerConfigFrameControllerProtocol): Controller used
                for career reads, writes, and navigation.
            theme (BaseViewThemeProtocol): Theme tokens used for visual styling.
        """
        super().__init__(parent, controller, theme)
        self.controller: CareerConfigFrameControllerProtocol = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.heading = ctk.CTkLabel(
            self, text="Career Settings", font=self.fonts["title"]
        )
        self.heading.grid(row=0, column=0, pady=(10, 10))

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.container.grid_columnconfigure(0, weight=1)

        # Metadata editor (manager, half length, difficulty)
        self.meta_frame = ctk.CTkFrame(self.container)
        self.meta_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.meta_frame.grid_columnconfigure(1, weight=1)

        self.manager_label = ctk.CTkLabel(
            self.meta_frame, text="Manager Name:", font=self.fonts["body"]
        )
        self.manager_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.manager_entry = ctk.CTkEntry(self.meta_frame, font=self.fonts["body"])
        self.manager_entry.grid(row=0, column=1, sticky="ew")

        self.half_label = ctk.CTkLabel(
            self.meta_frame, text="Half Length:", font=self.fonts["body"]
        )
        self.half_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.half_entry = ctk.CTkEntry(
            self.meta_frame, font=self.fonts["body"], width=80
        )
        self.half_entry.grid(row=1, column=1, sticky="w", pady=(8, 0))

        self.diff_label = ctk.CTkLabel(
            self.meta_frame, text="Match Difficulty:", font=self.fonts["body"]
        )
        self.diff_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.diff_var = ctk.StringVar(value="Select Difficulty")
        self.diff_dropdown = ctk.CTkOptionMenu(
            self.meta_frame,
            variable=self.diff_var,
            values=[
                "Beginner",
                "Amateur",
                "Semi-Pro",
                "Professional",
                "World Class",
                "Legendary",
                "Ultimate",
            ],
            font=self.fonts["body"],
        )
        self.diff_dropdown.grid(row=2, column=1, sticky="w", pady=(8, 0))

        self.save_meta_button = ctk.CTkButton(
            self.meta_frame,
            text="Save Metadata",
            font=self.fonts["button"],
            command=self._on_save_metadata,
        )
        self.save_meta_button.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        # Style save metadata as success (green)
        with contextlib.suppress(Exception):
            self.save_meta_button.configure(
                hover_color=self.theme.semantic_colors.submit_hover
            )
        # Competitions list label
        self.comps_label = ctk.CTkLabel(
            self.container, text="Competitions:", font=self.fonts["body"]
        )
        self.comps_label.grid(row=1, column=0, sticky="w")

        # Scrollable frame holding competition entries
        self.list_frame = ctk.CTkScrollableFrame(self.container, height=250)
        self.list_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # Add competition controls
        self.add_frame = ctk.CTkFrame(self.container)
        self.add_frame.grid(row=3, column=0, sticky="ew")
        self.add_frame.grid_columnconfigure(0, weight=1)

        self.new_comp_entry = ctk.CTkEntry(
            self.add_frame,
            placeholder_text="New competition name",
            font=self.fonts["body"],
        )
        self.new_comp_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.add_comp_button = ctk.CTkButton(
            self.add_frame,
            text="Add",
            font=self.fonts["button"],
            command=self._on_add_comp,
        )
        self.add_comp_button.grid(row=0, column=1)
        # Style add as success (green)
        with contextlib.suppress(Exception):
            self.add_comp_button.configure(
                hover_color=self.theme.semantic_colors.submit_hover
            )
        self.back_button = ctk.CTkButton(
            self,
            text="Back",
            font=self.fonts["button"],
            command=lambda: self.controller.show_frame(
                self.controller.get_frame_class("MainMenuFrame")
            ),
        )
        self.back_button.grid(row=4, column=0, pady=(8, 16))

        # Undo buffers for last operations (simple single-step undo)
        self._last_deleted_comp: str | None = None
        self._last_metadata: CareerMetadata | None = None

    def on_show(self) -> None:
        """Refresh visible metadata and competitions when the frame is shown.

        Loads current career values into metadata widgets and then rebuilds the
        competitions list so the view reflects the latest persisted state each
        time it becomes active.
        """
        if meta := self.controller.get_current_career_details():
            self.manager_entry.delete(0, "end")
            self.manager_entry.insert(0, meta.manager_name)

            self.half_entry.delete(0, "end")
            self.half_entry.insert(0, str(meta.half_length))

            self.diff_var.set(meta.difficulty)

        self._refresh_competitions()

    def _refresh_competitions(self) -> None:
        """Rebuild the competitions list UI from current career metadata.

        Clears existing list rows, loads the active career competitions, and
        renders each row with a corresponding delete action. If no career is
        loaded, the list shows a fallback informational message.
        """
        for child in self.list_frame.winfo_children():
            child.destroy()

        meta: CareerMetadata | None = self.controller.get_current_career_details()
        if not meta:
            lbl = ctk.CTkLabel(self.list_frame, text="No career loaded.")
            lbl.grid(row=0, column=0)
            return

        comps: list[str] = getattr(meta, "competitions", []) or []
        for i, comp in enumerate(comps):
            row_frame = ctk.CTkFrame(self.list_frame)
            row_frame.grid(row=i, column=0, sticky="ew", pady=4, padx=4)
            row_frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(
                row_frame, text=comp, font=self.fonts["body"], anchor="w"
            )
            label.grid(row=0, column=0, sticky="w")

            delete_btn = ctk.CTkButton(
                row_frame,
                text="Delete",
                width=80,
                font=self.fonts["button"],
                command=lambda c=comp: self._on_delete_comp(c),
            )
            # Style delete as error (red)
            with contextlib.suppress(Exception):
                delete_btn.configure(
                    hover_color=self.theme.semantic_colors.remove_hover
                )
            delete_btn.grid(row=0, column=1, padx=(8, 0))

    def _on_add_comp(self) -> None:
        """Validate and add a competition, then optionally undo the action.

        Ensures the competition name is present, delegates insertion to the
        controller, refreshes list rendering, and offers an immediate undo
        action through a follow-up dialog.
        """
        name: str = self.new_comp_entry.get().strip()
        if not name:
            self.show_warning(
                "Missing Competition", "Please enter a competition name before adding."
            )
            return

        try:
            self.controller.add_competition(name)
            self.new_comp_entry.delete(0, "end")
            self._refresh_competitions()
            normalized_name = capitalize_competition_name(name)
            # Offer an undo after adding by showing a short info with Undo option
            res = self.show_info(
                "Added",
                f"Competition '{normalized_name}' added to career.",
                options=["Undo", "Close"],
            )
            if res == "Undo":
                try:
                    # Removing what was just added
                    self.controller.remove_competition(name)
                    self._refresh_competitions()
                    self.show_success(
                        "Undone", f"Addition of '{normalized_name}' undone."
                    )
                    self.on_show()  # Refresh to reflect undone state
                except Exception:
                    # If remove fails (unlikely), just log and continue
                    logger.exception("Failed to undo competition add for %s", name)
        except Exception as e:
            logger.exception("Failed to add competition: %s", e)
            self.show_error("Error", f"Failed to add competition: {e}")

    def _on_delete_comp(self, comp: str) -> None:
        """Delete a competition with confirmation and optional undo.

        Prompts the user to confirm the destructive action, removes the
        selected competition via the controller, refreshes list state, and
        provides a one-step undo path when removal succeeds.

        Args:
            comp (str): Competition name selected for removal.
        """
        # Confirm destructive action first
        confirm = self.show_warning(
            "Confirm Delete",
            (
                f"Are you sure you want to permanently remove the competition '{comp}' "
                "from this career? This cannot be undone."
            ),
            options=["Delete", "Cancel"],
        )
        if confirm != "Delete":
            return

        try:
            # Store for potential undo
            self._last_deleted_comp = comp
            self.controller.remove_competition(comp)
            self._refresh_competitions()
            # Offer undo after successful delete
            res = self.show_info(
                "Removed",
                f"Competition '{comp}' removed.",
                options=[("Undo", self.theme.semantic_colors.error), "Close"],
            )
            if res == "Undo" and self._last_deleted_comp:
                try:
                    self.controller.add_competition(self._last_deleted_comp)
                    self._last_deleted_comp = None
                    self._refresh_competitions()
                    self.show_success("Restored", "Competition restored.")
                    self.on_show()  # Refresh to reflect restored state
                except Exception:
                    logger.exception("Failed to restore competition %s", comp)
        except ValueError as ve:
            self.show_warning("Cannot Remove", str(ve))
        except Exception as e:
            logger.exception("Failed to remove competition: %s", e)
            self.show_error("Error", f"Failed to remove competition: {e}")

    def _on_save_metadata(self) -> None:
        """Validate metadata fields, confirm intent, and persist updates.

        Collects manager name, half length, and difficulty from the form,
        validates required values and bounds, captures previous metadata for
        potential undo, and asks the user to confirm before persisting.

        Persistence is delegated to a dedicated helper that centralizes success
        feedback and undo restoration behavior.
        """
        manager: str = self.manager_entry.get().strip()
        half: int | None = safe_int_conversion(self.half_entry.get().strip())
        difficulty: str = self.diff_var.get()

        missing: list[str] = []
        if not manager:
            missing.append("Manager Name")
        if half is None:
            missing.append("Half Length")
        if difficulty in {"Select Difficulty", ""}:
            missing.append("Difficulty")

        if missing:
            self.show_warning(
                "Missing Information",
                f"The following required fields are missing: {', '.join(missing)}",
            )
            return

        # Keep an explicit None-guard for static type narrowing.
        if half is None:
            return

        if not self.validate_half_length(half):
            return

        updates = {
            "manager_name": manager,
            "half_length": half,
            "difficulty": difficulty,
        }

        if prev := self.controller.get_current_career_details():
            self._last_metadata: dict[str, str | int] = {
                "manager_name": prev.manager_name,
                "half_length": prev.half_length,
                "difficulty": prev.difficulty,
            }

        confirm = self.show_warning(
            "Confirm Save",
            "Save changes to career metadata?",
            options=["Save", "Cancel"],
        )
        if confirm != "Save":
            return

        if not self._persist_updates(updates):
            # If save fails, clear the undo buffer
            # since the current state is now unknown
            self._last_metadata = None

    def _persist_updates(self, updates: dict[str, str | int]) -> bool:
        """Persist metadata updates and optionally restore prior values.

        Applies the provided metadata update payload through the controller,
        refreshes dependent UI state, and offers an undo action that restores
        previously cached metadata values.

        Args:
            updates (dict[str, str | int]): Validated metadata patch payload.

        Returns:
            bool: True when updates are persisted successfully; False when an
            error occurs during save.
        """
        try:
            self.controller.update_career_metadata(updates)
            # Offer undo after save
            res = self.show_info(
                "Saved",
                "Career metadata updated successfully.",
                options=[("Undo", self.theme.semantic_colors.error), "Close"],
            )
            self._refresh_competitions()
            if res == "Undo" and self._last_metadata:
                try:
                    self.controller.update_career_metadata(self._last_metadata)
                    self.show_success("Restored", "Previous metadata restored.")
                    self._last_metadata = None
                    self.on_show()
                except Exception:
                    logger.exception("Failed to restore metadata")
            return True
        except Exception as e:
            logger.exception("Failed to save metadata: %s", e)
            self.show_error("Error", f"Failed to save metadata: {e}")
            return False
