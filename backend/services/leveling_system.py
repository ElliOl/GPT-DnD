"""
Leveling System - Tracks progression and manages level ups

Tracks the 3 pillars of D&D:
- Combat: Encounters defeated
- Exploration: Locations discovered, secrets found
- Social: NPCs met, quests completed

Checks for level ups on long rests based on adventure progression.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class LevelingSystem:
    """
    Manages character leveling based on adventure progression
    
    Uses milestone leveling tied to adventure chapters and the 3 pillars.
    Prevents leveling without meaningful progress.
    """
    
    # Level up thresholds for Lost Mines (1-5)
    # Based on chapter progression and expected XP
    LEVEL_MILESTONES = {
        1: {  # Level 1 → 2
            "chapter": "part1_goblin_arrows",
            "required": ["clear_hideout", "rescue_sildar"],
            "description": "Complete Cragmaw Hideout and rescue Sildar"
        },
        2: {  # Level 2 → 3
            "chapter": "part2_phandalin",
            "required": ["clear_redbrands"],
            "description": "Clear Redbrand Hideout and defeat Glasstaff"
        },
        3: {  # Level 3 → 4
            "chapter": "part3_spiders_web",
            "required": ["find_cragmaw_castle", "rescue_gundren"],
            "description": "Find Cragmaw Castle and rescue Gundren"
        },
        4: {  # Level 4 → 5
            "chapter": "part4_wave_echo_cave",
            "required": ["defeat_black_spider", "find_forge"],
            "description": "Defeat Black Spider and find Forge of Spells"
        }
    }
    
    def __init__(self, adventure_context):
        """
        Initialize leveling system
        
        Args:
            adventure_context: AdventureContext instance
        """
        self.adventure = adventure_context
        self.metadata = adventure_context.metadata
        
    def track_combat_encounter(self, encounter_id: str, xp_value: int = 0):
        """Track a combat encounter completion"""
        if "progression" not in self.metadata:
            self.metadata["progression"] = {}
        if "combat_encounters" not in self.metadata["progression"]:
            self.metadata["progression"]["combat_encounters"] = []
        
        if encounter_id not in self.metadata["progression"]["combat_encounters"]:
            self.metadata["progression"]["combat_encounters"].append({
                "id": encounter_id,
                "xp": xp_value,
                "completed_at": datetime.now().isoformat()
            })
            self.adventure.save_metadata()
    
    def track_exploration(self, milestone: str, location_id: Optional[str] = None):
        """Track exploration milestone (location discovered, secret found, etc.)"""
        if "progression" not in self.metadata:
            self.metadata["progression"] = {}
        if "exploration_milestones" not in self.metadata["progression"]:
            self.metadata["progression"]["exploration_milestones"] = []
        
        milestone_entry = {
            "milestone": milestone,
            "completed_at": datetime.now().isoformat()
        }
        if location_id:
            milestone_entry["location"] = location_id
        
        if milestone_entry not in self.metadata["progression"]["exploration_milestones"]:
            self.metadata["progression"]["exploration_milestones"].append(milestone_entry)
            self.adventure.save_metadata()
    
    def track_social_interaction(self, interaction_type: str, npc_id: Optional[str] = None, quest_id: Optional[str] = None):
        """Track social interaction (NPC met, quest completed, etc.)"""
        if "progression" not in self.metadata:
            self.metadata["progression"] = {}
        if "social_interactions" not in self.metadata["progression"]:
            self.metadata["progression"]["social_interactions"] = []
        
        interaction_entry = {
            "type": interaction_type,
            "completed_at": datetime.now().isoformat()
        }
        if npc_id:
            interaction_entry["npc"] = npc_id
        if quest_id:
            interaction_entry["quest"] = quest_id
        
        if interaction_entry not in self.metadata["progression"]["social_interactions"]:
            self.metadata["progression"]["social_interactions"].append(interaction_entry)
            self.adventure.save_metadata()
    
    def check_level_up_eligibility(self, current_level: int) -> Dict[str, Any]:
        """
        Check if party is eligible for level up
        
        Args:
            current_level: Current party level
            
        Returns:
            Dict with:
            - eligible: bool
            - reason: str (why eligible or not)
            - new_level: int (if eligible)
            - progress_summary: dict (what they've accomplished)
        """
        if current_level >= 5:
            return {
                "eligible": False,
                "reason": "Already at maximum level for this adventure",
                "new_level": current_level,
                "progress_summary": {}
            }
        
        next_level = current_level + 1
        milestone = self.LEVEL_MILESTONES.get(current_level)
        
        if not milestone:
            return {
                "eligible": False,
                "reason": f"No milestone defined for level {current_level}",
                "new_level": current_level,
                "progress_summary": {}
            }
        
        # Get current state
        current_state = self.metadata.get("current_state", {})
        current_chapter = current_state.get("chapter", "")
        progression = self.metadata.get("progression", {})
        
        # Check if they've reached the required chapter
        required_chapter = milestone.get("chapter", "")
        chapter_match = required_chapter in current_chapter or current_chapter in required_chapter
        
        # Check required objectives
        required_objectives = milestone.get("required", [])
        completed_objectives = []
        
        # Get progression data
        combat_encounters = progression.get("combat_encounters", [])
        exploration = progression.get("exploration_milestones", [])
        social = progression.get("social_interactions", [])
        active_quests = self.metadata.get("active_quests", [])
        completed_quests = [q for q in active_quests if isinstance(q, dict) and q.get("status") == "completed"]
        discovered_locations = self.metadata.get("discovered_locations", [])
        met_npcs = self.metadata.get("met_npcs", [])
        
        # Check objectives more flexibly
        for obj in required_objectives:
            obj_lower = obj.lower()
            
            # Combat-based objectives
            if "hideout" in obj_lower or "clear" in obj_lower:
                # Check if they've been to relevant locations or had combat
                if "cragmaw" in obj_lower and ("cragmaw_hideout" in discovered_locations or len(combat_encounters) > 0):
                    completed_objectives.append(obj)
                elif "redbrand" in obj_lower and ("redbrand_hideout" in discovered_locations or any("redbrand" in str(e.get("id", "")).lower() for e in combat_encounters)):
                    completed_objectives.append(obj)
            
            # Boss defeat objectives
            if "black_spider" in obj_lower or "nezznar" in obj_lower or "defeat" in obj_lower:
                if any("black_spider" in str(e.get("id", "")).lower() or "nezznar" in str(e.get("id", "")).lower() for e in combat_encounters):
                    completed_objectives.append(obj)
            
            # Location discovery objectives
            if "find" in obj_lower or "castle" in obj_lower:
                if "cragmaw_castle" in obj_lower and "cragmaw_castle" in discovered_locations:
                    completed_objectives.append(obj)
                elif "forge" in obj_lower and any("forge" in str(e.get("milestone", "")).lower() for e in exploration):
                    completed_objectives.append(obj)
            
            # Rescue objectives
            if "rescue" in obj_lower:
                if "sildar" in obj_lower and ("sildar_hallwinter" in met_npcs or any("sildar" in str(s.get("npc", "")).lower() for s in social)):
                    completed_objectives.append(obj)
                elif "gundren" in obj_lower and ("gundren_rockseeker" in met_npcs or any("gundren" in str(s.get("npc", "")).lower() for s in social)):
                    completed_objectives.append(obj)
        
        # If no specific objectives required, check general progress
        if not required_objectives:
            # Use chapter progression and general activity as proxy
            if chapter_match and (len(combat_encounters) > 0 or len(exploration) > 0 or len(social) > 0):
                completed_objectives = ["general_progress"]  # Mark as having progress
        
        # Check if meaningful progress has been made
        # Require at least one of: combat encounter, exploration milestone, or quest completion since last level
        last_level_up = self.metadata.get("last_level_up", {})
        last_check_time = last_level_up.get("checked_at")
        
        recent_activity = False
        if last_check_time:
            try:
                last_check = datetime.fromisoformat(last_check_time.replace('Z', '+00:00'))
                now = datetime.now()
                
                # Check for recent combat
                recent_combat = any(
                    datetime.fromisoformat(e.get("completed_at", "").replace('Z', '+00:00')) > last_check
                    for e in combat_encounters
                    if e.get("completed_at")
                )
                
                # Check for recent exploration
                recent_exploration = any(
                    datetime.fromisoformat(e.get("completed_at", "").replace('Z', '+00:00')) > last_check
                    for e in exploration
                    if e.get("completed_at")
                )
                
                # Check for recent social
                recent_social = any(
                    datetime.fromisoformat(s.get("completed_at", "").replace('Z', '+00:00')) > last_check
                    for s in social
                    if s.get("completed_at")
                )
                
                recent_activity = recent_combat or recent_exploration or recent_social
            except (ValueError, AttributeError):
                # If parsing fails, assume recent activity if any progress exists
                recent_activity = len(combat_encounters) > 0 or len(exploration) > 0 or len(social) > 0
        else:
            # First check - allow if they have any progress
            recent_activity = len(combat_encounters) > 0 or len(exploration) > 0 or len(social) > 0
        
        # Determine eligibility
        # For early levels, be more lenient
        if current_level < 2:
            # Level 1 → 2: Just need some activity and to be in/through Part 1
            objectives_met = len(completed_objectives) > 0 or len(combat_encounters) > 0
            chapter_progress = chapter_match or "part1" in current_chapter.lower()
        else:
            # Higher levels: Need more specific progress
            objectives_met = len(completed_objectives) >= max(1, len(required_objectives) * 0.6)  # 60% of objectives
            chapter_progress = chapter_match
        
        eligible = (objectives_met or chapter_progress) and recent_activity
        
        progress_summary = {
            "current_chapter": current_chapter,
            "required_chapter": required_chapter,
            "chapter_match": chapter_match,
            "required_objectives": required_objectives,
            "completed_objectives": completed_objectives,
            "combat_encounters": len(combat_encounters),
            "exploration_milestones": len(exploration),
            "social_interactions": len(social),
            "completed_quests": len(completed_quests),
            "recent_activity": recent_activity
        }
        
        if eligible:
            reason = f"Completed milestone: {milestone.get('description', 'Adventure progression')}"
        else:
            missing = []
            if not chapter_progress:
                missing.append(f"reach chapter {required_chapter}")
            if not objectives_met:
                missing.append(f"complete objectives: {', '.join(set(required_objectives) - set(completed_objectives))}")
            if not recent_activity:
                missing.append("make meaningful progress (combat, exploration, or social interaction)")
            reason = f"Need to: {', '.join(missing)}"
        
        return {
            "eligible": eligible,
            "reason": reason,
            "new_level": next_level if eligible else current_level,
            "progress_summary": progress_summary
        }
    
    def process_long_rest(self, current_level: int) -> Dict[str, Any]:
        """
        Process a long rest and check for level up
        
        Args:
            current_level: Current party level
            
        Returns:
            Dict with level up information if eligible
        """
        check_result = self.check_level_up_eligibility(current_level)
        
        # Update last check time
        if "last_level_up" not in self.metadata:
            self.metadata["last_level_up"] = {}
        self.metadata["last_level_up"]["checked_at"] = datetime.now().isoformat()
        self.metadata["last_level_up"]["level"] = current_level
        self.adventure.save_metadata()
        
        if check_result["eligible"]:
            # Level up!
            new_level = check_result["new_level"]
            self.metadata["last_level_up"]["leveled_up"] = True
            self.metadata["last_level_up"]["new_level"] = new_level
            self.metadata["last_level_up"]["leveled_at"] = datetime.now().isoformat()
            self.adventure.update_party_level(new_level)
            
            return {
                "level_up": True,
                "old_level": current_level,
                "new_level": new_level,
                "reason": check_result["reason"],
                "progress_summary": check_result["progress_summary"]
            }
        else:
            return {
                "level_up": False,
                "current_level": current_level,
                "reason": check_result["reason"],
                "progress_summary": check_result["progress_summary"]
            }
    
    def get_progression_summary(self) -> Dict[str, Any]:
        """Get summary of party progression across all 3 pillars"""
        progression = self.metadata.get("progression", {})
        current_state = self.metadata.get("current_state", {})
        
        return {
            "current_level": current_state.get("party_level", 1),
            "current_chapter": current_state.get("chapter", ""),
            "combat_encounters": len(progression.get("combat_encounters", [])),
            "exploration_milestones": len(progression.get("exploration_milestones", [])),
            "social_interactions": len(progression.get("social_interactions", [])),
            "completed_quests": len([q for q in self.metadata.get("active_quests", []) if isinstance(q, dict) and q.get("status") == "completed"]),
            "last_level_up": self.metadata.get("last_level_up", {})
        }

