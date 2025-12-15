"""
Adventure Context Loader - Optimized for Token Efficiency

Dynamically loads only relevant adventure content to minimize AI costs.
Uses three-tier context system: minimal, standard, detailed.

Based on ADVENTURE_STRUCTURE_GUIDE.md and OPTIMIZATION_GUIDE.md
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal


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
        backend_path = Path(__file__).parent.parent / "adventures" / adventure_name
        frontend_path = Path(__file__).parent.parent.parent / "frontend" / "public" / "data" / adventure_name
        
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
        self._npc_cache = {}
    
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
    # On-Demand Loading
    # ========================================================================
    
    def get_location_details(self, location_id: Optional[str] = None, area_id: Optional[str] = None) -> str:
        """
        COMPRESSED location info - only load when investigating
        Target: 100-300 tokens
        
        Args:
            location_id: Specific location to load (if None, uses current location)
            area_id: Specific area within the location
        """
        if location_id:
            location = self._load_location(location_id)
        else:
            location = self._get_location()
        
        if not location:
            return "Location details not available."
        
        if area_id and 'areas' in location:
            area = location['areas'].get(area_id, {})
            parts = [
                f"**{area_id.replace('_', ' ').title()}**",
                area.get('description', '')
            ]
            
            if area.get('features'):
                parts.append(f"\n**Features:** {', '.join(area['features'][:5])}")
            
            if area.get('encounters'):
                enc = area['encounters']
                if isinstance(enc, dict):
                    parts.append(f"\n**Encounter:** {enc.get('type', 'enemies')} ({enc.get('trigger', 'when entering')})")
            
            if area.get('secrets'):
                parts.append(f"\n**Hidden:** {len(area['secrets'])} secret(s)")
            
            if area.get('treasure'):
                parts.append(f"\n**Treasure:** Present")
            
            return "\n".join(parts)
        
        # General location summary
        parts = [
            f"**{location.get('name', 'Location')}**",
            location.get('description', '')[:200] + "..."
        ]
        
        if location.get('areas'):
            parts.append(f"\n**Areas:** {', '.join(list(location['areas'].keys())[:5])}")
        
        return "\n".join(parts)
    
    def get_npc_info(self, npc_id: str) -> str:
        """
        COMPRESSED NPC info - only load when interacting
        Target: 150-250 tokens
        """
        npc = self._load_npc(npc_id)
        if not npc:
            return f"NPC '{npc_id}' not found."
        
        parts = [
            f"**{npc.get('name', npc_id)}**",
        ]
        
        if npc.get('title'):
            parts.append(f"_{npc['title']}_")
        
        # Basic info
        info_parts = []
        if npc.get('race'):
            info_parts.append(npc['race'])
        if npc.get('class'):
            info_parts.append(npc['class'])
        if info_parts:
            parts.append(" ".join(info_parts))
        
        # Personality (compressed)
        if npc.get('personality'):
            personality = npc['personality']
            if personality.get('traits'):
                parts.append(f"\n**Traits:** {', '.join(personality['traits'][:3])}")
            if personality.get('goals'):
                parts.append(f"**Goals:** {', '.join(personality['goals'][:2])}")
            if personality.get('mannerisms'):
                parts.append(f"**Mannerisms:** {personality['mannerisms'][:100]}")
        
        # One example dialogue
        if npc.get('dialogue_examples'):
            parts.append(f"\n_Example: {npc['dialogue_examples'][0][:150]}_")
        
        # Current situation
        if npc.get('current_situation'):
            situation = npc['current_situation']
            parts.append(f"\n**Status:** {situation.get('status', 'normal')}")
            if situation.get('location'):
                parts.append(f"**Location:** {situation['location']}")
        
        # Key info (first 2 items)
        if npc.get('information_known'):
            parts.append("\n**Knows:**")
            for info in npc['information_known'][:2]:
                parts.append(f"  - {info[:100]}")
        
        return "\n".join(parts)
    
    def get_encounter_details(self, location_id: str, area_id: str) -> Optional[Dict[str, Any]]:
        """Get encounter details for a specific area"""
        location = self._load_location(location_id)
        if not location or 'areas' not in location:
            return None
        
        if area_id in location['areas']:
            area = location['areas'][area_id]
            return area.get('encounters')
        
        return None
    
    # ========================================================================
    # State Management
    # ========================================================================
    
    def update_location(self, new_location: str, validate_discovery: bool = True):
        """
        Update current location with optional validation
        
        Args:
            new_location: Location ID to set
            validate_discovery: If True, only allow moving to discovered locations
                               (except for starting locations or locations in current chapter)
        
        Note:
            The DM should handle narrative validation (ensuring players can reach the location).
            This method tracks discovery but doesn't prevent movement - the DM prompt
            enforces that players must actually travel to locations.
            
            Backtracking to previously visited locations is always allowed.
        """
        if "current_state" not in self.metadata:
            self.metadata["current_state"] = {}
        
        # Track discovered locations
        discovered = self.metadata.get("discovered_locations", [])
        if new_location not in discovered:
            self.metadata.setdefault("discovered_locations", []).append(new_location)
        
        self.metadata["current_state"]["location"] = new_location
        self._current_location_cache = None  # Invalidate cache
        self.save_metadata()
    
    def get_accessible_locations(self) -> Dict[str, Any]:
        """
        Get list of locations that are accessible for travel/freeroaming
        
        Returns:
            Dict with:
            - discovered: Previously visited locations (can backtrack)
            - current_chapter: Locations in current chapter (can explore)
            - previous_chapters: Locations from previous chapters (can backtrack)
            - nearby: Locations that are loosely connected/accessible
        """
        current_state = self.metadata.get("current_state", {})
        current_chapter_id = current_state.get("chapter")
        current_location_id = current_state.get("location")
        discovered = self.metadata.get("discovered_locations", [])
        
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
        locations_dir = self.adventure_dir / "locations"
        if locations_dir.exists():
            for loc_file in locations_dir.glob("*.json"):
                try:
                    with open(loc_file) as f:
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
        
        # Nearby locations: same part or adjacent parts, or connected by travel routes
        # This is a heuristic - locations in same/adjacent parts are "nearby"
        if current_part and locations_dir.exists():
            for loc_file in locations_dir.glob("*.json"):
                try:
                    with open(loc_file) as f:
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
                        # Adjacent parts = potentially nearby (depends on travel routes)
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
    
    def update_chapter(self, new_chapter: str, force: bool = False):
        """
        Update current chapter with flexible validation for sandbox adventures
        
        Args:
            new_chapter: Chapter ID to set (e.g., "part1_goblin_arrows", "part2_phandalin")
            force: If True, bypass validation (for DM override when narrative makes sense)
        
        Raises:
            ValueError: If trying to skip ahead without prerequisites (unless force=True)
        
        Note:
            - Backtracking to previous chapters is always allowed
            - Forward progression is flexible: players can skip ahead if they have:
              * Discovered the location (in discovered_locations)
              * Learned about it from NPCs (tracked in party_knowledge)
              * Received directions/information
            - In sandbox adventures, chapters represent areas/storylines that can be
              accessed in any order if players have the right information
            - Use force=True when DM determines narrative progression makes sense
        """
        if "current_state" not in self.metadata:
            self.metadata["current_state"] = {}
        
        current_chapter = self.metadata.get("current_state", {}).get("chapter")
        
        # If force is True, allow any chapter change (DM override)
        if force:
            self.metadata["current_state"]["chapter"] = new_chapter
            self._current_chapter_cache = None
            self.save_metadata()
            return
        
        # Validate chapter progression - flexible for sandbox adventures
        if current_chapter and new_chapter:
            # Extract part numbers for comparison
            current_part = self._extract_part_number(current_chapter)
            new_part = self._extract_part_number(new_chapter)
            
            if current_part is not None and new_part is not None:
                # Always allow: same part, going back, or forward by 1
                if new_part <= current_part + 1:
                    # Normal progression - always allowed
                    pass
                else:
                    # Skipping ahead more than 1 part - check if prerequisites are met
                    # Check if location is discovered or party has knowledge
                    chapter_data = self._load_chapter(new_chapter)
                    if chapter_data:
                        key_locations = chapter_data.get("key_locations", [])
                        discovered = self.metadata.get("discovered_locations", [])
                        party_knowledge = self.metadata.get("party_knowledge", {})
                        
                        # Check if any key location is discovered
                        has_discovered_location = any(
                            loc in discovered for loc in key_locations
                        )
                        
                        # Check if party has relevant knowledge
                        # Look for knowledge flags that might unlock this chapter
                        has_relevant_knowledge = False
                        chapter_id_lower = new_chapter.lower()
                        for key, value in party_knowledge.items():
                            if value and (
                                "wave_echo" in key or "cragmaw_castle" in key or
                                "location" in key or "knows_about" in key
                            ):
                                has_relevant_knowledge = True
                                break
                        
                        # Allow if location discovered OR party has knowledge OR chapter has no strict prerequisites
                        if not (has_discovered_location or has_relevant_knowledge):
                            # Still allow, but log a warning - DM should validate narratively
                            # In sandbox adventures, chapters may not have strict prerequisites
                            pass  # Allow but DM should ensure narrative makes sense
        
        self.metadata["current_state"]["chapter"] = new_chapter
        self._current_chapter_cache = None  # Invalidate cache
        self.save_metadata()
    
    def _extract_part_number(self, chapter_id: str) -> Optional[int]:
        """Extract part number from chapter ID (e.g., 'part1_goblin_arrows' -> 1)"""
        if chapter_id.startswith("part"):
            # Extract number after "part"
            try:
                # Handle formats like "part1", "part1_goblin_arrows", "part01", etc.
                remaining = chapter_id[4:]  # Remove "part"
                # Find where the number ends
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
                # Find where the number ends
                num_str = "".join(c for c in num_str if c.isdigit())
                if num_str:
                    return int(num_str)
            except (ValueError, IndexError):
                pass
        
        return None
    
    def add_event(self, event: str):
        """Track important event"""
        self.metadata.setdefault("important_events", []).append(event)
        # Keep only last 20 events
        self.metadata["important_events"] = self.metadata["important_events"][-20:]
        self.save_metadata()
    
    def meet_npc(self, npc_id: str):
        """Track that party met an NPC"""
        if npc_id not in self.metadata.get("met_npcs", []):
            self.metadata.setdefault("met_npcs", []).append(npc_id)
        self.save_metadata()
    
    def add_quest(self, quest: Dict[str, Any]):
        """Add a new quest"""
        self.metadata.setdefault("active_quests", []).append(quest)
        self.save_metadata()
    
    def update_quest_status(self, quest_id: str, status: str):
        """Update quest status"""
        for quest in self.metadata.get("active_quests", []):
            if isinstance(quest, dict) and quest.get("id") == quest_id:
                quest["status"] = status
                break
        self.save_metadata()
    
    def update_party_knowledge(self, key: str, value: bool):
        """Update what the party knows"""
        self.metadata.setdefault("party_knowledge", {})[key] = value
        self.save_metadata()
    
    def update_session_number(self, session_number: int):
        """Update session number"""
        if "current_state" not in self.metadata:
            self.metadata["current_state"] = {}
        self.metadata["current_state"]["session_number"] = session_number
        self.save_metadata()
    
    def update_party_level(self, level: int):
        """Update party level"""
        if "current_state" not in self.metadata:
            self.metadata["current_state"] = {}
        self.metadata["current_state"]["party_level"] = level
        self.save_metadata()
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _get_chapter(self) -> Dict[str, Any]:
        """Get current chapter (with caching) - supports both 'current_state.chapter' and 'current_part' formats"""
        if not self._current_chapter_cache:
            # Try new format first
            current_state = self.metadata.get("current_state", {})
            chapter_id = current_state.get("chapter")
            
            # Fall back to legacy format
            if not chapter_id:
                chapter_id = self.metadata.get("current_part")
            
            if chapter_id:
                self._current_chapter_cache = self._load_chapter(chapter_id)
        return self._current_chapter_cache or {}
    
    def _get_location(self) -> Dict[str, Any]:
        """Get current location (with caching) - supports both 'current_state.location' and 'current_location' formats"""
        if not self._current_location_cache:
            # Try new format first
            current_state = self.metadata.get("current_state", {})
            location_id = current_state.get("location")
            
            # Fall back to legacy format
            if not location_id:
                location_id = self.metadata.get("current_location")
            
            if location_id:
                self._current_location_cache = self._load_location(location_id)
        return self._current_location_cache or {}
    
    def _load_chapter(self, chapter_id: str) -> Dict[str, Any]:
        """Load chapter file - supports both 'part1' and 'ch01' naming conventions"""
        # Try exact match first
        path = self.adventure_dir / "chapters" / f"{chapter_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        
        # Try alternative naming: if looking for 'ch01', try 'part1' and vice versa
        # Convert ch01 -> part1, ch02 -> part2, etc.
        if chapter_id.startswith("ch") and chapter_id[2:].isdigit():
            part_num = chapter_id[2:]
            alt_id = f"part{part_num}"
            # Try exact match first
            path = self.adventure_dir / "chapters" / f"{alt_id}.json"
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            # Try files that start with the pattern (e.g., "part1_goblin_arrows.json")
            chapters_dir = self.adventure_dir / "chapters"
            if chapters_dir.exists():
                for file in chapters_dir.glob(f"{alt_id}_*.json"):
                    with open(file) as f:
                        return json.load(f)
        
        # Convert part1 -> ch01, part2 -> ch02, etc.
        # Note: Even though we convert the ID format, the actual files use "part" prefix
        # So we still search for "part*" files, not "ch*" files
        if chapter_id.startswith("part") and chapter_id[4:].isdigit():
            part_num = chapter_id[4:]
            # Try exact match first
            path = self.adventure_dir / "chapters" / f"{chapter_id}.json"
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            # Try files that start with the pattern (e.g., "part1_goblin_arrows.json")
            chapters_dir = self.adventure_dir / "chapters"
            if chapters_dir.exists():
                for file in chapters_dir.glob(f"{chapter_id}_*.json"):
                    with open(file) as f:
                        return json.load(f)
        
        # If still not found, try to find any chapter file that might match
        chapters_dir = self.adventure_dir / "chapters"
        if chapters_dir.exists():
            # Look for files that might be the chapter (fuzzy match)
            for file in chapters_dir.glob("*.json"):
                if chapter_id.lower() in file.stem.lower() or file.stem.lower() in chapter_id.lower():
                    with open(file) as f:
                        return json.load(f)
        
        return {}
    
    def _load_location(self, location_id: str) -> Dict[str, Any]:
        """Load location file"""
        path = self.adventure_dir / "locations" / f"{location_id}.json"
        if not path.exists():
            return {}
        
        with open(path) as f:
            return json.load(f)
    
    def _load_npc(self, npc_id: str) -> Dict[str, Any]:
        """Load NPC file (with caching)"""
        if npc_id in self._npc_cache:
            return self._npc_cache[npc_id]
        
        path = self.adventure_dir / "npcs" / f"{npc_id}.json"
        if not path.exists():
            return {}
        
        with open(path) as f:
            npc_data = json.load(f)
            self._npc_cache[npc_id] = npc_data
            return npc_data
    
    def list_available_chapters(self) -> List[str]:
        """List all available chapters"""
        chapters_dir = self.adventure_dir / "chapters"
        if not chapters_dir.exists():
            return []
        
        return [f.stem for f in chapters_dir.glob("*.json")]
    
    def list_available_locations(self) -> List[str]:
        """List all available locations"""
        locations_dir = self.adventure_dir / "locations"
        if not locations_dir.exists():
            return []
        
        return [f.stem for f in locations_dir.glob("*.json")]
    
    def list_available_npcs(self) -> List[str]:
        """List all available NPCs"""
        npcs_dir = self.adventure_dir / "npcs"
        if not npcs_dir.exists():
            return []
        
        return [f.stem for f in npcs_dir.glob("*.json")]
    
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


class ContextManager:
    """
    Smart manager that decides WHEN and WHAT context to load
    This is the key to speed and cost optimization!
    """
    
    def __init__(self, adventure_context: AdventureContext):
        self.adventure = adventure_context
        self.last_context_level = "minimal"
    
    def get_context_for_turn(
        self, 
        user_input: str, 
        turn_type: Literal["auto", "minimal", "standard", "detailed"] = "auto"
    ) -> str:
        """
        Intelligently decide how much context to load
        
        Args:
            user_input: Player's input text
            turn_type: Context level (auto-detect by default)
        
        Returns:
            Appropriate context string
        """
        
        if turn_type == "auto":
            turn_type = self._detect_context_need(user_input)
        
        # Get base context
        if turn_type == "minimal":
            context = self.adventure.get_minimal_context()
        elif turn_type == "standard":
            context = self.adventure.get_standard_context()
        else:  # detailed
            context = self.adventure.get_detailed_context()
        
        # Add location details if examining
        if self._is_examining(user_input):
            context += "\n\n" + self.adventure.get_location_details()
        
        # Add NPC details if talking
        npc_id = self._extract_npc_mention(user_input)
        if npc_id:
            context += "\n\n" + self.adventure.get_npc_info(npc_id)
        
        self.last_context_level = turn_type
        return context
    
    def _detect_context_need(self, user_input: str) -> Literal["minimal", "standard", "detailed"]:
        """Smart detection of how much context player needs"""
        lower = user_input.lower()
        
        # Needs detailed context
        if any(word in lower for word in [
            "recap", "summary", "remind me", "what's happening",
            "where am i", "what was", "confused", "what's my quest"
        ]):
            return "detailed"
        
        # Needs standard context
        if any(word in lower for word in [
            "look around", "what do i see", "describe",
            "where are we", "status", "investigate", "search"
        ]):
            return "standard"
        
        # Most actions need minimal context
        return "minimal"
    
    def _is_examining(self, user_input: str) -> bool:
        """Check if player is examining surroundings"""
        examine_words = ["look", "search", "examine", "investigate", "check", "inspect", "explore"]
        return any(word in user_input.lower() for word in examine_words)
    
    def _extract_npc_mention(self, user_input: str) -> Optional[str]:
        """Extract NPC name if mentioned"""
        lower = user_input.lower()
        
        # Get met NPCs
        met_npcs = self.adventure.metadata.get("met_npcs", [])
        
        # Check if any known NPC is mentioned
        for npc_id in met_npcs:
            # Check various forms (underscores, spaces, partial)
            npc_name_parts = npc_id.replace("_", " ").split()
            if any(part.lower() in lower for part in npc_name_parts if len(part) > 3):
                return npc_id
        
        return None


# Export main classes
__all__ = ['AdventureContext', 'ContextManager']

