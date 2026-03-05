"""
Quest Log Analyzer

Automatically extracts quest-related information from DM responses
and updates the quest log accordingly.
"""

import re
from typing import List, Dict, Any, Optional


class QuestLogAnalyzer:
    """Analyzes DM responses to extract quest updates"""
    
    # Quest status keywords
    QUEST_COMPLETION_KEYWORDS = [
        "completed", "finished", "accomplished", "fulfilled", 
        "succeeded", "done", "achieved", "resolved", "concluded"
    ]
    
    QUEST_START_KEYWORDS = [
        "new quest", "begin", "start", "accept", "take on",
        "embark", "undertake", "beginning"
    ]
    
    QUEST_FAILURE_KEYWORDS = [
        "failed", "lost", "abandoned", "gave up", "couldn't complete",
        "unable to", "impossible", "too late"
    ]
    
    QUEST_PROGRESS_KEYWORDS = [
        "progress", "advance", "step forward", "closer", "discovered",
        "found", "learned", "uncovered", "revealed"
    ]
    
    def analyze_response(self, narrative: str, current_quests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze DM narrative for quest updates
        
        Args:
            narrative: DM's narrative response
            current_quests: List of current quest log entries
            
        Returns:
            List of quest updates to apply
            Each update is: {
                "action": "create" | "update" | "complete" | "fail",
                "quest_id": Optional[str],  # For updates to existing quests
                "name": str,
                "description": Optional[str],
                "status": str,
                "notes": Optional[str]
            }
        """
        updates = []
        narrative_lower = narrative.lower()
        
        # Check for quest completion
        for quest in current_quests:
            quest_name = quest.get("name", "").lower()
            if quest_name and any(keyword in narrative_lower for keyword in self.QUEST_COMPLETION_KEYWORDS):
                # Check if this quest is mentioned in the narrative
                if quest_name in narrative_lower or any(word in narrative_lower for word in quest_name.split()):
                    updates.append({
                        "action": "complete",
                        "quest_id": quest.get("id"),
                        "name": quest.get("name"),
                        "status": "completed",
                        "notes": f"Completed: {self._extract_relevant_snippet(narrative, quest_name)}"
                    })
        
        # Check for quest failure
        for quest in current_quests:
            quest_name = quest.get("name", "").lower()
            if quest_name and any(keyword in narrative_lower for keyword in self.QUEST_FAILURE_KEYWORDS):
                if quest_name in narrative_lower or any(word in narrative_lower for word in quest_name.split()):
                    updates.append({
                        "action": "fail",
                        "quest_id": quest.get("id"),
                        "name": quest.get("name"),
                        "status": "failed",
                        "notes": f"Failed: {self._extract_relevant_snippet(narrative, quest_name)}"
                    })
        
        # Check for quest progress updates
        for quest in current_quests:
            quest_name = quest.get("name", "").lower()
            if quest_name and any(keyword in narrative_lower for keyword in self.QUEST_PROGRESS_KEYWORDS):
                if quest_name in narrative_lower or any(word in narrative_lower for word in quest_name.split()):
                    # Extract progress note
                    progress_note = self._extract_relevant_snippet(narrative, quest_name)
                    if progress_note:
                        updates.append({
                            "action": "update",
                            "quest_id": quest.get("id"),
                            "name": quest.get("name"),
                            "status": "in_progress",
                            "notes": progress_note
                        })
        
        # Check for new quest mentions
        # Look for patterns like "new quest", "your quest is to", etc.
        new_quest_patterns = [
            r"new quest[:\s]+(.+?)(?:\.|$)",
            r"your quest[:\s]+(.+?)(?:\.|$)",
            r"mission[:\s]+(.+?)(?:\.|$)",
            r"task[:\s]+(.+?)(?:\.|$)",
        ]
        
        for pattern in new_quest_patterns:
            matches = re.finditer(pattern, narrative, re.IGNORECASE)
            for match in matches:
                quest_name = match.group(1).strip()
                if quest_name and len(quest_name) < 100:  # Reasonable quest name length
                    # Check if this quest already exists
                    if not any(q.get("name", "").lower() == quest_name.lower() for q in current_quests):
                        updates.append({
                            "action": "create",
                            "name": quest_name,
                            "description": self._extract_quest_description(narrative, quest_name),
                            "status": "not_started"
                        })
        
        return updates
    
    def _extract_relevant_snippet(self, narrative: str, quest_name: str, context_chars: int = 200) -> str:
        """Extract a relevant snippet from narrative mentioning the quest"""
        quest_name_lower = quest_name.lower()
        narrative_lower = narrative.lower()
        
        # Find where quest is mentioned
        index = narrative_lower.find(quest_name_lower)
        if index == -1:
            # Try finding any word from quest name
            quest_words = quest_name_lower.split()
            for word in quest_words:
                if len(word) > 3:  # Only meaningful words
                    index = narrative_lower.find(word)
                    if index != -1:
                        break
        
        if index != -1:
            start = max(0, index - context_chars // 2)
            end = min(len(narrative), index + context_chars // 2)
            snippet = narrative[start:end].strip()
            # Clean up snippet
            snippet = re.sub(r'\s+', ' ', snippet)
            return snippet
        
        return ""
    
    def _extract_quest_description(self, narrative: str, quest_name: str) -> str:
        """Extract quest description from narrative"""
        # Try to find the sentence or paragraph containing the quest name
        sentences = re.split(r'[.!?]+', narrative)
        for sentence in sentences:
            if quest_name.lower() in sentence.lower():
                return sentence.strip()
        
        # Fallback: return first sentence mentioning quest-related keywords
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in ["quest", "mission", "task", "goal"]):
                return sentence.strip()
        
        return ""


def extract_quest_updates_from_narrative(
    narrative: str,
    current_quests: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Convenience function to extract quest updates from DM narrative
    
    Args:
        narrative: DM's narrative response
        current_quests: List of current quest log entries
        
    Returns:
        List of quest updates
    """
    analyzer = QuestLogAnalyzer()
    return analyzer.analyze_response(narrative, current_quests)

