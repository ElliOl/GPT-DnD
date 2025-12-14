# Local AI Dungeon Master - Complete Setup Guide

## Overview

Run a D&D campaign with a **local AI model** instead of expensive APIs. Fast, free, and private!

### Why Local?

- ✅ **FREE** - No API costs ($0 vs $15-50/month)
- ✅ **FAST** - 0.5-2 second responses (vs 3-10 seconds)
- ✅ **PRIVATE** - Your campaign stays on your machine
- ✅ **OFFLINE** - Works without internet
- ✅ **CUSTOMIZABLE** - Fine-tune to your DM style

### Architecture

```
┌──────────────────────────────────────────┐
│  Web Frontend                            │
│  - Chat interface                        │
│  - Character sheets                      │
│  - Dice roller UI                        │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│  Backend API (FastAPI/Flask)             │
│  - Game state (characters, quests, HP)   │
│  - Rules engine (dice, combat, skills)   │
│  - Encounter management                  │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│  Local LLM (Llama 3.1 8B)                │
│  - Scene narration                       │
│  - NPC dialogue                          │
│  - Creative descriptions                 │
└──────────────────────────────────────────┘
```

**Division of Labor:**

| Code Handles | LLM Handles |
|-------------|-------------|
| Dice rolling | Scene narration |
| AC/HP/damage calculation | NPC voices |
| Initiative tracking | Creative descriptions |
| State management | Improvisation |
| Rule validation | Atmospheric prose |

---

## Quick Start (15 minutes)

### 1. Install Ollama (Local Model Runner)

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

### 2. Download the Model

```bash
# Recommended: Llama 3.1 8B (best balance)
ollama pull llama3.1:8b

# Alternative: Mistral 7B (faster)
ollama pull mistral:7b-instruct

# Lightweight: Phi-3 Mini (smaller, good quality)
ollama pull phi3:mini
```

### 3. Test It

```bash
ollama run llama3.1:8b "You are a D&D Dungeon Master. Describe a goblin ambush on a forest road."
```

You should get atmospheric narration back!

### 4. Start Ollama Server

```bash
ollama serve
```

Server runs on `http://localhost:11434`

---

## Backend Implementation

### Install Dependencies

```bash
pip install fastapi uvicorn ollama-python
```

### Create `backend/dm_agent.py`

```python
"""
Local AI Dungeon Master Agent
Uses Ollama to run local LLM for narration
"""

from ollama import Client

class DungeonMaster:
    def __init__(self, model="llama3.1:8b"):
        self.client = Client()
        self.model = model
        
        # DM system prompt - teaches the model how to DM
        self.system_prompt = """You are an expert D&D 5e Dungeon Master.

CRITICAL RULES:
- End every scene with ONLY: "What do you do?"
- NEVER suggest actions or list options
- NEVER tell players what their characters think/feel/notice
- NEVER reveal hidden information before discovery
- Describe the WORLD objectively, players interpret it

NARRATION STYLE:
- Use all 5 senses (sight, sound, smell, touch, taste)
- Vivid, atmospheric prose
- Vary sentence length for rhythm
- Show don't tell

EXAMPLES:

BAD: "You enter a room. It has a table."
GOOD: "The door groans open on rusted hinges. Beyond, a circular chamber opens before you, perhaps twenty feet across. A heavy oak table dominates the center, its surface scarred with knife marks and dark stains you hope are wine. The air tastes of mildew and old secrets."

BAD: "The goblin attacks and hits you for 5 damage."
GOOD: "The goblin shrieks and lunges, its rusted scimitar flashing in the torchlight. The blade bites into your shoulder—you feel hot blood running down your arm."

Always end with: "What do you do?"
"""
    
    def narrate(self, context, player_action=None):
        """
        Generate DM narration
        
        Args:
            context: Current scene/situation (str)
            player_action: What the player just did (optional)
        
        Returns:
            Narration text (str)
        """
        
        # Build prompt
        prompt = f"CONTEXT: {context}\n\n"
        
        if player_action:
            prompt += f"PLAYER ACTION: {player_action}\n\n"
        
        prompt += "Narrate the scene with rich sensory detail:"
        
        # Generate response
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            system=self.system_prompt,
            options={
                "temperature": 0.8,    # Creative but not random
                "top_p": 0.9,          # Nucleus sampling
                "top_k": 40,           # Limit vocabulary randomness
                "num_predict": 200,    # Max tokens (keep concise)
            }
        )
        
        return response['response']
    
    def npc_dialogue(self, npc_name, npc_personality, situation):
        """
        Generate NPC dialogue
        
        Args:
            npc_name: NPC's name
            npc_personality: Brief description (e.g., "gruff dwarf, distrusts outsiders")
            situation: What's happening
        
        Returns:
            Dialogue text
        """
        
        prompt = f"""NPC: {npc_name}
PERSONALITY: {npc_personality}
SITUATION: {situation}

Generate 1-2 sentences of dialogue in character. Include speech patterns and mannerisms."""

        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            system="You are a D&D DM creating NPC dialogue. Make NPCs memorable with distinct voices.",
            options={
                "temperature": 0.9,    # More creative for NPCs
                "num_predict": 100,
            }
        )
        
        return response['response']
    
    def describe_combat_action(self, attacker, target, hit, damage=None):
        """
        Narrate a combat action cinematically
        
        Args:
            attacker: Who's attacking
            target: Who's being attacked
            hit: True if attack hit
            damage: Damage amount (if hit)
        
        Returns:
            Combat narration
        """
        
        if hit:
            prompt = f"{attacker} attacks {target} and HITS for {damage} damage. Describe the attack cinematically in 1-2 sentences."
        else:
            prompt = f"{attacker} attacks {target} and MISSES. Describe the failed attack in 1 sentence."
        
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            system="You are a D&D DM narrating combat. Be cinematic and vivid.",
            options={
                "temperature": 0.7,
                "num_predict": 80,
            }
        )
        
        return response['response']


# Example usage
if __name__ == "__main__":
    dm = DungeonMaster()
    
    # Test narration
    context = "The party arrives at a clearing where two dead horses block the trail"
    narration = dm.narrate(context)
    print(narration)
    print()
    
    # Test NPC dialogue
    dialogue = dm.npc_dialogue(
        "Gundren Rockseeker",
        "Enthusiastic dwarf prospector, impatient, uses mining metaphors",
        "The party asks where he's been"
    )
    print(dialogue)
```

