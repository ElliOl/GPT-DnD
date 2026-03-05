# Adventure Structure System - Running Full Campaigns Efficiently

## The Problem

Large adventure modules like **Curse of Strahd** (256 pages, ~200k tokens) cannot be loaded into context every turn:
- Cost: $0.60 per turn = $24/session = $1,248/year ❌
- Context limit: Exceeds Claude's window
- Performance: Slow, wasteful

## The Solution: Modular Adventure Architecture

Structure adventures like **code** - load only what's needed, when needed.

---

## 1. Adventure File Structure

### Example: Curse of Strahd

```
backend/adventures/curse_of_strahd/
├── adventure.json              # Metadata, current state
├── chapters/
│   ├── ch01_barovia.json       # Chapter-level info
│   ├── ch02_old_bonegrinder.json
│   ├── ch03_vallaki.json
│   ├── ch04_kresk.json
│   ├── ch05_castle_ravenloft.json
│   └── ...
├── locations/
│   ├── death_house.json        # Detailed locations
│   ├── village_of_barovia.json
│   ├── tser_pool.json
│   ├── vallaki_town.json
│   └── ...
├── npcs/
│   ├── strahd_von_zarovich.json
│   ├── ireena_kolyana.json
│   ├── ismark_kolyanovich.json
│   ├── madam_eva.json
│   └── ...
├── encounters/
│   ├── random_encounters.json
│   ├── scripted_events.json
│   └── set_pieces/
│       ├── death_house_escape.json
│       ├── strahd_first_appearance.json
│       └── ...
├── items/
│   ├── sunsword.json
│   ├── holy_symbol_of_ravenkind.json
│   ├── tome_of_strahd.json
│   └── ...
└── mechanics/
    ├── dark_powers.json
    ├── tarokka_reading.json
    ├── madness_effects.json
    └── ...
```

---

## 2. Adventure Metadata File

`adventure.json` - Tracks campaign state:

```json
{
  "name": "Curse of Strahd",
  "current_chapter": "ch01_barovia",
  "current_location": "village_of_barovia",
  "session_number": 12,
  "
_summary": "Party has entered Barovia, met Ismark, agreed to escort Ireena",
  
  "party_level": 3,
  "milestone": "Rescued Ireena from Strahd's attack",
  
  "active_quests": [
    {
      "id": "escort_ireena",
      "name": "Escort Ireena to Vallaki",
      "status": "active",
      "location": "village_of_barovia"
    },
    {
      "id": "explore_death_house",
      "name": "Investigate Death House",
      "status": "completed"
    }
  ],
  
  "discovered_locations": [
    "village_of_barovia",
    "death_house",
    "church_of_barovia"
  ],
  
  "met_npcs": [
    "ismark_kolyanovich",
    "ireena_kolyana",
    "father_donavich"
  ],
  
  "important_events": [
    "Received Tarokka reading from Madam Eva",
    "Strahd appeared at church",
    "Found letter in Death House"
  ],
  
  "strahd_relationship": {
    "encounters": 2,
    "attitude": "curious",
    "knows_party": true
  }
}
```

---

## 3. Chapter File Example

`chapters/ch01_barovia.json`:

```json
{
  "id": "ch01_barovia",
  "name": "Chapter 1: Into the Mists",
  
  "overview": "The party enters Barovia, a cursed land ruled by Strahd. They meet Ismark and Ireena in the village.",
  
  "key_locations": [
    "village_of_barovia",
    "death_house",
    "church_of_barovia",
    "blood_of_the_vine_tavern"
  ],
  
  "key_npcs": [
    "ismark_kolyanovich",
    "ireena_kolyana",
    "father_donavich",
    "bildrath"
  ],
  
  "main_quests": [
    {
      "id": "escort_ireena",
      "trigger": "Talk to Ismark",
      "objective": "Escort Ireena safely to Vallaki",
      "reward": "Ismark's gratitude, safe haven in Vallaki"
    }
  ],
  
  "optional_content": [
    "death_house",
    "donavich_rescue_son"
  ],
  
  "strahd_appearances": [
    {
      "trigger": "First night in Barovia",
      "location": "any",
      "purpose": "Observe party, gauge threat"
    },
    {
      "trigger": "Attempting to leave Barovia",
      "location": "church",
      "purpose": "Show power, claim Ireena"
    }
  ],
  
  "next_chapter": "ch02_old_bonegrinder"
}
```

---

## 4. Location File Example

`locations/death_house.json`:

