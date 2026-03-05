"""
Location and NPC Loading Utilities

Handles loading of location and NPC data from JSON files.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class LocationManager:
    """Manages loading and caching of location and NPC data"""
    
    def __init__(self, adventure_dir: Path):
        self.adventure_dir = adventure_dir
        self._npc_cache = {}
        self._location_cache = {}
    
    def load_location(self, location_id: str) -> Dict[str, Any]:
        """Load location file"""
        if location_id in self._location_cache:
            return self._location_cache[location_id]
        
        path = self.adventure_dir / "locations" / f"{location_id}.json"
        if not path.exists():
            return {}
        
        with open(path) as f:
            location_data = json.load(f)
            self._location_cache[location_id] = location_data
            return location_data
    
    def load_npc(self, npc_id: str) -> Dict[str, Any]:
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
    
    def load_chapter(self, chapter_id: str) -> Dict[str, Any]:
        """Load chapter file - supports both 'part1' and 'ch01' naming conventions"""
        # Try exact match first
        path = self.adventure_dir / "chapters" / f"{chapter_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        
        # Try alternative naming: if looking for 'ch01', try 'part1' and vice versa
        if chapter_id.startswith("ch") and chapter_id[2:].isdigit():
            part_num = chapter_id[2:]
            alt_id = f"part{part_num}"
            path = self.adventure_dir / "chapters" / f"{alt_id}.json"
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            # Try files that start with the pattern
            chapters_dir = self.adventure_dir / "chapters"
            if chapters_dir.exists():
                for file in chapters_dir.glob(f"{alt_id}_*.json"):
                    with open(file) as f:
                        return json.load(f)
        
        # Convert part1 -> ch01 format
        if chapter_id.startswith("part") and chapter_id[4:].isdigit():
            part_num = chapter_id[4:]
            path = self.adventure_dir / "chapters" / f"{chapter_id}.json"
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            # Try files that start with the pattern
            chapters_dir = self.adventure_dir / "chapters"
            if chapters_dir.exists():
                for file in chapters_dir.glob(f"{chapter_id}_*.json"):
                    with open(file) as f:
                        return json.load(f)
        
        # Fuzzy match fallback
        chapters_dir = self.adventure_dir / "chapters"
        if chapters_dir.exists():
            for file in chapters_dir.glob("*.json"):
                if chapter_id.lower() in file.stem.lower() or file.stem.lower() in chapter_id.lower():
                    with open(file) as f:
                        return json.load(f)
        
        return {}
    
    def get_location_details(self, location: Dict[str, Any], area_id: Optional[str] = None) -> str:
        """
        Get compressed location info - only load when investigating
        Target: 100-300 tokens
        """
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
    
    def get_npc_info(self, npc: Dict[str, Any]) -> str:
        """
        Get compressed NPC info - only load when interacting
        Target: 150-250 tokens
        """
        if not npc:
            return "NPC not found."
        
        parts = [f"**{npc.get('name', 'Unknown')}**"]
        
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