### Create `backend/api.py`

```python
"""
FastAPI backend for D&D campaign
Handles game state and calls local LLM for narration
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path

from dm_agent import DungeonMaster
from dice_roller import roll  # Your existing dice roller
from skill_checker import skill_check  # Your existing skill checker

app = FastAPI()

# Initialize DM
dm = DungeonMaster(model="llama3.1:8b")

# Game state
state = {
    "location": "triboar_trail",
    "characters": {},
    "active_encounter": None,
}

# Load characters
def load_characters():
    chars_dir = Path("characters")
    characters = {}
    for char_file in chars_dir.glob("*.json"):
        with open(char_file) as f:
            char = json.load(f)
            characters[char["name"]] = char
    return characters

state["characters"] = load_characters()


# Request models
class NarrateRequest(BaseModel):
    context: str
    player_action: Optional[str] = None

class NPCDialogueRequest(BaseModel):
    npc_name: str
    personality: str
    situation: str

class SkillCheckRequest(BaseModel):
    character: str
    skill: str
    dc: int
    player_roll: int

class CombatActionRequest(BaseModel):
    attacker: str
    target: str
    attack_roll: int
    damage_roll: Optional[int] = None


# Endpoints

@app.get("/")
def root():
    return {"status": "D&D Campaign API - Running Local LLM"}

@app.post("/narrate")
def narrate(req: NarrateRequest):
    """Generate DM narration"""
    narration = dm.narrate(req.context, req.player_action)
    return {"narration": narration}

@app.post("/npc_dialogue")
def npc_dialogue(req: NPCDialogueRequest):
    """Generate NPC dialogue"""
    dialogue = dm.npc_dialogue(req.npc_name, req.personality, req.situation)
    return {"dialogue": dialogue}

@app.post("/skill_check")
def handle_skill_check(req: SkillCheckRequest):
    """Handle a skill check"""
    
    # Get character
    char = state["characters"].get(req.character)
    if not char:
        raise HTTPException(404, "Character not found")
    
    # Determine success
    success = req.player_roll >= req.dc
    
    # Generate narration based on result
    context = f"{req.character} rolled {req.skill} check: {req.player_roll} vs DC {req.dc}"
    
    if success:
        context += " (SUCCESS)"
        narration = dm.narrate(context, f"They succeed at {req.skill}")
    else:
        context += " (FAILURE)"
        narration = dm.narrate(context, f"They fail at {req.skill}")
    
    return {
        "success": success,
        "roll": req.player_roll,
        "dc": req.dc,
        "narration": narration
    }

@app.post("/combat_action")
def combat_action(req: CombatActionRequest):
    """Handle a combat action"""
    
    # Determine if hit (simplified - you'd check AC properly)
    target_char = state["characters"].get(req.target)
    hit = req.attack_roll >= target_char.get("ac", 10) if target_char else False
    
    # Generate narration
    narration = dm.describe_combat_action(
        req.attacker,
        req.target,
        hit,
        req.damage_roll if hit else None
    )
    
    # Update HP if hit
    if hit and req.damage_roll and target_char:
        target_char["hp"] = max(0, target_char["hp"] - req.damage_roll)
        # Save to file
        char_file = Path(f"characters/{req.target.lower().replace(' ', '_')}.json")
        with open(char_file, 'w') as f:
            json.dump(target_char, f, indent=2)
    
    return {
        "hit": hit,
        "damage": req.damage_roll if hit else 0,
        "narration": narration,
        "target_hp": target_char["hp"] if target_char else None
    }

@app.get("/characters/{name}")
def get_character(name: str):
    """Get character data"""
    char = state["characters"].get(name)
    if not char:
        raise HTTPException(404, "Character not found")
    return char

@app.get("/state")
def get_state():
    """Get current game state"""
    return state


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Run the Backend

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start API
cd backend
python api.py
```

