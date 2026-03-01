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