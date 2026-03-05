# Adventure Structure Implementation - Cursor Instructions

## Overview

This guide shows you how to implement the **modular adventure system** that allows running full campaigns (like Curse of Strahd) efficiently without loading 200,000 tokens every turn.

**What you're building:**
- JSON-based adventure structure (chapters, locations, NPCs, etc.)
- Dynamic context loader that loads only what's needed
- Integration with the DM agent to use adventure data

**Result:**
- Run any size campaign (Lost Mines, Curse of Strahd, homebrew)
- Cost: ~$0.01/turn instead of $0.60/turn
- AI gets exactly the context it needs, when it needs it

---

## Step 1: Create Adventure Structure

### Directory Setup

Create this folder structure in your backend:

```
backend/adventures/
├── lost_mines_of_phandelver/
│   ├── adventure.json
│   ├── chapters/
│   │   ├── ch01_goblin_arrows.json
│   │   ├── ch02_phandalin.json
│   │   ├── ch03_spider_threat.json
│   │   ├── ch04_wave_echo_cave.json
│   │   └── ch05_showdown.json
│   ├── locations/
│   │   ├── cragmaw_hideout.json
│   │   ├── redbrand_hideout.json
│   │   ├── phandalin_town.json
│   │   ├── tresendar_manor.json
│   │   ├── wave_echo_cave.json
│   │   └── cragmaw_castle.json
│   ├── npcs/
│   │   ├── gundren_rockseeker.json
│   │   ├── sildar_hallwinter.json
│   │   ├── glasstaff.json
│   │   ├── klarg.json
│   │   └── black_spider.json
│   ├── encounters/
│   │   └── random_encounters.json
│   └── mechanics/
│       └── special_rules.json
└── curse_of_strahd/
    └── (similar structure)
```

---

## Step 2: Create Adventure Metadata File

**File:** `backend/adventures/lost_mines_of_phandelver/adventure.json`

```json
{
  "name": "Lost Mines of Phandelver",
  "description": "A classic D&D adventure for levels 1-5. The party seeks the lost Wave Echo Cave.",
  
  "current_chapter": "ch01_goblin_arrows",
  "current_location": "triboar_trail",
  "session_number": 1,
  "party_level": 1,
  
  "campaign_summary": "The party has been hired to escort supplies to Phandalin.",
  "milestone": "Journey begins",
  
  "active_quests": [
    {
      "id": "deliver_supplies",
      "name": "Deliver Supplies to Phandalin",
      "status": "active",
      "giver": "Gundren Rockseeker",
      "reward": "10gp each"
    }
  ],
  
  "completed_quests": [],
  
  "discovered_locations": [
    "neverwinter",
    "triboar_trail"
  ],
  
  "met_npcs": [
    "gundren_rockseeker"
  ],
  
  "important_events": [
    "Hired by Gundren Rockseeker",
    "Left Neverwinter"
  ],
  
  "party_relationships": {
    "gundren_rockseeker": "friendly"
  },
  
  "world_state": {
    "redbrands_active": true,
    "gundren_captured": false,
    "wave_echo_cave_location_known": false
  }
}
```

---

## Step 3: Create Chapter Files

**File:** `backend/adventures/lost_mines_of_phandelver/chapters/ch01_goblin_arrows.json`

```json
{
  "id": "ch01_goblin_arrows",
  "name": "Chapter 1: Goblin Arrows",
  "level_range": "1-2",
  
  "overview": "The party is ambushed by goblins on the Triboar Trail. They discover Gundren and Sildar have been captured.",
  
  "objectives": [
    "Survive the goblin ambush",
    "Rescue Sildar from Cragmaw Hideout",
    "Learn about Gundren's capture"
  ],
  
  "key_locations": [
    "triboar_trail",
    "cragmaw_hideout"
  ],
  
  "key_npcs": [
    "sildar_hallwinter",
    "klarg",
    "yeemik"
  ],
  
  "main_quest": {
    "id": "rescue_sildar",
    "name": "Rescue Sildar Hallwinter",
    "trigger": "Find Sildar's tracks at ambush site",
    "completion": "Free Sildar from Cragmaw Hideout",
    "reward": "Information about Gundren, Sildar's gratitude"
  },
  
  "next_chapter_trigger": "Arrive in Phandalin",
  "next_chapter": "ch02_phandalin"
}
```

---