API runs on `http://localhost:8000`

---

## Frontend Example (Simple HTML)

Create `frontend/index.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>D&D Campaign</title>
    <style>
        body {
            font-family: 'Georgia', serif;
            max-width: 800px;
            margin: 50px auto;
            background: #2c2416;
            color: #e8dcc0;
            padding: 20px;
        }
        
        #narration {
            background: #1a1410;
            padding: 20px;
            border-left: 4px solid #8b4513;
            margin: 20px 0;
            line-height: 1.8;
            white-space: pre-wrap;
        }
        
        #input-area {
            margin: 20px 0;
        }
        
        input, button {
            padding: 10px;
            font-size: 16px;
        }
        
        button {
            background: #8b4513;
            color: #e8dcc0;
            border: none;
            cursor: pointer;
        }
        
        button:hover {
            background: #a0522d;
        }
    </style>
</head>
<body>
    <h1>🎲 D&D Campaign</h1>
    
    <div id="narration"></div>
    
    <div id="input-area">
        <input type="text" id="action" placeholder="What do you do?" style="width: 70%">
        <button onclick="submitAction()">Act</button>
    </div>
    
    <div id="dice-roller">
        <button onclick="rollDice('1d20')">d20</button>
        <button onclick="rollDice('1d12')">d12</button>
        <button onclick="rollDice('1d10')">d10</button>
        <button onclick="rollDice('1d8')">d8</button>
        <button onclick="rollDice('1d6')">d6</button>
        <button onclick="rollDice('1d4')">d4</button>
        <span id="roll-result"></span>
    </div>
    
    <script>
        const API_URL = 'http://localhost:8000';
        
        async function startAdventure() {
            const context = "The party arrives at a clearing on the Triboar Trail where two dead horses block the path.";
            const response = await fetch(`${API_URL}/narrate`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({context})
            });
            
            const data = await response.json();
            document.getElementById('narration').textContent = data.narration;
        }
        
        async function submitAction() {
            const action = document.getElementById('action').value;
            if (!action) return;
            
            const context = "Current scene continues";
            const response = await fetch(`${API_URL}/narrate`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    context,
                    player_action: action
                })
            });
            
            const data = await response.json();
            document.getElementById('narration').textContent = data.narration;
            document.getElementById('action').value = '';
        }
        
        function rollDice(dice) {
            // Simple client-side roll (or call API)
            const [num, sides] = dice.split('d').map(Number);
            let total = 0;
            for (let i = 0; i < num; i++) {
                total += Math.floor(Math.random() * sides) + 1;
            }
            document.getElementById('roll-result').textContent = `Rolled ${dice}: ${total}`;
        }
        
        // Start adventure on load
        window.onload = startAdventure;
    </script>
</body>
</html>
```

Open in browser: `file:///path/to/index.html`

---

## Performance Specs

### Hardware Requirements

**Minimum (8B model, quantized):**
- RAM: 8GB
- CPU: Modern processor (M1, i5, Ryzen 5+)
- Speed: ~5-10 tokens/sec

