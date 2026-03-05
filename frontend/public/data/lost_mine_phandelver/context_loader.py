"""
Lost Mine of Phandelver - Adventure Context Loader
Dynamically loads only relevant content based on current game state
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class LMOPContext:
    """Context loader for Lost Mine of Phandelver"""
    
    def __init__(self):
        self.adventure_dir = Path("/mnt/user-data/outputs/lost_mine_phandelver")
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load adventure.json metadata"""
        with open(self.adventure_dir / "adventure.json") as f:
            return json.load(f)
    
    def save_metadata(self):
        """Save updated metadata"""
        with open(self.adventure_dir / "adventure.json", 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _load_chapter(self, chapter_id: str) -> Dict[str, Any]:
        """Load chapter file"""
        path = self.adventure_dir / "chapters" / f"{chapter_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def _load_location(self, location_id: str) -> Dict[str, Any]:
        """Load location file"""
        path = self.adventure_dir / "locations" / f"{location_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def _load_npc(self, npc_id: str) -> Dict[str, Any]:
        """Load NPC file"""
        path = self.adventure_dir / "npcs" / f"{npc_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def get_current_context(self) -> str:
        """
        Get ONLY context needed for current situation
        Returns ~500-1500 tokens instead of full adventure!
        """
        parts = []
        
        # Current chapter overview
        chapter = self._load_chapter(self.metadata["current_part"])
        if chapter:
            parts.append(f"=== CURRENT PART: {chapter['name']} (Level {chapter['level_range']}) ===")
            parts.append(f"Overview: {chapter['overview']}")
            parts.append(f"")
        
        # Current location
        current_loc = self.metadata.get("current_location")
        if current_loc:
            location = self._load_location(current_loc)
            if location:
                parts.append(f"=== CURRENT LOCATION: {location['name']} ===")
                parts.append(f"{location['description']}")
                if 'atmosphere' in location:
                    parts.append(f"Atmosphere: {location['atmosphere']}")
                parts.append(f"")
        
        # Active quests
        active_quests = [q for q in self.metadata.get("active_quests", []) if q["status"] == "active"]
        if active_quests:
            parts.append("=== ACTIVE QUESTS ===")
            for quest in active_quests:
                parts.append(f"- {quest['name']}: {quest.get('reward', 'No reward listed')}")
            parts.append(f"")
        
        # Black Spider plot status
        if self.metadata.get("black_spider_plot"):
            plot = self.metadata["black_spider_plot"]
            parts.append("=== BLACK SPIDER PLOT STATUS ===")
            if not plot["identity_revealed"]:
                parts.append("- Identity: Unknown (mysterious villain)")
            else:
                parts.append(f"- Identity: {plot['true_name']} ({plot['race']})")
            parts.append(f"- Gundren: {plot['gundren_status']}")
            parts.append(f"- Wave Echo Cave: {'Located' if plot['wave_echo_location_known'] else 'Location unknown'}")
            parts.append(f"")
        
        # Recent events (last 5)
        events = self.metadata.get("important_events", [])
        if events:
            parts.append("=== RECENT EVENTS ===")
            for event in events[-5:]:
                parts.append(f"- {event}")
            parts.append(f"")
        
        # Party status
        parts.append(f"=== PARTY STATUS ===")
        parts.append(f"- Level: {self.metadata['party_level']}")
        parts.append(f"- Session: {self.metadata['session_number']}")
        if self.metadata.get("met_npcs"):
            parts.append(f"- Key NPCs met: {', '.join(self.metadata['met_npcs'][:5])}")
        
        return "\\n".join(parts)
    
    def get_location_details(self, area_id: Optional[str] = None) -> str:
        """Get detailed location info when players investigate"""
        current_loc = self.metadata.get("current_location")
        if not current_loc:
            return "No current location set."
        
        location = self._load_location(current_loc)
        if not location:
            return f"Location data not found for {current_loc}"
        
        parts = [f"=== {location['name'].upper()} ==="]
        parts.append(f"{location.get('description', 'No description')}")
        parts.append(f"")
        
        # If specific area requested
        if area_id and 'areas' in location:
            area = location['areas'].get(area_id)
            if area:
                parts.append(f"--- {area_id.upper()} ---")
                parts.append(area.get('description', ''))
                if 'features' in area:
                    parts.append(f"Features: {', '.join(area['features'])}")
                if 'enemies' in area and area['enemies']:
                    parts.append(f"Enemies: {area['enemies']}")
                if 'tactics' in area:
                    parts.append(f"Tactics: {area['tactics']}")
                if 'treasure' in area:
                    parts.append(f"Treasure: {area['treasure']}")
        else:
            # General location features
            if 'general_features' in location:
                parts.append("GENERAL FEATURES:")
                for key, val in location['general_features'].items():
                    parts.append(f"- {key.title()}: {val}")
                parts.append("")
            
            if 'areas' in location:
                parts.append(f"AREAS: {', '.join(location['areas'].keys())}")
        
        return "\\n".join(parts)
    
    def get_npc_info(self, npc_id: str) -> str:
        """Get NPC details when party interacts"""
        npc = self._load_npc(npc_id)
        if not npc:
            return f"NPC data not found for {npc_id}"
        
        parts = [f"=== {npc['name'].upper()} ==="]
        if 'alias' in npc:
            parts.append(f"Also known as: {npc['alias']}")
        
        parts.append(f"{npc.get('race', 'Unknown')} {npc.get('class', '')}")
        
        if 'appearance' in npc:
            parts.append(f"\\nAppearance: {npc['appearance']}")
        
        if 'personality' in npc:
            pers = npc['personality']
            parts.append(f"\\nPersonality: {', '.join(pers.get('traits', []))}")
            if 'goals' in pers:
                parts.append(f"Goals: {'; '.join(pers['goals'][:3])}")
            if 'mannerisms' in pers:
                parts.append(f"Mannerisms: {pers['mannerisms']}")
        
        if 'dialogue_examples' in npc and npc['dialogue_examples']:
            parts.append(f"\\nExample dialogue: \\\"{npc['dialogue_examples'][0]}\\\"")
        
        if 'key_information' in npc:
            parts.append(f"\\nKEY INFO:")
            for info in npc['key_information'][:5]:
                parts.append(f"- {info}")
        
        return "\\n".join(parts)
    
    # State update methods
    def update_location(self, new_location: str):
        """Update current location"""
        self.metadata["current_location"] = new_location
        if new_location not in self.metadata.get("discovered_locations", []):
            self.metadata.setdefault("discovered_locations", []).append(new_location)
        self.save_metadata()
    
    def update_part(self, new_part: str):
        """Update current adventure part"""
        self.metadata["current_part"] = new_part
        self.save_metadata()
    
    def add_event(self, event: str):
        """Add important event"""
        self.metadata.setdefault("important_events", []).append(event)
        # Keep last 20
        self.metadata["important_events"] = self.metadata["important_events"][-20:]
        self.save_metadata()
    
    def meet_npc(self, npc_id: str):
        """Track NPC encounter"""
        if npc_id not in self.metadata.get("met_npcs", []):
            self.metadata.setdefault("met_npcs", []).append(npc_id)
        self.save_metadata()
    
    def update_quest(self, quest_id: str, status: str):
        """Update quest status"""
        for quest in self.metadata.get("active_quests", []):
            if quest["id"] == quest_id:
                quest["status"] = status
                break
        self.save_metadata()
    
    def level_up(self):
        """Increment party level"""
        self.metadata["party_level"] += 1
        self.save_metadata()
    
    def next_session(self):
        """Increment session number"""
        self.metadata["session_number"] += 1
        self.save_metadata()


# Example usage and testing
if __name__ == "__main__":
    lmop = LMOPContext()
    
    print("=== CURRENT CONTEXT ===")
    print(lmop.get_current_context())
    print(f"\\nEstimated tokens: ~{len(lmop.get_current_context().split()) * 1.3:.0f}")
    
    print("\\n\\n=== EXAMPLE: Getting NPC Info ===")
    print(lmop.get_npc_info("sildar_hallwinter"))
    
    print("\\n\\n=== EXAMPLE: Updating State ===")
    lmop.update_location("cragmaw_hideout")
    lmop.add_event("Party ambushed by goblins on Triboar Trail")
    lmop.meet_npc("sildar_hallwinter")
    print("State updated!")
    
    print("\\n\\n=== UPDATED CONTEXT ===")
    print(lmop.get_current_context())