## Step 4: Create Location Files

**File:** `backend/adventures/lost_mines_of_phandelver/locations/cragmaw_hideout.json`

```json
{
  "id": "cragmaw_hideout",
  "name": "Cragmaw Hideout",
  "type": "dungeon",
  "description": "A cave complex hidden in the hills, used by the Cragmaw goblin tribe.",
  
  "atmosphere": "Dark, damp, smells of goblin refuse and wet fur. Sounds of dripping water and goblin chatter echo through passages.",
  
  "entrance": {
    "description": "A shallow stream flows from the cave mouth. Goblin tracks are visible in the mud.",
    "hidden": false,
    "dc_to_find": 0
  },
  
  "areas": {
    "cave_mouth": {
      "description": "A stream flows out of the cave. The entrance is wide enough for two people side-by-side.",
      "features": ["Flowing stream", "Muddy banks", "Goblin tracks"],
      "connections": ["stream_passage"],
      "encounter": null
    },
    
    "goblin_den": {
      "description": "A large cavern with crude bedrolls and refuse scattered about. Three goblins lounge here.",
      "features": ["Campfire", "Sleeping goblins", "Stolen supplies"],
      "connections": ["stream_passage", "klargs_cave"],
      "encounter": {
        "type": "goblins",
        "count": 3,
        "hp": [7, 7, 7],
        "tactics": "Raise alarm if they see intruders"
      }
    },
    
    "klargs_cave": {
      "description": "The chieftain's cave. A large bugbear sits on a pile of furs, a wolf at his side.",
      "features": ["Treasure chest", "Animal pelts", "Crude throne"],
      "connections": ["goblin_den"],
      "encounter": {
        "type": "boss",
        "enemies": [
          {"name": "Klarg", "type": "bugbear", "hp": 27},
          {"name": "Wolf", "type": "wolf", "hp": 11}
        ],
        "tactics": "Klarg fights viciously. Wolf attacks weakest-looking PC."
      },
      "npcs_present": ["sildar_hallwinter"]
    }
  },
  
  "treasure": [
    {
      "location": "klargs_cave",
      "items": ["600cp", "110sp", "50ep", "2 potions of healing"],
      "container": "Unlocked chest"
    }
  ],
  
  "secrets": [
    {
      "location": "goblin_den",
      "description": "Crack in wall leads to escape route",
      "dc": 15,
      "skill": "Investigation"
    }
  ],
  
  "completion_rewards": {
    "xp": 200,
    "story": "Sildar rescued, learns about Gundren's capture"
  }
}
```

---

## Step 5: Create NPC Files

**File:** `backend/adventures/lost_mines_of_phandelver/npcs/sildar_hallwinter.json`

```json
{
  "id": "sildar_hallwinter",
  "name": "Sildar Hallwinter",
  "title": "Member of the Lords' Alliance",
  "race": "Human",
  "class": "Fighter",
  "level": 4,
  
  "personality": {
    "traits": ["Honorable", "Brave", "Loyal", "Formal"],
    "goals": ["Find Iarno Albrek", "Help Gundren", "Bring order to Phandalin"],
    "fears": ["Failing his duty", "Gundren's death"],
    "mannerisms": "Stands at attention. Speaks formally. Uses military terms."
  },
  
  "background": "A veteran warrior and agent of the Lords' Alliance. Traveling with Gundren to help establish order in Phandalin.",
  
  "dialogue_examples": [
    "\"I am in your debt. Those goblins would have been the death of me.\"",
    "\"Gundren is my friend. We must find him before the Black Spider does.\"",
    "\"I was sent to find Iarno Albrek, my fellow agent. He was meant to be in Phandalin.\""
  ],
  
  "voice_style": "Formal, military bearing. Says 'sir' and 'ma'am'. Speaks in complete sentences.",
  
  "current_situation": {
    "location": "cragmaw_hideout",
    "status": "captured",
    "injuries": "Beaten, 5 HP remaining"
  },
  
  "information_known": [
    "Gundren was captured by goblins",
    "Gundren mentioned 'Wave Echo Cave' before capture",
    "The goblins work for someone called 'The Black Spider'",
    "Iarno Albrek was sent to Phandalin months ago and hasn't reported back"
  ],
  
  "rewards_can_offer": {
    "immediate": "Information about Gundren and the Black Spider",
    "future": "50gp for finding Iarno (when in Phandalin)"
  },
  
  "relationship_tracking": {
    "initial_attitude": "grateful",
    "trust_level": 5,
    "notes": "Will become ally if party helps him"
  }
}
```