**Recommended (8B model, full precision):**
- RAM: 16GB
- GPU: 8GB VRAM (RTX 3060, M1 Max, etc.) *optional but faster*
- Speed: 20-50 tokens/sec

**Ideal (13B model or multiple models):**
- RAM: 32GB+
- GPU: 16GB+ VRAM
- Speed: 30-80 tokens/sec

### Expected Response Times

| Model | Hardware | Time for 100 tokens |
|-------|----------|---------------------|
| Llama 3.1 8B | CPU only | 10-20 seconds |
| Llama 3.1 8B | M1 Mac | 2-5 seconds |
| Llama 3.1 8B | RTX 3060 | 1-3 seconds |
| Llama 3.1 8B | RTX 4090 | 0.5-1 second |

**For D&D:** Aim for 2-5 second responses. Totally acceptable!

---

## Model Comparison

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| **Llama 3.1 8B** | 8B params | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **Recommended - Best balance** |
| Mistral 7B | 7B params | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Speed priority |
| Phi-3 Mini | 3.8B params | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Limited hardware |
| Gemma 7B | 7B params | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Google ecosystem |

---

## Fine-Tuning (Optional - Advanced)

To make the model even better at DMing:

### 1. Gather Training Data

Collect examples of good DM narration:
- Lost Mines of Phandelver text
- Other D&D adventures
- Critical Role transcripts
- Your own DM notes

Format as:
```json
{
  "instruction": "Describe a goblin ambush on a forest road",
  "output": "The forest goes eerily silent. Then—TWANG! Black-fletched arrows whistle from the underbrush..."
}
```

### 2. Fine-Tune with Axolotl or Unsloth

```bash
# Install unsloth (faster fine-tuning)
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# Fine-tune (simplified)
from unsloth import FastLanguageModel

model = FastLanguageModel.from_pretrained("meta-llama/Llama-3.1-8B-Instruct")
model = FastLanguageModel.get_peft_model(model)  # LoRA adapters

# Train on your D&D dataset
trainer.train()

# Save
model.save_pretrained("llama-3.1-8b-dnd-dm")
```

### 3. Use Your Custom Model

```python
dm = DungeonMaster(model="llama-3.1-8b-dnd-dm")
```

---

## Cost Comparison

### OpenAI GPT-4
- **Cost:** $0.03 per 1K tokens
- **Typical session:** ~5K tokens = $0.15
- **Monthly (8 sessions):** ~$1.20
- **Yearly:** ~$15

### Anthropic Claude
- **Cost:** Similar to GPT-4
- **Yearly:** ~$15-20

### Local Llama 8B
- **Cost:** $0 (after hardware)
- **Initial investment:** $0 (if you have a laptop)
- **Electricity:** ~$0.01 per session
- **Yearly:** ~$0.10

**Savings:** ~$15-20/year + unlimited usage

---

## Troubleshooting

### Model downloads slowly
→ Ollama downloads from HuggingFace. Be patient or use faster mirrors.

### Out of memory errors
→ Use quantized models: `ollama pull llama3.1:8b-q4_0`

### Slow responses
→ Use GPU if available, or try smaller model (phi3:mini)

### Poor quality narration
→ Adjust temperature (try 0.7-0.9), or fine-tune on D&D data

### Ollama server won't start
→ Check port 11434 isn't in use: `lsof -i :11434`

---

## Next Steps

1. **Install Ollama** and download Llama 3.1 8B
2. **Test the model** with simple D&D prompts
3. **Build the backend API** with FastAPI
4. **Create a simple frontend** (HTML or React)
5. **Test a full encounter** (goblin ambush)
6. **(Optional) Fine-tune** on D&D-specific data

---

## Resources

- **Ollama:** https://ollama.com
- **Model Library:** https://ollama.com/library
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Llama 3.1:** https://huggingface.co/meta-llama
- **Fine-tuning Guide:** https://github.com/unslothai/unsloth

---

## Summary

**Best Setup for Most People:**
- Model: Llama 3.1 8B via Ollama
- Backend: FastAPI with dm_agent.py
- Frontend: Simple HTML/JS or React
- Hardware: Laptop with 16GB RAM

**Result:**
- Fast responses (1-3 seconds)
- Free forever
- Good narration quality (7-8/10)
- Fully customizable

Start with stock Llama 8B, fine-tune later if needed. You'll have a working AI DM in under an hour! 🎲
