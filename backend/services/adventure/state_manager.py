"""
State Management for Adventure System

Handles updating adventure state (location, chapter, quests, events, etc.)
"""

from typing import Dict, Any, Optional


class StateManager:
    """Manages adventure state updates"""
    
    def __init__(self, adventure_context):
        """
        Initialize state manager
        
        Args:
            adventure_context: Reference to AdventureContext instance
        """
        self.adventure = adventure_context
    
    def update_location(self, new_location: str, validate_discovery: bool = True):
        """
        Update current location with optional validation
        
        Args:
            new_location: Location ID to set
            validate_discovery: If True, only allow moving to discovered locations
        """
        if "current_state" not in self.adventure.metadata:
            self.adventure.metadata["current_state"] = {}
        
        # Track discovered locations
        discovered = self.adventure.metadata.get("discovered_locations", [])
        if new_location not in discovered:
            self.adventure.metadata.setdefault("discovered_locations", []).append(new_location)
            # Track exploration milestone
            if hasattr(self.adventure, 'leveling'):
                self.adventure.leveling.track_exploration(f"discovered_{new_location}", new_location)
        
        self.adventure.metadata["current_state"]["location"] = new_location
        self.adventure._current_location_cache = None  # Invalidate cache
        self.adventure.save_metadata()
    
    def update_chapter(self, new_chapter: str, force: bool = False):
        """
        Update current chapter with flexible validation for sandbox adventures
        
        Args:
            new_chapter: Chapter ID to set
            force: If True, bypass validation (for DM override)
        """
        if "current_state" not in self.adventure.metadata:
            self.adventure.metadata["current_state"] = {}
        
        current_chapter = self.adventure.metadata.get("current_state", {}).get("chapter")
        
        # If force is True, allow any chapter change (DM override)
        if force:
            self.adventure.metadata["current_state"]["chapter"] = new_chapter
            self.adventure._current_chapter_cache = None
            self.adventure.save_metadata()
            return
        
        # Validate chapter progression - flexible for sandbox adventures
        if current_chapter and new_chapter:
            current_part = self._extract_part_number(current_chapter)
            new_part = self._extract_part_number(new_chapter)
            
            if current_part is not None and new_part is not None:
                # Always allow: same part, going back, or forward by 1
                if new_part > current_part + 1:
                    # Skipping ahead more than 1 part - check prerequisites
                    chapter_data = self.adventure.location_manager.load_chapter(new_chapter)
                    if chapter_data:
                        key_locations = chapter_data.get("key_locations", [])
                        discovered = self.adventure.metadata.get("discovered_locations", [])
                        party_knowledge = self.adventure.metadata.get("party_knowledge", {})
                        
                        has_discovered_location = any(
                            loc in discovered for loc in key_locations
                        )
                        
                        has_relevant_knowledge = False
                        for key, value in party_knowledge.items():
                            if value and (
                                "wave_echo" in key or "cragmaw_castle" in key or
                                "location" in key or "knows_about" in key
                            ):
                                has_relevant_knowledge = True
                                break
                        
                        # Allow if location discovered OR party has knowledge
                        # DM should validate narratively
                        if not (has_discovered_location or has_relevant_knowledge):
                            pass  # Allow but DM should ensure narrative makes sense
        
        self.adventure.metadata["current_state"]["chapter"] = new_chapter
        self.adventure._current_chapter_cache = None  # Invalidate cache
        self.adventure.save_metadata()
    
    def _extract_part_number(self, chapter_id: str) -> Optional[int]:
        """Extract part number from chapter ID (e.g., 'part1_goblin_arrows' -> 1)"""
        if chapter_id.startswith("part"):
            try:
                remaining = chapter_id[4:]  # Remove "part"
                num_str = ""
                for char in remaining:
                    if char.isdigit():
                        num_str += char
                    else:
                        break
                if num_str:
                    return int(num_str)
            except (ValueError, IndexError):
                pass
        
        # Try "ch01" format
        if chapter_id.startswith("ch"):
            try:
                num_str = chapter_id[2:]
                num_str = "".join(c for c in num_str if c.isdigit())
                if num_str:
                    return int(num_str)
            except (ValueError, IndexError):
                pass
        
        return None
    
    def add_event(self, event: str):
        """Track important event"""
        self.adventure.metadata.setdefault("important_events", []).append(event)
        # Keep only last 20 events
        self.adventure.metadata["important_events"] = self.adventure.metadata["important_events"][-20:]
        self.adventure.save_metadata()
    
    def meet_npc(self, npc_id: str):
        """Track that party met an NPC"""
        if npc_id not in self.adventure.metadata.get("met_npcs", []):
            self.adventure.metadata.setdefault("met_npcs", []).append(npc_id)
            # Track social interaction
            if hasattr(self.adventure, 'leveling'):
                self.adventure.leveling.track_social_interaction("met_npc", npc_id)
        self.adventure.save_metadata()
    
    def add_quest(self, quest: Dict[str, Any]):
        """Add a new quest"""
        self.adventure.metadata.setdefault("active_quests", []).append(quest)
        self.adventure.save_metadata()
    
    def update_quest_status(self, quest_id: str, status: str):
        """Update quest status"""
        for quest in self.adventure.metadata.get("active_quests", []):
            if isinstance(quest, dict) and quest.get("id") == quest_id:
                old_status = quest.get("status")
                quest["status"] = status
                # Track social interaction if quest completed
                if status == "completed" and old_status != "completed":
                    if hasattr(self.adventure, 'leveling'):
                        self.adventure.leveling.track_social_interaction("quest_completed", None, quest_id)
                break
        self.adventure.save_metadata()
    
    def update_party_knowledge(self, key: str, value: bool):
        """Update what the party knows"""
        self.adventure.metadata.setdefault("party_knowledge", {})[key] = value
        self.adventure.save_metadata()
    
    def update_session_number(self, session_number: int):
        """Update session number"""
        if "current_state" not in self.adventure.metadata:
            self.adventure.metadata["current_state"] = {}
        self.adventure.metadata["current_state"]["session_number"] = session_number
        self.adventure.save_metadata()
    
    def update_party_level(self, level: int):
        """Update party level"""
        if "current_state" not in self.adventure.metadata:
            self.adventure.metadata["current_state"] = {}
        self.adventure.metadata["current_state"]["party_level"] = level
        self.adventure.save_metadata()
    
    def get_accessible_locations(self) -> Dict[str, Any]:
        """
        Get list of locations that are accessible for travel/freeroaming
        
        Returns:
            Dict with discovered, current_chapter, previous_chapters, nearby locations
        """
        current_state = self.adventure.metadata.get("current_state", {})
        current_chapter_id = current_state.get("chapter")
        current_location_id = current_state.get("location")
        discovered = self.adventure.metadata.get("discovered_locations", [])
        
        result = {
            "discovered": [],
            "current_chapter": [],
            "previous_chapters": [],
            "nearby": []
        }
        
        # Get current chapter part number
        current_part = None
        if current_chapter_id:
            current_part = self._extract_part_number(current_chapter_id)
        
        # Load all location files to check their part numbers
        locations_dir = self.adventure.adventure_dir / "locations"
        if locations_dir.exists():
            for loc_file in locations_dir.glob("*.json"):
                try:
                    with open(loc_file) as f:
                        import json
                        loc_data = json.load(f)
                        loc_id = loc_data.get("id")
                        if not loc_id:
                            continue
                        
                        loc_part = loc_data.get("part")
                        
                        # Discovered locations (can always backtrack)
                        if loc_id in discovered:
                            result["discovered"].append({
                                "id": loc_id,
                                "name": loc_data.get("name", loc_id),
                                "type": loc_data.get("type", "unknown"),
                                "part": loc_part
                            })
                        
                        # Current chapter locations (can explore)
                        if current_part and loc_part == current_part:
                            if loc_id not in [d["id"] for d in result["current_chapter"]]:
                                result["current_chapter"].append({
                                    "id": loc_id,
                                    "name": loc_data.get("name", loc_id),
                                    "type": loc_data.get("type", "unknown")
                                })
                        
                        # Previous chapter locations (can backtrack if discovered)
                        if current_part and loc_part and loc_part < current_part:
                            if loc_id in discovered:
                                if loc_id not in [d["id"] for d in result["previous_chapters"]]:
                                    result["previous_chapters"].append({
                                        "id": loc_id,
                                        "name": loc_data.get("name", loc_id),
                                        "type": loc_data.get("type", "unknown"),
                                        "part": loc_part
                                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Nearby locations: same part or adjacent parts
        if current_part and locations_dir.exists():
            for loc_file in locations_dir.glob("*.json"):
                try:
                    with open(loc_file) as f:
                        import json
                        loc_data = json.load(f)
                        loc_id = loc_data.get("id")
                        loc_part = loc_data.get("part")
                        
                        if not loc_id or loc_id == current_location_id:
                            continue
                        
                        # Same part = nearby
                        if loc_part == current_part:
                            if loc_id not in [d["id"] for d in result["nearby"]]:
                                result["nearby"].append({
                                    "id": loc_id,
                                    "name": loc_data.get("name", loc_id),
                                    "type": loc_data.get("type", "unknown")
                                })
                        # Adjacent parts = potentially nearby
                        elif loc_part and current_part and abs(loc_part - current_part) == 1:
                            if loc_id not in [d["id"] for d in result["nearby"]]:
                                result["nearby"].append({
                                    "id": loc_id,
                                    "name": loc_data.get("name", loc_id),
                                    "type": loc_data.get("type", "unknown"),
                                    "part": loc_part,
                                    "note": "Adjacent chapter - may require travel"
                                })
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return result