---

## Step 6: Implement Context Loader

**Copy the code from ADVENTURE_STRUCTURE_GUIDE.md**

Create: `backend/services/adventure_context.py`

Then add these helper methods:

```python
class AdventureContext:
    # ... (existing code from guide) ...
    
    def handle_location_transition(self, new_location_id: str) -> str:
        """
        Handle moving to a new location
        Returns description of new location
        """
        self.update_location(new_location_id)
        location = self._load_location(new_location_id)
        
        return f"""LOCATION TRANSITION:

You arrive at: {location['name']}

{location['description']}

Atmosphere: {location['atmosphere']}

{f"Areas visible: {', '.join(location.get('areas', {}).keys())}" if location.get('areas') else ""}
"""
    
    def handle_npc_interaction(self, npc_id: str) -> str:
        """
        Handle talking to an NPC
        Returns NPC info for DM to roleplay
        """
        npc = self._load_npc(npc_id)
        
        # Track that party met this NPC
        if npc_id not in self.metadata.get("met_npcs", []):
            self.metadata.setdefault("met_npcs", []).append(npc_id)
            self.save_metadata()
        
        return f"""NPC INTERACTION:

Name: {npc['name']} - {npc.get('title', '')}
Personality: {', '.join(npc['personality']['traits'])}
Voice: {npc['voice_style']}
Goals: {', '.join(npc['personality']['goals'])}

Current Situation: {npc.get('current_situation', {}).get('status', 'normal')}

Information they know:
{chr(10).join('- ' + info for info in npc.get('information_known', []))}

Example dialogue:
"{npc['dialogue_examples'][0]}"
"""
    
    def get_encounter_details(self, location_id: str, area_id: str) -> Optional[Dict]:
        """
        Get encounter details for a specific area
        Returns None if no encounter
        """
        location = self._load_location(location_id)
        
        if area_id in location.get("areas", {}):
            area = location["areas"][area_id]
            return area.get("encounter")
        
        return None
    
    def complete_quest(self, quest_id: str):
        """Mark a quest as completed"""
        for quest in self.metadata.get("active_quests", []):
            if quest["id"] == quest_id:
                quest["status"] = "completed"
                # Move to completed quests
                self.metadata.setdefault("completed_quests", []).append(quest)
                self.metadata["active_quests"].remove(quest)
                break
        
        self.save_metadata()
    
    def advance_chapter(self, new_chapter_id: str):
        """Move to next chapter"""
        self.metadata["current_chapter"] = new_chapter_id
        self.add_event(f"Advanced to {new_chapter_id}")
        self.save_metadata()
```

---

## Step 7: Update DM Agent Integration

**Update:** `backend/services/dm_agent.py`

