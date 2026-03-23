from typing import List, Dict, Any
import logging
import customtkinter as ctk
from src.exceptions import UIPopulationError

logger = logging.getLogger(__name__)

class PlayerDropdownMixin:
    """A feature pack that adds player dropdown functionality to any frame"""
    def enforce_player_database(self, only_gk: bool = False, only_outfield: bool = False, remove_on_loan: bool = False) -> List[str]:
        names = self.controller.get_all_player_names(
            only_gk=only_gk,
            only_outfield=only_outfield,
            remove_on_loan=remove_on_loan
        )
        if not names or names == ["No Players Found"]:
            self.show_warning(
                title="No players found",
                message="Add players to the library first",
                options=["Go to Library"],
            )
            self.controller.show_frame(self.controller.get_frame_class("PlayerLibraryFrame"))
            return []
        return names
    
    def refresh_player_dropdown(self, only_gk: bool = False, only_outfield: bool = False, remove_on_loan: bool = False) -> None:
        if names := self.enforce_player_database(
            only_gk=only_gk,
            only_outfield=only_outfield,
            remove_on_loan=remove_on_loan,
        ):
            self.player_dropdown.set_values(names)

class OCRDataMixin:
    """A feature pack that adds OCR data validation and processing to any frame"""
    def get_ocr_mapping(self) -> Dict[str, Dict[str, ctk.StringVar]]:
        if hasattr(self, "attr_vars"):
            return {"": self.attr_vars}
        if hasattr(self, "stats_vars"):
            return {"": self.stats_vars}
        
        return {}
    
    def populate_stats(self, stats: Dict[str, Any]) -> None:
        if not stats:
            raise UIPopulationError("No stats data provided for population")
        
        mapping = self.get_ocr_mapping()
        
        for prefix, var_dict in mapping.items():
            for key, var in var_dict.items():
                # Case A: Nested dict (e.g. stats["home"]["possession"])
                if prefix and prefix in stats and isinstance(stats[prefix], dict):
                    if key in stats[prefix]:
                        var.set(str(stats[prefix][key]))
                    else:
                        logger.warning(f"Key '{key}' not found in stats['{prefix}']")
                    
                # Case B: Flat dict (e.g. stats["possession"])
                elif not prefix and key in stats:
                    var.set(str(stats[key]))

class PerformanceSidebarMixin:
    def remove_player_from_buffer(self, player_name: str) -> None:
        self.controller.remove_player_from_buffer(player_name)
        self.refresh_performance_sidebar()
    
    def refresh_performance_sidebar(self) -> None:
        buffered_players = self.controller.get_buffered_player_performances(
            display_keys=["player_name", "positions_played"],
            id_key="player_name"
        )
        self.performance_sidebar.populate(buffered_players)

class EntryFocusMixin:
    def _theme_color(self, widget: str, key: str) -> str:
        value = ctk.ThemeManager.theme[widget][key]
        if isinstance(value, list):
            idx = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
            return value[idx]
        return value

    def apply_focus_flourishes(self, parent_widget: ctk.CTkBaseClass) -> None:
        for child in parent_widget.winfo_children():
            if isinstance(child, ctk.CTkEntry):
                child.bind(
                    "<FocusIn>",
                    lambda event, w=child: w.configure(
                        border_color=self.theme.semantic_colors.info
                    ),
                )
                child.bind(
                    "<FocusOut>",
                    lambda event, w=child: w.configure(
                        border_color=self._theme_color("CTkEntry", "border_color")
                    ),
                )
            elif isinstance(child, (ctk.CTkFrame, ctk.CTkScrollableFrame)):
                self.apply_focus_flourishes(child)

    def trigger_success_flash(self, button: ctk.CTkButton, original_text: str) -> None:
        button.configure(
            fg_color=self.theme.semantic_colors.success,
            hover_color=self.theme.semantic_colors.success,
            text="Added!"
        )
        button.after(
            1000,
            lambda: button.configure(
                fg_color=self._theme_color("CTkButton", "fg_color"),
                hover_color=self._theme_color("CTkButton", "hover_color"),
                text=original_text,
            ),
        )