```json
{
  "id": "death_house",
  "name": "Death House",
  "type": "dungeon",
  
  "description": "A dilapidated mansion on the outskirts of the Village of Barovia. Once home to the Durst family, now a cursed haunted house.",
  
  "atmosphere": "Oppressive, creepy, Gothic horror. Mist seeps through cracks. Portraits watch visitors. Children's laughter echoes.",
  
  "areas": {
    "entrance": {
      "description": "Grand foyer with twin marble staircases. Dust covers everything. A large chandelier hangs precariously.",
      "features": ["Coat of arms", "Dusty furniture", "Creaking stairs"],
      "secrets": ["Hidden door behind coat of arms (DC 15 Investigation)"],
      "encounters": null
    },
    
    "dining_room": {
      "description": "Long table set for a feast that never happened. Food has rotted to dust.",
      "features": ["Silverware", "Crystal glasses", "Portrait of family"],
      "secrets": null,
      "encounters": {
        "type": "specter",
        "trigger": "Touching silverware",
        "count": 1
      }
    },
    
    "basement": {
      "description": "Stone walls weep with moisture. The air is thick with the smell of decay and old blood.",
      "features": ["Cult altar", "Sacrificial pit", "Ritual circle"],
      "secrets": null,
      "encounters": {
        "type": "shambling_mound",
        "trigger": "Approaching altar",
        "count": 1,
        "special": "Made from flesh of Durst family"
      }
    }
  },
  
  "treasure": [
    {"item": "Letter from Strahd", "location": "master_bedroom"},
    {"item": "Deed to windmill", "location": "hidden_library"},
    {"item": "200gp in old coins", "location": "basement_chest"}
  ],
  
  "escape_challenge": {
    "trigger": "Taking anything from basement",
    "description": "House comes alive! Walls close in, doors slam shut, smoke fills rooms.",
    "skill_checks": [
      {"skill": "Athletics", "dc": 15, "purpose": "Force doors open"},
      {"skill": "Acrobatics", "dc": 12, "purpose": "Dodge falling debris"}
    ],
    "consequence": "2d6 bludgeoning damage from collapsing house"
  }
}
```

---

## 5. NPC File Example

`npcs/strahd_von_zarovich.json`:

```json
{
  "id": "strahd_von_zarovich",
  "name": "Count Strahd von Zarovich",
  "title": "The Devil Strahd, Lord of Barovia",
  
  "personality": {
    "traits": ["Arrogant", "Charismatic", "Tragic", "Calculating"],
    "goals": ["Win Ireena's love", "Break his curse", "Entertain himself with worthy foes"],
    "fears": ["True love's rejection", "Symbols of Ravenloft", "Sunsword"],
    "mannerisms": "Speaks formally, Old World charm. Smiles rarely but genuinely. Never raises voice."
  },
  
  "dialogue_examples": [
    "\"I have learned much. But the lesson I learned most of all is that I am eternal. I cannot be destroyed. Not by you, not by anyone.\"",
    "\"I am The Ancient, I am The Land. My beginnings are lost in the darkness of the past.\"",
    "\"She looks like her. My beloved. Perhaps this time...\""
  ],
  
  "tactics": {
    "first_encounter": "Observe from distance. Be charming. Show power subtly.",
    "early_game": "Toy with party. Test their capabilities. Appear in dreams.",
    "mid_game": "Direct confrontation if party threatens his plans. Offer deals.",
    "end_game": "Full power. No mercy if party has artifacts or threatens Ireena."
  },
  
  "stat_block_reference": "Monster Manual p. 297 - Vampire",
  "special_abilities": ["Lair actions in Castle Ravenloft", "Scrying", "Charm", "Summon wolves/bats/swarms"],
  
  "relationship_tracking": {
    "respect_threshold": 5,
    "current_respect": 0,
    "notes": "Gains respect for: clever tactics, sparing innocents, standing up to him. Loses respect for: cowardice, harming Ireena."
  }
}
```

---

## 6. Context Loader System

Create `backend/services/adventure_context.py`:

```python
"""
Adventure Context Loader
Dynamically loads only relevant adventure content
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class AdventureContext:
    def __init__(self, adventure_name: str):
        self.adventure_dir = Path(f"adventures/{adventure_name}")
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load adventure metadata"""
        with open(self.adventure_dir / "adventure.json") as f:
            return json.load(f)
    
    def save_metadata(self):
        """Save updated metadata"""
        with open(self.adventure_dir / "adventure.json", 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def get_current_context(self) -> str:
        """
        Get ONLY the context needed for current situation
        
        Returns concise context string (~500-1000 tokens instead of 200k!)
        """
        
        context_parts = []
        
        # 1. Current chapter overview (small)
        chapter = self._load_chapter(self.metadata["current_chapter"])
        context_parts.append(f"CHAPTER: {chapter['name']}")
        context_parts.append(f"Overview: {chapter['overview']}")
        
        # 2. Current location (medium)
        location = self._load_location(self.metadata["current_location"])
        context_parts.append(f"\nCURRENT LOCATION: {location['name']}")
        context_parts.append(f"Description: {location['description']}")
        context_parts.append(f"Atmosphere: {location['atmosphere']}")
        
        # 3. Active quests (small)
        active_quests = [q for q in self.metadata["active_quests"] if q["status"] == "active"]
        if active_quests:
            context_parts.append("\nACTIVE QUESTS:")
            for quest in active_quests:
                context_parts.append(f"- {quest['name']}")
        
        # 4. Nearby NPCs (if any)
        nearby_npcs = self._get_nearby_npcs(location)
        if nearby_npcs:
            context_parts.append("\nNEARBY NPCs:")
            for npc in nearby_npcs:
                context_parts.append(f"- {npc['name']}: {npc['personality']['traits'][0]}")
        
        # 5. Recent events (context continuity)
        if self.metadata["important_events"]:
            recent = self.metadata["important_events"][-3:]  # Last 3 events
            context_parts.append("\nRECENT EVENTS:")
            for event in recent:
                context_parts.append(f"- {event}")
        
        return "\n".join(context_parts)
    
    def _load_chapter(self, chapter_id: str) -> Dict[str, Any]:
        """Load chapter file"""
        with open(self.adventure_dir / "chapters" / f"{chapter_id}.json") as f:
            return json.load(f)
    
    def _load_location(self, location_id: str) -> Dict[str, Any]:
        """Load location file"""
        with open(self.adventure_dir / "locations" / f"{location_id}.json") as f:
            return json.load(f)
    
    def _load_npc(self, npc_id: str) -> Dict[str, Any]:
        """Load NPC file"""
        with open(self.adventure_dir / "npcs" / f"{npc_id}.json") as f:
            return json.load(f)
    
    def _get_nearby_npcs(self, location: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get NPCs present at current location"""
        # Check location's NPC list or global NPC locations
        npc_ids = location.get("present_npcs", [])
        return [self._load_npc(npc_id) for npc_id in npc_ids if npc_id]
    
    def get_location_details(self, area_id: Optional[str] = None) -> str:
        """
        Get detailed info about specific area when player investigates
        
        Only called when needed (player says "I search the room")
        """
        location = self._load_location(self.metadata["current_location"])
        
        if area_id and area_id in location.get("areas", {}):
            area = location["areas"][area_id]
            details = [
                f"AREA: {area_id}",
                f"Description: {area['description']}",
                f"Features: {', '.join(area['features'])}"
            ]
            
            if area.get("secrets"):
                details.append(f"Hidden: {', '.join(area['secrets'])}")
            
            if area.get("encounters"):
                enc = area["encounters"]
                details.append(f"Encounter: {enc['count']}x {enc['type']} (triggered by: {enc['trigger']})")
            
            return "\n".join(details)
        
        # Return general location info
        return f"{location['description']}\n\nAreas: {', '.join(location.get('areas', {}).keys())}"
    
    def get_npc_info(self, npc_id: str) -> str:
        """
        Get NPC details when party interacts with them
        """
        npc = self._load_npc(npc_id)
        
        info = [
            f"NPC: {npc['name']} - {npc.get('title', '')}",
            f"Personality: {', '.join(npc['personality']['traits'])}",
            f"Goals: {', '.join(npc['personality']['goals'])}",
            f"Mannerisms: {npc['personality']['mannerisms']}"
        ]
        
        if npc.get("dialogue_examples"):
            info.append(f"\nExample dialogue: {npc['dialogue_examples'][0]}")
        
        return "\n".join(info)
    
    def update_location(self, new_location_id: str):
        """Update current location"""
        self.metadata["current_location"] = new_location_id
        
        # Track discovered locations
        if new_location_id not in self.metadata.get("discovered_locations", []):
            self.metadata.setdefault("discovered_locations", []).append(new_location_id)
        
        self.save_metadata()
    
    def add_event(self, event_description: str):
        """Track important events"""
        self.metadata.setdefault("important_events", []).append(event_description)
        
        # Keep only last 20 events to prevent bloat
        self.metadata["important_events"] = self.metadata["important_events"][-20:]
        
        self.save_metadata()
    
    def update_quest(self, quest_id: str, new_status: str):
        """Update quest status"""
        for quest in self.metadata.get("active_quests", []):
            if quest["id"] == quest_id:
                quest["status"] = new_status
                break
        
        self.save_metadata()


# Example usage
if __name__ == "__main__":
    # Load Curse of Strahd
    cos = AdventureContext("curse_of_strahd")
    
    # Get current context (only ~1000 tokens!)
    context = cos.get_current_context()
    print(context)
    print(f"\nContext size: ~{len(context.split())} words (~{len(context.split()) * 1.3:.0f} tokens)")
    
    # When player enters a room
    room_details = cos.get_location_details("dining_room")
    print(f"\n{room_details}")
    
    # When talking to NPC
    npc_info = cos.get_npc_info("strahd_von_zarovich")
    print(f"\n{npc_info}")
```