```python
from typing import Optional
from services.adventure_context import AdventureContext

class DMAgent:
    def __init__(self, adventure_name: Optional[str] = None):
        self.client = AnthropicClient()
        self.executor = ToolExecutor()
        self.conversation_history = []
        
        # Load adventure context
        self.adventure = None
        if adventure_name:
            self.adventure = AdventureContext(adventure_name)
    
    def process_action(self, action: str, game_state: Dict[str, Any]):
        """Process player action with adventure context"""
        
        # Detect action type
        context_type = self._detect_context(action, game_state)
        
        # Build game state with adventure context
        if self.adventure:
            # Get current adventure context
            game_state["adventure_context"] = self.adventure.get_current_context()
            
            # Handle specific interactions
            action_lower = action.lower()
            
            # Location changes
            if any(word in action_lower for word in ["enter", "go to", "approach", "move to"]):
                # Try to extract location from action
                # (You'd implement smarter parsing here)
                if "cave" in action_lower:
                    location_desc = self.adventure.handle_location_transition("cragmaw_hideout")
                    game_state["location_transition"] = location_desc
            
            # NPC interactions
            if any(word in action_lower for word in ["talk to", "speak with", "ask"]):
                # Extract NPC name
                if "sildar" in action_lower:
                    npc_info = self.adventure.handle_npc_interaction("sildar_hallwinter")
                    game_state["npc_interaction"] = npc_info
            
            # Investigation
            if any(word in action_lower for word in ["search", "investigate", "look around"]):
                # Get detailed location info
                location_details = self.adventure.get_location_details()
                game_state["investigation_details"] = location_details
        
        # Add to conversation
        self.conversation_history.append({
            "role": "user",
            "content": action
        })
        
        # Generate response
        ai_response = self.client.generate(
            messages=self.conversation_history,
            game_state=game_state,
            context_type=context_type
        )
        
        # ... rest of existing code ...
        
        # Track important events
        if self.adventure and ai_response.get("tool_calls"):
            # Record significant actions
            if any(tool["name"] == "attack_roll" for tool in ai_response["tool_calls"]):
                self.adventure.add_event(f"Combat: {action}")
        
        return {
            "narration": final_narration,
            "tool_results": tool_results,
            "updated_state": game_state
        }
    
    def start_adventure(self, adventure_intro: str, game_state: Dict[str, Any]):
        """Start adventure with context"""
        
        if self.adventure:
            # Get starting context
            game_state["adventure_context"] = self.adventure.get_current_context()
        
        # Clear history
        self.conversation_history = []
        
        # Generate opening
        response = self.client.generate(
            messages=[{
                "role": "user",
                "content": f"Start this D&D adventure: {adventure_intro}"
            }],
            game_state=game_state,
            context_type="scene_description"
        )
        
        self.conversation_history.append({
            "role": "user",
            "content": f"Start this D&D adventure: {adventure_intro}"
        })
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response["content"]
        })
        
        return {
            "narration": response["content"],
            "tool_results": [],
            "updated_state": game_state
        }
```

---

## Step 8: Update Backend API

**Update:** `backend/main.py`

```python
from typing import Optional

# Global adventure
current_adventure: Optional[str] = None

@app.post("/adventure/load")
def load_adventure(request: dict):
    """Load an adventure module"""
    global current_adventure
    
    adventure_name = request.get("adventure_name")
    
    try:
        # Initialize DM with adventure
        global dm
        dm = DMAgent(adventure_name=adventure_name)
        current_adventure = adventure_name
        
        return {
            "success": True,
            "message": f"Loaded adventure: {adventure_name}",
            "metadata": dm.adventure.metadata
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to load adventure: {e}")

@app.get("/adventure/status")
def get_adventure_status():
    """Get current adventure state"""
    if not current_adventure or not dm.adventure:
        return {"adventure_loaded": False}
    
    return {
        "adventure_loaded": True,
        "name": dm.adventure.metadata["name"],
        "current_chapter": dm.adventure.metadata["current_chapter"],
        "current_location": dm.adventure.metadata["current_location"],
        "active_quests": dm.adventure.metadata.get("active_quests", []),
        "party_level": dm.adventure.metadata.get("party_level", 1)
    }

@app.post("/adventure/update")
def update_adventure(request: dict):
    """Update adventure state"""
    if not dm.adventure:
        raise HTTPException(400, "No adventure loaded")
    
    updates = request.get("updates", {})
    
    if "location" in updates:
        dm.adventure.update_location(updates["location"])
    
    if "event" in updates:
        dm.adventure.add_event(updates["event"])
    
    if "complete_quest" in updates:
        dm.adventure.complete_quest(updates["complete_quest"])
    
    if "advance_chapter" in updates:
        dm.adventure.advance_chapter(updates["advance_chapter"])
    
    return {
        "success": True,
        "metadata": dm.adventure.metadata
    }
```

---

## Step 9: Update Frontend

**Add to your frontend API service:**

```typescript
// Load adventure at session start
export async function loadAdventure(adventureName: string) {
  const response = await fetch('http://localhost:8000/adventure/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ adventure_name: adventureName })
  });
  
  return response.json();
}

// Get adventure status
export async function getAdventureStatus() {
  const response = await fetch('http://localhost:8000/adventure/status');
  return response.json();
}

// Start adventure
export async function startAdventure() {
  // First load the adventure
  await loadAdventure('lost_mines_of_phandelver');
  
  // Then start playing
  const response = await fetch('http://localhost:8000/dm/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      intro: "The party has been hired to escort supplies to Phandalin.",
      game_state: {
        party: ["Thorin", "Elara"],
        party_level: 1
      }
    })
  });
  
  return response.json();
}
```

---

## Step 10: Testing

**Create:** `backend/test_adventure.py`

