# Lost Mine of Phandelver - Modular Adventure Structure

Complete D&D 5E adventure broken into efficient, loadable modules following the Adventure Structure Guide principles.

## 📁 Directory Structure

```
lost_mine_phandelver/
├── adventure.json                 # Campaign metadata & state tracking
├── context_loader.py              # Python loader - gets only current context
├── chapters/                      # 4 adventure parts
│   ├── part1_goblin_arrows.json
│   ├── part2_phandalin.json
│   ├── part3_spiders_web.json
│   └── part4_wave_echo_cave.json
├── locations/                     # Detailed location files
│   ├── cragmaw_hideout.json
│   ├── phandalin_town.json
│   ├── redbrand_hideout.json      # TODO
│   ├── cragmaw_castle.json        # TODO
│   ├── thundertree.json           # TODO
│   ├── wave_echo_cave.json        # TODO
│   └── ...
├── npcs/                          # NPC personality & info
│   ├── sildar_hallwinter.json
│   ├── nezznar_black_spider.json
│   ├── gundren_rockseeker.json    # TODO
│   ├── iarno_glasstaff.json       # TODO
│   ├── king_grol.json             # TODO
│   └── ...
├── encounters/                    # Combat encounters & tactics
│   └── [TODO]
└── items/                         # Magic items & treasures
    └── [TODO]
```

## 🎯 How It Works

### Problem Solved
- **Full adventure**: ~200,000 tokens
- **Would cost**: $0.60/turn = $24/session
- **This solution**: ~1,000-2,000 tokens/turn = $0.01/turn

**98% cost reduction!**

### Load Only What's Needed

**Always Loaded** (~500-1000 tokens):
- Current chapter overview
- Current location description
- Active quests
- Recent events (last 5)
- Black Spider plot status

**On-Demand** (when requested):
- Specific room details
- NPC personalities & dialogue
- Combat encounter tactics
- Item descriptions

**Never Loaded**:
- Future chapters
- Unvisited locations
- NPCs not yet met

## 🚀 Usage

### Python Integration

```python
from context_loader import LMOPContext

# Initialize
lmop = LMOPContext()

# Get current context (for AI)
context = lmop.get_current_context()
# Returns ~1000 tokens of relevant info

# Player enters location
details = lmop.get_location_details("2_goblin_blind")
# Returns specific area info

# Player talks to NPC
npc_info = lmop.get_npc_info("sildar_hallwinter")
# Returns personality, goals, dialogue examples

# Update state as game progresses
lmop.update_location("cragmaw_hideout")
lmop.add_event("Rescued Sildar from goblins")
lmop.meet_npc("sildar_hallwinter")
lmop.update_quest("escort_supplies", "completed")
lmop.level_up()
```

### In Your DM Agent

```python
class DMAgent:
    def __init__(self):
        self.lmop = LMOPContext()
    
    def process_action(self, action: str, game_state: dict):
        # Get current context
        adventure_context = self.lmop.get_current_context()
        
        # Add to prompt
        game_state["adventure_context"] = adventure_context
        
        # If player investigating
        if "search" in action.lower() or "examine" in action.lower():
            details = self.lmop.get_location_details()
            game_state["location_details"] = details
        
        # If talking to NPC
        if "talk to" in action.lower():
            npc_name = extract_npc_name(action)
            npc_info = self.lmop.get_npc_info(npc_name)
            game_state["npc_info"] = npc_info
        
        # Send to AI...
```

## 📊 Context Size Examples

### Starting the Adventure
```
Input tokens:
- System prompt: 2,000 (cached)
- Current context: 800
- Game state: 300
Total: 3,100 tokens (~$0.01)
```

### Entering Cragmaw Hideout
```
Input tokens:
- System prompt: 2,000 (cached)
- Part 1 overview: 300
- Cragmaw Hideout: 1,200
- Active quests: 100
Total: 3,600 tokens (~$0.01)
```