---

## 7. Integration with DM Agent

Update `dm_agent.py` to use adventure context:

```python
from services.adventure_context import AdventureContext

class DMAgent:
    def __init__(self, adventure_name: Optional[str] = None):
        self.client = AnthropicClient()
        self.executor = ToolExecutor()
        self.conversation_history = []
        
        # Load adventure if specified
        self.adventure = AdventureContext(adventure_name) if adventure_name else None
    
    def process_action(self, action: str, game_state: Dict[str, Any]):
        # Get adventure context (only current relevant info!)
        adventure_context = None
        if self.adventure:
            adventure_context = self.adventure.get_current_context()
            
            # Add to game state
            game_state["adventure_context"] = adventure_context
        
        # Detect context type
        context_type = self._detect_context(action, game_state)
        
        # If player is investigating/talking to NPC, load specific details
        if "talk to" in action.lower() or "speak with" in action.lower():
            # Extract NPC name from action
            npc_name = self._extract_npc_name(action)
            if npc_name and self.adventure:
                npc_info = self.adventure.get_npc_info(npc_name)
                game_state["npc_details"] = npc_info
        
        # Continue with normal flow...
        ai_response = self.client.generate(
            messages=self.conversation_history,
            game_state=game_state,
            context_type=context_type
        )
        
        # ... rest of method
```

---

## 8. Token Usage Comparison

### Loading Full Module (BAD):
```
Input per turn:
- System prompt: 2,000 tokens
- Full Curse of Strahd: 200,000 tokens
- Game state: 1,000 tokens
Total: 203,000 tokens × $3/M = $0.61 per turn
```

### Loading Only Current Context (GOOD):
```
Input per turn:
- System prompt: 2,000 tokens (cached)
- Current context: 1,000 tokens
- Game state: 500 tokens
Total: 3,500 tokens × $3/M = $0.01 per turn
```

**Savings: 98%!**

---

## 9. How to Structure Your Own Adventures

### Step 1: Break into Chunks
- One file per chapter
- One file per major location
- One file per important NPC

### Step 2: Identify What's Needed When
- **Always loaded:** Current chapter, current location, active quests
- **On-demand:** Specific room details, NPC dialogue, encounter stats
- **Never loaded:** Future chapters, distant locations, unused content

### Step 3: Keep Files Small
- Chapters: 200-500 tokens each
- Locations: 300-800 tokens each
- NPCs: 200-400 tokens each
- **Total current context: 1,000-2,000 tokens**

### Step 4: Track State
- What chapter/location are we in?
- What quests are active?
- What NPCs have been met?
- What events have happened?

---

## 10. Example: Starting Curse of Strahd

```python
# Initialize adventure
dm = DMAgent(adventure_name="curse_of_strahd")

# Start game
result = dm.start_adventure(
    "The party is traveling through a misty forest when they enter Barovia.",
    game_state={
        "party": ["Thorin", "Elara"],
        "party_level": 3
    }
)

# Claude receives:
# - DM system prompt (cached)
# - D&D rules (cached)
# - Current chapter: "Into the Mists" overview
# - Current location: "Village of Barovia" description
# - Active quests: None yet
# - Recent events: None yet
# Total: ~3,000 tokens (vs 200,000!)

# Claude generates:
"Thick fog rolls through the dark forest. The trees seem to 
watch you with twisted, gnarled faces. Ahead, through the mist, 
you see the dim lights of a village. A weathered sign reads: 
'Welcome to Barovia.' The air feels heavy, oppressive, as if 
the land itself is holding its breath.

What do you do?"
```

---

## 11. Handling Dynamic Content

### When Strahd Appears:

```python
# In your code
if strahd_should_appear(situation):
    # Load Strahd's NPC file on-demand
    strahd_info = adventure.get_npc_info("strahd_von_zarovich")
    game_state["special_npc"] = strahd_info
    
    # Claude now has Strahd's personality, dialogue examples, tactics
    # Only when needed!
```

### When Entering New Location:

```python
# Player says: "We enter Death House"
adventure.update_location("death_house")

# Next turn, Claude gets:
# - Death House description
# - Atmosphere
# - First room details
# Not the entire dungeon at once!
```

---

## Summary

**The Strategy:**
1. ✅ Break adventure into small JSON files
2. ✅ Load only current chapter + location + active quests
3. ✅ Pull specific details on-demand
4. ✅ Track state in metadata file
5. ✅ Update context as party progresses

**The Result:**
- Full campaign playable ✅
- Costs stay low (~$0.01/turn vs $0.61) ✅
- Context stays relevant ✅
- No manual "reading" needed ✅

**Like Cursor** but better - the AI gets exactly what it needs, when it needs it, automatically! 🎲

Want me to create a starter Curse of Strahd structure for you?
