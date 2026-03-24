import contextlib
import customtkinter as ctk
import logging
from typing import Any, List

from src.views.base_view_frame import BaseViewFrame
from src.utils import safe_int_conversion

logger = logging.getLogger(__name__)


class CareerConfigFrame(BaseViewFrame):
    """Simple career settings frame for managing competitions."""

    def __init__(self, parent: ctk.CTkFrame, controller: Any, theme: Any) -> None:
        super().__init__(parent, controller, theme)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.heading = ctk.CTkLabel(self, text="Career Settings", font=self.fonts["title"])
        self.heading.grid(row=0, column=0, pady=(10, 10))

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.container.grid_columnconfigure(0, weight=1)

        # Metadata editor (manager, half length, difficulty)
        self.meta_frame = ctk.CTkFrame(self.container)
        self.meta_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        self.meta_frame.grid_columnconfigure(1, weight=1)

        self.manager_label = ctk.CTkLabel(self.meta_frame, text="Manager Name:", font=self.fonts["body"])
        self.manager_label.grid(row=0, column=0, sticky="w", padx=(0,8))
        self.manager_entry = ctk.CTkEntry(self.meta_frame, font=self.fonts["body"])
        self.manager_entry.grid(row=0, column=1, sticky="ew")

        self.half_label = ctk.CTkLabel(self.meta_frame, text="Half Length:", font=self.fonts["body"])
        self.half_label.grid(row=1, column=0, sticky="w", padx=(0,8), pady=(8,0))
        self.half_entry = ctk.CTkEntry(self.meta_frame, font=self.fonts["body"], width=80)
        self.half_entry.grid(row=1, column=1, sticky="w", pady=(8,0))

        self.diff_label = ctk.CTkLabel(self.meta_frame, text="Match Difficulty:", font=self.fonts["body"])
        self.diff_label.grid(row=2, column=0, sticky="w", padx=(0,8), pady=(8,0))
        self.diff_var = ctk.StringVar(value="Select Difficulty")
        self.diff_dropdown = ctk.CTkOptionMenu(self.meta_frame, variable=self.diff_var, values=["Beginner", "Amateur", "Semi-Pro", "Professional", "World Class", "Legendary", "Ultimate"], font=self.fonts["body"])
        self.diff_dropdown.grid(row=2, column=1, sticky="w", pady=(8,0))

        self.save_meta_button = ctk.CTkButton(self.meta_frame, text="Save Metadata", font=self.fonts["button"], command=self.on_save_metadata)
        self.save_meta_button.grid(row=3, column=0, columnspan=2, pady=(10,0))
        # Style save metadata as success (green)
        with contextlib.suppress(Exception):
            self.save_meta_button.configure(hover_color=self.theme.semantic_colors.submit_hover)
        # Competitions list label
        self.comps_label = ctk.CTkLabel(self.container, text="Competitions:", font=self.fonts["body"])
        self.comps_label.grid(row=1, column=0, sticky="w")

        # Scrollable frame holding competition entries
        self.list_frame = ctk.CTkScrollableFrame(self.container, height=250)
        self.list_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 8))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # Add competition controls
        self.add_frame = ctk.CTkFrame(self.container)
        self.add_frame.grid(row=3, column=0, sticky="ew")
        self.add_frame.grid_columnconfigure(0, weight=1)

        self.new_comp_entry = ctk.CTkEntry(self.add_frame, placeholder_text="New competition name", font=self.fonts["body"])
        self.new_comp_entry.grid(row=0, column=0, sticky="ew", padx=(0,8))

        self.add_comp_button = ctk.CTkButton(self.add_frame, text="Add", font=self.fonts["button"], command=self.on_add_comp)
        self.add_comp_button.grid(row=0, column=1)
        # Style add as success (green)
        with contextlib.suppress(Exception):
            self.add_comp_button.configure(hover_color=self.theme.semantic_colors.submit_hover)
        self.back_button = ctk.CTkButton(self, text="Back", font=self.fonts["button"], command=lambda: self.controller.show_frame(self.controller.get_frame_class("MainMenuFrame")))
        self.back_button.grid(row=4, column=0, pady=(8, 16))

        # Undo buffers for last operations (simple single-step undo)
        self._last_deleted_comp: str | None = None
        self._last_metadata: dict | None = None

    def on_show(self) -> None:
        if meta := self.controller.get_current_career_details():
            self.manager_entry.delete(0, 'end')
            self.manager_entry.insert(0, meta.manager_name)

            self.half_entry.delete(0, 'end')
            self.half_entry.insert(0, str(meta.half_length))

            self.diff_var.set(meta.difficulty)

        self.refresh_competitions()

    def refresh_competitions(self) -> None:
        """Reload competition list from current career metadata and render UI."""
        for child in self.list_frame.winfo_children():
            child.destroy()

        meta = self.controller.get_current_career_details()
        if not meta:
            lbl = ctk.CTkLabel(self.list_frame, text="No career loaded.")
            lbl.grid(row=0, column=0)
            return

        comps: List[str] = getattr(meta, "competitions", []) or []
        for i, comp in enumerate(comps):
            row_frame = ctk.CTkFrame(self.list_frame)
            row_frame.grid(row=i, column=0, sticky="ew", pady=4, padx=4)
            row_frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(row_frame, text=comp, font=self.fonts["body"], anchor="w")
            label.grid(row=0, column=0, sticky="w")

            delete_btn = ctk.CTkButton(row_frame, text="Delete", width=80, font=self.fonts["button"], command=lambda c=comp: self.on_delete_comp(c))
            # Style delete as error (red)
            with contextlib.suppress(Exception):
                delete_btn.configure(hover_color=self.theme.semantic_colors.remove_hover)
            delete_btn.grid(row=0, column=1, padx=(8,0))

    def on_add_comp(self) -> None:
        name = self.new_comp_entry.get().strip()
        if not name:
            self.show_warning("Missing Competition", "Please enter a competition name before adding.")
            return

        try:
            self.controller.add_competition(name)
            self.new_comp_entry.delete(0, 'end')
            self.refresh_competitions()
            # Offer an undo after adding by showing a short info with Undo option
            res = self.show_info("Added", f"Competition '{name.title()}' added to career.", options=["Undo", "Close"])
            if res == "Undo":
                try:
                    # Removing what was just added
                    self.controller.remove_competition(name)
                    self.refresh_competitions()
                    self.show_success("Undone", f"Addition of '{name.title()}' undone.")
                except Exception:
                    # If remove fails (unlikely), just log and continue
                    logger.exception("Failed to undo competition add for %s", name)
        except Exception as e:
            logger.exception("Failed to add competition: %s", e)
            self.show_error("Error", f"Failed to add competition: {e}")

    def on_delete_comp(self, comp: str) -> None:
        # Confirm destructive action first
        confirm = self.show_warning(
            "Confirm Delete",
            f"Are you sure you want to permanently remove the competition '{comp}' from this career? This cannot be undone.",
            options=["Delete", "Cancel"]
        )
        if confirm != "Delete":
            return

        try:
            # Store for potential undo
            self._last_deleted_comp = comp
            self.controller.remove_competition(comp)
            self.refresh_competitions()
            # Offer undo after successful delete
            res = self.show_info("Removed", f"Competition '{comp}' removed.", options=[("Undo", self.theme.semantic_colors.error), "Close"])
            if res == "Undo" and self._last_deleted_comp:
                try:
                    self.controller.add_competition(self._last_deleted_comp)
                    self._last_deleted_comp = None
                    self.refresh_competitions()
                    self.show_success("Restored", "Competition restored.")
                except Exception:
                    logger.exception("Failed to restore competition %s", comp)
        except ValueError as ve:
            self.show_warning("Cannot Remove", str(ve))
        except Exception as e:
            logger.exception("Failed to remove competition: %s", e)
            self.show_error("Error", f"Failed to remove competition: {e}")

    def on_save_metadata(self) -> None:
        manager = self.manager_entry.get().strip()
        half = safe_int_conversion(self.half_entry.get().strip())
        difficulty = self.diff_var.get()

        missing = []
        if not manager:
            missing.append("Manager Name")
        if not half:
            missing.append("Half Length")
        if difficulty in ["Select Difficulty", ""]:
            missing.append("Difficulty")

        if missing:
            self.show_warning("Missing Information", f"The following required fields are missing: {', '.join(missing)}")
            return

        # Validate half length bounds
        if half < 4 or half > 20:
            self.show_warning("Invalid Half Length", "Half length must be between 4 and 20 minutes.")
            return

        updates = {
            "manager_name": manager,
            "half_length": int(half),
            "difficulty": difficulty
        }

        if prev := self.controller.get_current_career_details():
            self._last_metadata = {
                "manager_name": prev.manager_name,
                "half_length": prev.half_length,
                "difficulty": prev.difficulty,
            }

        confirm = self.show_warning(
            "Confirm Save",
            "Save changes to career metadata?",
            options=["Save", "Cancel"]
        )
        if confirm != "Save":
            return

        try:
            self.controller.update_career_metadata(updates)
            # Offer undo after save
            res = self.show_info("Saved", "Career metadata updated successfully.", options=[("Undo", self.theme.semantic_colors.error), "Close"])
            self.refresh_competitions()
            if res == "Undo" and self._last_metadata:
                try:
                    self.controller.update_career_metadata(self._last_metadata)
                    self.show_success("Restored", "Previous metadata restored.")
                    self._last_metadata = None
                    self.on_show()
                except Exception:
                    logger.exception("Failed to restore metadata")
        except Exception as e:
            logger.exception("Failed to save metadata: %s", e)
            self.show_error("Error", f"Failed to save metadata: {e}")
