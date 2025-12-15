"""
Adventure Context Loader - Main Class

Ultra-efficient adventure context loader that manages modular adventure structure.
Uses three-tier context system: minimal, standard, detailed.

Based on ADVENTURE_STRUCTURE_GUIDE.md and OPTIMIZATION_GUIDE.md
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from .location_manager import LocationManager
from .state_manager import StateManager


class AdventureContext:
    """
    Ultra-efficient adventure context loader
    
    Manages modular adventure structure (chapters, locations, NPCs)
    and loads only what's needed for each turn.
    """
    
    def __init__(self, adventure_name: str):
        """
        Initialize adventure context loader
        
        Args:
            adventure_name: Name of adventure folder (e.g., "lost_mines_of_phandelver")
        """
        # Support both backend/adventures and frontend/public/data paths
        backend_path = Path(__file__).parent.parent.parent / "adventures" / adventure_name
        frontend_path = Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "data" / adventure_name
        
        if backend_path.exists():
            self.adventure_dir = backend_path
        elif frontend_path.exists():
            self.adventure_dir = frontend_path
        else:
            raise FileNotFoundError(
                f"Adventure '{adventure_name}' not found in:\n"
                f"  - {backend_path}\n"
                f"  - {frontend_path}"
            )
        
        self.metadata = self._load_metadata()
        
        # Cache frequently accessed data
        self._current_chapter_cache = None
        self._current_location_cache = None
        
        # Initialize managers
        self.location_manager = LocationManager(self.adventure_dir)
        self.state_manager = StateManager(self)
        
        # Initialize leveling system
        from ..leveling_system import LevelingSystem
        self.leveling = LevelingSystem(self)
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load adventure metadata (state tracking)"""
        metadata_path = self.adventure_dir / "adventure.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Adventure metadata not found: {metadata_path}")
        
        with open(metadata_path) as f:
            return json.load(f)
    
    def save_metadata(self):
        """Save updated adventure metadata"""
        with open(self.adventure_dir / "adventure.json", 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    # ========================================================================
    # Three-Tier Context System (Optimization)
    # ========================================================================
    
    def get_minimal_context(self) -> str:
        """
        BARE MINIMUM context - use for most turns
        Target: 200-400 tokens
        
        Use for: Simple actions (attack, move, take item)
        """
        parts = []
        
        current_state = self.metadata.get("current_state", {})
        
        # Adventure name
        parts.append(f"**{self.metadata['name']}**")
        
        # Current chapter & level
        chapter = self._get_chapter()
        if chapter:
            parts.append(f"Chapter: {chapter.get('name', 'Unknown')}")
        
        # Get party level from current_state or root level
        party_level = current_state.get('party_level') or self.metadata.get('party_level', 1)
        parts.append(f"Level: {party_level}")
        
        # Location (compressed)
        location = self._get_location()
        if location:
            parts.append(f"Location: {location.get('name', 'Unknown')}")
        
        # Active quest (primary only)
        active = [q for q in self.metadata.get("active_quests", []) if isinstance(q, dict)]
        if active:
            parts.append(f"Quest: {active[0].get('name', 'Quest')}")
        
        return "\n".join(parts)
    
    def get_standard_context(self) -> str:
        """
        STANDARD context - use when player needs orientation
        Target: 400-800 tokens
        
        Use for: Looking around, exploring, scene transitions
        """
        parts = []
        
        # Adventure header
        parts.append(f"=== {self.metadata['name']} ===")
        if self.metadata.get('description'):
            parts.append(self.metadata['description'][:200] + "...")
        parts.append("")
        
        # Chapter overview (compressed)
        chapter = self._get_chapter()
        if chapter:
            parts.append(f"**Chapter:** {chapter.get('name', 'Unknown')}")
            if chapter.get('overview'):
                parts.append(chapter['overview'][:300] + "...")
            parts.append("")
        
        # Location (compressed)
        location = self._get_location()
        if location:
            parts.append(f"**Location:** {location.get('name', 'Unknown')}")
            if location.get('description'):
                parts.append(location['description'][:200] + "...")
            if location.get('atmosphere'):
                parts.append(f"_Atmosphere: {location['atmosphere'][:150]}_")
            parts.append("")
        
        # Accessible locations for freeroaming/backtracking
        accessible = self.get_accessible_locations()
        if accessible["discovered"] or accessible["current_chapter"]:
            parts.append("**Accessible Locations:**")
            if accessible["discovered"]:
                discovered_names = [loc["name"] for loc in accessible["discovered"][:5]]
                parts.append(f"  Previously visited: {', '.join(discovered_names)}")
            if accessible["current_chapter"]:
                chapter_names = [loc["name"] for loc in accessible["current_chapter"][:5]]
                parts.append(f"  In this area: {', '.join(chapter_names)}")
            parts.append("")
        
        # Active quests (bullet list)
        active_quests = self.metadata.get("active_quests", [])
        if active_quests:
            parts.append("**Active Quests:**")
            for quest in active_quests[:3]:  # Max 3
                if isinstance(quest, dict):
                    parts.append(f"  - {quest.get('name', 'Quest')}")
            parts.append("")
        
        # Recent events (last 3)
        events = self.metadata.get("important_events", [])
        if events:
            parts.append("**Recent Events:**")
            for event in events[-3:]:
                parts.append(f"  - {event}")
        
        return "\n".join(parts)
    
    def get_detailed_context(self) -> str:
        """
        DETAILED context - only when player explicitly asks for recap
        Target: 800-1500 tokens
        
        Use for: "Remind me what's happening", session start
        """
        parts = []
        
        # Full adventure info
        parts.append(f"=== {self.metadata['name']} ===")
        parts.append(self.metadata.get('description', ''))
        if self.metadata.get('setting'):
            parts.append(f"_Setting: {self.metadata['setting']}_")
        parts.append("")
        
        # Chapter details
        chapter = self._get_chapter()
        if chapter:
            parts.append(f"## {chapter.get('name', 'Current Chapter')}")
            parts.append(chapter.get('overview', ''))
            
            # Handle both list and dict formats for objectives
            if chapter.get('objectives'):
                objectives = chapter['objectives']
                parts.append("\n**Objectives:**")
                if isinstance(objectives, list):
                    for obj in objectives:
                        if isinstance(obj, dict):
                            parts.append(f"  - {obj.get('description', str(obj))}")
                        else:
                            parts.append(f"  - {obj}")
            parts.append("")
        
        # Full location info
        location = self._get_location()
        if location:
            parts.append(f"## {location.get('name', 'Current Location')}")
            parts.append(location.get('description', ''))
            
            if location.get('atmosphere'):
                parts.append(f"\n_Atmosphere: {location['atmosphere']}_")
            
            # Areas available
            if location.get('areas'):
                parts.append(f"\n**Areas:** {', '.join(location['areas'].keys())}")
            parts.append("")
        
        # All active quests with details
        active_quests = self.metadata.get("active_quests", [])
        if active_quests:
            parts.append("## Active Quests")
            for quest in active_quests:
                if isinstance(quest, dict):
                    parts.append(f"\n**{quest.get('name', 'Quest')}**")
                    if quest.get('description'):
                        parts.append(quest['description'])
                    if quest.get('giver'):
                        parts.append(f"_From: {quest['giver']}_")
                    if quest.get('reward'):
                        parts.append(f"_Reward: {quest['reward']}_")
        parts.append("")
        
        # Met NPCs
        met_npcs = self.metadata.get("met_npcs", [])
        if met_npcs:
            parts.append("## Known NPCs")
            parts.append(", ".join(met_npcs[:10]))  # Max 10
            parts.append("")
        
        # Important events (last 5)
        events = self.metadata.get("important_events", [])
        if events:
            parts.append("## Recent Events")
            for event in events[-5:]:
                parts.append(f"  - {event}")
        
        # Black Spider plot (if exists - Lost Mines specific)
        if self.metadata.get("black_spider_plot"):
            plot = self.metadata["black_spider_plot"]
            parts.append("\n## Black Spider Plot")
            if not plot.get("identity_revealed", False):
                parts.append("  - Identity: Unknown villain")
            else:
                parts.append(f"  - Identity: {plot.get('true_name', 'Unknown')} ({plot.get('race', 'unknown')})")
            parts.append(f"  - Gundren: {plot.get('gundren_status', 'unknown')}")
            parts.append(f"  - Sildar: {plot.get('sildar_status', 'unknown')}")
            if plot.get("wave_echo_location_known"):
                parts.append("  - Wave Echo Cave location: Known")
            parts.append("")
        
        # Rockseeker brothers (if exists - Lost Mines specific)
        if self.metadata.get("rockseeker_brothers"):
            brothers = self.metadata["rockseeker_brothers"]
            parts.append("## Rockseeker Brothers")
            for name, info in brothers.items():
                if isinstance(info, dict):
                    parts.append(f"  - {name.title()}: {info.get('status', 'unknown')} ({info.get('location', 'unknown')})")
            parts.append("")
        
        # Faction standings (if exists)
        if self.metadata.get("faction_standings"):
            factions = self.metadata["faction_standings"]
            significant = {k: v for k, v in factions.items() if v != 0}
            if significant:
                parts.append("## Faction Standings")
                for faction, standing in significant.items():
                    faction_name = faction.replace("_", " ").title()
                    parts.append(f"  - {faction_name}: {standing}")
                parts.append("")
        
        # Party knowledge (if exists)
        if self.metadata.get("party_knowledge"):
            knowledge = self.metadata["party_knowledge"]
            known_facts = [k.replace("knows_", "").replace("_", " ").title() 
                          for k, v in knowledge.items() if v]
            if known_facts:
                parts.append("## Party Knowledge")
                for fact in known_facts:
                    parts.append(f"  - {fact}")
        
        return "\n".join(parts)
    
    # ========================================================================
    # On-Demand Loading (delegates to LocationManager)
    # ========================================================================
    
    def get_location_details(self, location_id: Optional[str] = None, area_id: Optional[str] = None) -> str:
        """
        COMPRESSED location info - only load when investigating
        Target: 100-300 tokens
        """
        if location_id:
            location = self.location_manager.load_location(location_id)
        else:
            location = self._get_location()
        
        return self.location_manager.get_location_details(location, area_id)
    
    def get_npc_info(self, npc_id: str) -> str:
        """
        COMPRESSED NPC info - only load when interacting
        Target: 150-250 tokens
        """
        npc = self.location_manager.load_npc(npc_id)
        if not npc:
            return f"NPC '{npc_id}' not found."
        
        return self.location_manager.get_npc_info(npc)
    
    def get_encounter_details(self, location_id: str, area_id: str) -> Optional[Dict[str, Any]]:
        """Get encounter details for a specific area"""
        location = self.location_manager.load_location(location_id)
        if not location or 'areas' not in location:
            return None
        
        if area_id in location['areas']:
            area = location['areas'][area_id]
            return area.get('encounters')
        
        return None
    
    # ========================================================================
    # State Management (delegates to StateManager)
    # ========================================================================
    
    def update_location(self, new_location: str, validate_discovery: bool = True):
        """Update current location"""
        self.state_manager.update_location(new_location, validate_discovery)
    
    def update_chapter(self, new_chapter: str, force: bool = False):
        """Update current chapter"""
        self.state_manager.update_chapter(new_chapter, force)
    
    def add_event(self, event: str):
        """Track important event"""
        self.state_manager.add_event(event)
    
    def meet_npc(self, npc_id: str):
        """Track that party met an NPC"""
        self.state_manager.meet_npc(npc_id)
    
    def add_quest(self, quest: Dict[str, Any]):
        """Add a new quest"""
        self.state_manager.add_quest(quest)
    
    def update_quest_status(self, quest_id: str, status: str):
        """Update quest status"""
        self.state_manager.update_quest_status(quest_id, status)
    
    def update_party_knowledge(self, key: str, value: bool):
        """Update what the party knows"""
        self.state_manager.update_party_knowledge(key, value)
    
    def update_session_number(self, session_number: int):
        """Update session number"""
        self.state_manager.update_session_number(session_number)
    
    def update_party_level(self, level: int):
        """Update party level"""
        self.state_manager.update_party_level(level)
    
    def get_accessible_locations(self) -> Dict[str, Any]:
        """Get list of locations that are accessible for travel/freeroaming"""
        return self.state_manager.get_accessible_locations()
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _get_chapter(self) -> Dict[str, Any]:
        """Get current chapter (with caching)"""
        if not self._current_chapter_cache:
            current_state = self.metadata.get("current_state", {})
            chapter_id = current_state.get("chapter")
            
            # Fall back to legacy format
            if not chapter_id:
                chapter_id = self.metadata.get("current_part")
            
            if chapter_id:
                self._current_chapter_cache = self.location_manager.load_chapter(chapter_id)
        return self._current_chapter_cache or {}
    
    def _get_location(self) -> Dict[str, Any]:
        """Get current location (with caching)"""
        if not self._current_location_cache:
            current_state = self.metadata.get("current_state", {})
            location_id = current_state.get("location")
            
            # Fall back to legacy format
            if not location_id:
                location_id = self.metadata.get("current_location")
            
            if location_id:
                self._current_location_cache = self.location_manager.load_location(location_id)
        return self._current_location_cache or {}
    
    # ========================================================================
    # List Methods (delegates to LocationManager)
    # ========================================================================
    
    def list_available_chapters(self) -> List[str]:
        """List all available chapters"""
        return self.location_manager.list_available_chapters()
    
    def list_available_locations(self) -> List[str]:
        """List all available locations"""
        return self.location_manager.list_available_locations()
    
    def list_available_npcs(self) -> List[str]:
        """List all available NPCs"""
        return self.location_manager.list_available_npcs()
    
    def get_adventure_info(self) -> Dict[str, Any]:
        """Get basic adventure information"""
        return {
            "id": self.metadata.get("id"),
            "name": self.metadata.get("name"),
            "description": self.metadata.get("description"),
            "level_range": self.metadata.get("level_range"),
            "estimated_sessions": self.metadata.get("estimated_sessions"),
            "current_state": self.metadata.get("current_state", {}),
            "available_chapters": self.list_available_chapters(),
            "available_locations": self.list_available_locations(),
            "available_npcs": self.list_available_npcs(),
        }

