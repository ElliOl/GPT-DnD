"""
Context Manager - Smart Context Detection

Intelligently decides when and what context to load based on player input.
This is the key to speed and cost optimization!
"""

from typing import Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .context_loader import AdventureContext


class ContextManager:
    """
    Smart manager that decides WHEN and WHAT context to load
    This is the key to speed and cost optimization!
    """
    
    def __init__(self, adventure_context: "AdventureContext"):
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