### Meeting Sildar
```
Additional on-demand:
- Sildar NPC file: 600 tokens
Total: 4,200 tokens (~$0.01)
```

Compare to loading full adventure: **203,000 tokens ($0.61)**

## 🗺️ Adventure Flow

### Part 1: Goblin Arrows (Level 1)
- Goblin ambush on road
- Track to Cragmaw Hideout
- Rescue Sildar
- **Advance to Level 2**

### Part 2: Phandalin (Levels 2-3)
- Arrive in town
- Multiple side quests available
- Confront Redbrands
- Clear Redbrand Hideout
- Defeat Glasstaff (Iarno Albrek)
- **Advance to Level 3**

### Part 3: The Spider's Web (Levels 3-4)
- Non-linear exploration
- Visit: Conyberry, Old Owl Well, Thundertree, Wyvern Tor
- Find Cragmaw Castle
- Rescue Gundren, get map
- **Advance to Level 4**

### Part 4: Wave Echo Cave (Levels 4-5)
- Explore ancient mine
- Fight undead & monsters
- Confront Black Spider (Nezznar)
- Rescue Nundro
- Claim Forge of Spells
- **Advance to Level 5**

## 📝 State Tracking

`adventure.json` tracks:
- Current part & location
- Active quests & status
- NPCs met
- Important events
- Black Spider plot progression
- Rockseeker brothers status
- Faction standings
- Party level

## 🎲 Key Features

### Dynamic Context Loading
- Only loads current chapter + location
- Pulls NPCs when encountered
- Gets room details when examined

### State Management
- Tracks quest progression
- Records important events
- Updates NPC relationships
- Manages faction reputation

### Efficient Storage
- Small JSON files (200-1500 tokens each)
- No duplication
- Easy to update/modify

## ⚡ Performance

**Traditional Approach**:
- Load full 64-page PDF
- 200,000+ tokens per turn
- $24 per 4-hour session
- $1,248 per year

**Modular Approach**:
- Load 1,000-2,000 tokens per turn
- $0.40 per 4-hour session
- $21 per year

**Savings: $1,227/year (98%)**

## 🔧 Extending the System

### Add New Location
```json
{
  "id": "new_dungeon",
  "name": "Secret Cave",
  "description": "...",
  "areas": {
    "entrance": {...},
    "chamber": {...}
  }
}
```

### Add New NPC
```json
{
  "id": "new_character",
  "name": "Bob the Blacksmith",
  "personality": {...},
  "dialogue_examples": [...]
}
```

### Track Custom State
```python
lmop.metadata["custom_flag"] = True
lmop.save_metadata()
```

## 📚 Complete File List

**Completed**:
- ✅ adventure.json
- ✅ context_loader.py
- ✅ All 4 chapter files
- ✅ cragmaw_hideout.json
- ✅ phandalin_town.json
- ✅ sildar_hallwinter.json
- ✅ nezznar_black_spider.json

**TODO** (can be added as needed):
- ⬜ redbrand_hideout.json
- ⬜ cragmaw_castle.json
- ⬜ thundertree.json
- ⬜ wave_echo_cave.json
- ⬜ gundren_rockseeker.json
- ⬜ iarno_glasstaff.json
- ⬜ Other NPCs & locations

## 🎯 Usage Tips

1. **Start simple**: Load just current context
2. **Pull details on-demand**: Room descriptions when examined
3. **Track everything**: Events, NPCs met, quests completed
4. **Update state frequently**: After each major action
5. **Let AI request info**: "What do I know about...?" → load that file

## 🏆 Benefits

- **Cost-effective**: 98% cheaper than loading full adventure
- **Fast**: Small context = quick responses
- **Scalable**: Add content without bloating context
- **Maintainable**: Easy to update individual files
- **Flexible**: Works with any LLM/AI system

---

**Built using Adventure Structure Guide principles**
**Ready for D&D AI DM integration**