```python
"""
Test adventure context system
"""

from services.adventure_context import AdventureContext
from services.dm_agent import DMAgent

def test_adventure_loading():
    print("=== Testing Adventure Context ===\n")
    
    # Load Lost Mines
    adventure = AdventureContext("lost_mines_of_phandelver")
    
    # Get current context
    context = adventure.get_current_context()
    print("Current Context:")
    print(context)
    print(f"\nContext size: ~{len(context.split())} words")
    print(f"Estimated tokens: ~{len(context.split()) * 1.3:.0f}")
    
    print("\n" + "="*60 + "\n")
    
    # Test location transition
    print("=== Moving to Cragmaw Hideout ===\n")
    location_desc = adventure.handle_location_transition("cragmaw_hideout")
    print(location_desc)
    
    print("\n" + "="*60 + "\n")
    
    # Test NPC interaction
    print("=== Talking to Sildar ===\n")
    npc_info = adventure.handle_npc_interaction("sildar_hallwinter")
    print(npc_info)
    
    print("\n" + "="*60 + "\n")
    
    # Test with DM Agent
    print("=== Full DM Integration Test ===\n")
    
    dm = DMAgent(adventure_name="lost_mines_of_phandelver")
    
    result = dm.start_adventure(
        "The party is traveling on the Triboar Trail toward Phandalin.",
        {"party": ["Thorin", "Elara"], "party_level": 1}
    )
    
    print("DM Opening:")
    print(result["narration"])

if __name__ == "__main__":
    test_adventure_loading()
```

Run:
```bash
cd backend
python test_adventure.py
```

---

## Step 11: How the AI Uses Adventures

### When Starting:

```
Player: Start Lost Mines of Phandelver

Backend loads: lost_mines_of_phandelver/adventure.json
Current context sent to AI:
  - Chapter: "Goblin Arrows"
  - Location: "Triboar Trail"  
  - Quest: "Deliver supplies"
  - Total: ~1,000 tokens

AI generates opening based on this context
```

### During Play:

```
Player: "We investigate the dead horses"

Backend sends to AI:
  - Current context (chapter, location, quests)
  - Investigation details (tracks, arrows, etc.)
  - Total: ~1,500 tokens

AI calls skill_check tool
AI narrates results using adventure context
```

### Location Changes:

```
Player: "We follow the tracks to the cave"

Backend:
  1. Detects location change
  2. Updates current_location to "cragmaw_hideout"
  3. Loads cave description
  4. Sends to AI

AI receives:
  - New location description
  - Cave atmosphere
  - First area details
  - Total: ~1,200 tokens

AI describes cave entrance dramatically
```

### NPC Interactions:

```
Player: "I talk to Sildar"

Backend:
  1. Detects NPC interaction
  2. Loads Sildar's file on-demand
  3. Sends personality, dialogue, info to AI

AI receives:
  - Sildar's personality traits
  - Example dialogue
  - Information he knows
  - Voice style
  - Total: ~800 tokens

AI roleplays Sildar accurately
```

---

## Token Usage Example

### Without Adventure System:
```
Full Lost Mines text: 50,000 tokens
Cost per turn: $0.15
Session (40 turns): $6.00
Year (52 sessions): $312
```

### With Adventure System:
```
Current context: 1,000 tokens
Cost per turn: $0.01
Session (40 turns): $0.40
Year (52 sessions): $21
```

**Savings: 93%**

---

## Summary

**What Cursor should implement:**

1. ✅ Create adventure folder structure
2. ✅ Add JSON files for chapters, locations, NPCs
3. ✅ Implement AdventureContext class
4. ✅ Update DMAgent to use adventure context
5. ✅ Add API endpoints for adventure management
6. ✅ Update frontend to load adventures
7. ✅ Test with Lost Mines

**Result:**
- AI can run full campaigns
- Only loads relevant context
- Costs stay low
- Easy to add new adventures

**Like having the adventure module as a "codebase" the AI can reference!** 🎲

---

## Quick Start Command

Tell Cursor:

```
Implement the adventure structure system:
1. Create the folder structure in backend/adventures/
2. Add the example JSON files for Lost Mines of Phandelver
3. Implement adventure_context.py
4. Update dm_agent.py to use adventure context
5. Add the new API endpoints
6. Test with test_adventure.py
```

The AI will have intelligent context awareness for running full campaigns!
