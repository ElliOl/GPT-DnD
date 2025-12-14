# Project TODO

## ✅ Completed

- [x] Project structure created
- [x] Backend with FastAPI set up
- [x] Multi-provider AI support (Anthropic, OpenAI, Ollama, LM Studio, OpenRouter)
- [x] DM Agent with tool calling
- [x] TTS service with caching
- [x] Frontend with React + Vite + TypeScript
- [x] shadcn/ui setup
- [x] Basic API integration
- [x] Configuration files (.env, etc.)
- [x] Documentation (README, QUICKSTART)
- [x] Sample character data
- [x] **Game engine ported from old project**
  - [x] Full combat system (combat.py) with attack rolls, damage, initiative
  - [x] Skill check system (skills.py) with proficiency and ability modifiers
  - [x] Dice roller (roller.py) with advantage/disadvantage support
  - [x] Character data migrated (Thorin Ironforge, Elara Moonwhisper, Gundren Rockseeker)
  - [x] All mechanics tested and verified working
- [x] **Both servers running**
  - [x] Backend server on http://localhost:8000
  - [x] Frontend dev server on http://localhost:5173

## 🔨 In Progress / To Do

### Critical (Must Have)

- [x] **Port game engine from old project**
  - [x] Copy `game_engine/combat.py` → implement full combat system
  - [x] Copy `game_engine/skills.py` → implement skill system with proper modifiers
  - [x] Copy `dice/roller.py` → implement advantage/disadvantage properly
  - [x] Update `game_engine/engine.py` to use ported code
  - [x] Test all game mechanics

- [ ] **Test the complete flow**
  - [x] Start backend server (running on http://localhost:8000)
  - [x] Start frontend (running on http://localhost:5173)
  - [ ] Send a message
  - [ ] Verify AI responds
  - [ ] Verify TTS works
  - [ ] Verify character sheet updates

- [ ] **Fix any bugs found during testing**

### High Priority (Should Have)

- [ ] **Web Speech API integration**
  - [ ] Add microphone button to frontend
  - [ ] Implement speech-to-text
  - [ ] Add recording indicator
  - [ ] Handle speech recognition errors

- [ ] **Better UI components**
  - [ ] Combat tracker component (initiative order, turn indicator)
  - [ ] Dice roller with animations
  - [ ] Inventory panel
  - [ ] Quest log display
  - [ ] Settings panel (AI provider selection, voice toggle)

- [ ] **Improve game engine**
  - [ ] Add spell casting system
  - [ ] Add conditions/status effects
  - [ ] Add concentration tracking
  - [ ] Implement death saves
  - [ ] Add short/long rest mechanics

- [ ] **Database persistence**
  - [ ] Replace JSON files with SQLite or PostgreSQL
  - [ ] Save conversation history
  - [ ] Save game states
  - [ ] Support multiple campaigns

### Medium Priority (Nice to Have)

- [ ] **Character creation UI**
  - [ ] Race selection
  - [ ] Class selection
  - [ ] Ability score rolling/point buy
  - [ ] Equipment selection

- [ ] **Campaign management**
  - [ ] Create new campaign
  - [ ] Load existing campaign
  - [ ] Save campaign state
  - [ ] Session notes

- [ ] **Encounter builder**
  - [ ] Add enemies
  - [ ] Set up environment
  - [ ] Define loot tables
  - [ ] Trigger conditions

- [ ] **Advanced TTS features**
  - [ ] NPC-specific voices
  - [ ] Emotion detection for voice modulation
  - [ ] Background music/ambience
  - [ ] Sound effects (dice rolls, combat hits)

- [ ] **Multiplayer support**
  - [ ] Multiple players connect via WebSocket
  - [ ] Player-specific views
  - [ ] Turn-based input
  - [ ] Chat between players

### Low Priority (Future Enhancements)

- [ ] **AI image generation**
  - [ ] Generate scene images
  - [ ] Generate NPC portraits
  - [ ] Generate maps

- [ ] **Map/grid system**
  - [ ] Visual battle map
  - [ ] Token placement
  - [ ] Movement tracking
  - [ ] Fog of war

- [ ] **Mobile app**
  - [ ] React Native version
  - [ ] Offline mode
  - [ ] Push notifications

- [ ] **Integration with D&D Beyond**
  - [ ] Import character sheets
  - [ ] Sync character updates
  - [ ] Access official content

## How to Port Game Engine

The existing game engine in `dnd-campaign test/` has robust implementations:

```bash
# From project root
cd /Users/elliotortiz/Code_Projects/Code_Projects/Dnd/dnd-ai-dm

# Copy game engine files
cp ../dnd-campaign\ test/game_engine/combat.py game_engine/
cp ../dnd-campaign\ test/game_engine/skills.py game_engine/
cp ../dnd-campaign\ test/dice/roller.py game_engine/

# Copy character data
cp ../dnd-campaign\ test/characters/*.json data/characters/
cp ../dnd-campaign\ test/npcs/*.json data/npcs/

# Update imports in engine.py to use ported modules
```

Then update `game_engine/engine.py` to import and use the ported functions:

```python
from .combat import CombatEngine, attack_roll, apply_damage
from .skills import skill_check, ability_save
from .roller import roll, roll_with_advantage
```

## Testing Checklist

Before considering this project "done":

- [ ] Backend starts without errors
- [ ] Frontend loads successfully
- [ ] Can send a message and get AI response
- [ ] TTS audio plays in browser
- [ ] Character HP updates when damage dealt
- [ ] Skill checks work correctly
- [ ] Attack rolls hit/miss appropriately
- [ ] Initiative tracking works
- [ ] Game state persists between messages
- [ ] Can switch AI providers
- [ ] Works with local Ollama
- [ ] Works with Claude
- [ ] Works with GPT-4

## Known Issues

(Add issues as you find them during testing)

- [ ] Issue 1:
- [ ] Issue 2:

## Future Ideas

- Integration with VTT platforms (Roll20, Foundry)
- AI-generated quest hooks
- Dynamic difficulty adjustment
- Achievement system
- Character progression tracking
- Session summaries via AI
