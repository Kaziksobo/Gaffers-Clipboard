from pathlib import Path
import json
import time

class DataManager:
    def __init__(self, data_folder: Path):
        self.data_folder = data_folder
        self.data_folder.mkdir(exist_ok=True)
        
        self.players_path = self.data_folder / "players.json"
        self.matches_path = self.data_folder / "matches.json"
        
        self.players = self._load_json(self.players_path, default=[])
        self.matches = self._load_json(self.matches_path, default=[])
    
    def _load_json(self, path: Path, default):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default
    
    def _save_json(self, path: Path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    
    def add_or_update_player(self, player_ui_data: dict, position: str, season: str):
        
        # Check if player already exists based on name to update them
        # May end up changing this to use ids in the future
        full_name = player_ui_data.get("name").strip()
        existing_player = next((p for p in self.players if p.get("name").strip() == full_name), None)
        
        non_attributes = ["name", "age", "height", "weight", "country"]
        
        attributes = {k: v for k, v in player_ui_data.items() if k not in non_attributes}
        attributes_snapshot = {
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "season": season,
            **attributes
        }
        
        if existing_player:
            existing_player["attribute_history"].append(attributes_snapshot)
        else:
            new_player = {
                "id": self._generate_player_id(self.players),
                "name": full_name,
                "nationality": player_ui_data.get("country").strip(),
                "age": player_ui_data.get("age").strip(),
                "height": player_ui_data.get("height").strip(),
                "weight": player_ui_data.get("weight").strip(),
                "position": position,
                "attribute_history": [attributes_snapshot]
            }
            self.players.append(new_player)
        self._save_json(self.players_path, self.players)
    
    def _generate_player_id(self, collection: list) -> int:
        if not collection:
            return 1
        max_id = max(int(item.get("id", 0)) for item in collection)
        return max_id + 1