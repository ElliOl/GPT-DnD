# Local AI DM for Mac - Complete Options Guide

## Quick Answer: What Works Best on Mac?

**Recommended: Llama 3.1 8B via Ollama**
- Best balance of speed and quality
- Optimized for Apple Silicon
- Easy setup (5 minutes)

---

## Installation (All Options)

### Option 1: Ollama (EASIEST - Recommended)

```bash
# Install via Homebrew
brew install ollama

# Or download app from https://ollama.com/download/mac
# (Comes with nice menu bar app)

# Start server
ollama serve

# Download your model
ollama pull llama3.1:8b
```

**Pros:**
- ✅ Easiest setup (literally 2 commands)
- ✅ Automatic Metal (GPU) acceleration
- ✅ Model management built-in
- ✅ Free and open source

**Cons:**
- ❌ Less control over advanced settings

---

### Option 2: LM Studio (GUI - User Friendly)

```bash
# Download from https://lmstudio.ai
# Drag to Applications folder
# Open and browse models
```

**Pros:**
- ✅ Beautiful GUI interface
- ✅ Easy model browsing/download
- ✅ Chat interface for testing
- ✅ Can export to code

**Cons:**
- ❌ Larger download (~500MB app)
- ❌ Slightly slower than Ollama

---

### Option 3: llama.cpp (Advanced - Most Control)

```bash
# Clone repo
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build for Mac (Metal acceleration)
make LLAMA_METAL=1

# Download model
# From HuggingFace, search for "GGUF" format

# Run
./main -m models/llama-3.1-8b-instruct.gguf -p "You are a DM..."
```

**Pros:**
- ✅ Maximum performance control
- ✅ Advanced quantization options
- ✅ Lowest memory usage possible

**Cons:**
- ❌ Command-line only
- ❌ Manual model downloads
- ❌ More complex setup

---

## Model Comparison for Mac

### Llama 3.1 8B (Recommended)

**Quality:** ⭐⭐⭐⭐⭐ (Best overall)  
**Speed on M1:** ⭐⭐⭐⭐ (20-40 tok/sec)  
**Memory:** 8GB RAM

```bash
ollama pull llama3.1:8b

# Or lighter version
ollama pull llama3.1:8b-q4_0  # 4-bit quantized, faster
```

**Best for:** General D&D DMing, balanced quality/speed

**Sample Output:**
```
The ancient door groans open on rusted hinges, revealing a vast 
chamber stretching into darkness. Your torchlight catches on 
something glittering in the far corner—gold, perhaps? The air 
is thick with the smell of sulfur and old smoke, and you hear 
a deep, rhythmic breathing echoing from the shadows.

What do you do?
```

---

### Mistral 7B Instruct

**Quality:** ⭐⭐⭐⭐ (Excellent)  
**Speed on M1:** ⭐⭐⭐⭐⭐ (25-50 tok/sec)  
**Memory:** 7GB RAM

```bash
ollama pull mistral:7b-instruct
```

**Best for:** Speed priority, still great quality

**Characteristics:**
- Slightly faster than Llama
- Very good at following instructions
- Less "creative" but more consistent

---

### Phi-3 Mini (3.8B)

**Quality:** ⭐⭐⭐ (Good)  
**Speed on M1:** ⭐⭐⭐⭐⭐ (50-80 tok/sec)  
**Memory:** 4GB RAM

```bash
ollama pull phi3:mini
```

**Best for:** Older Macs, limited RAM, need speed

**Trade-off:** Less atmospheric prose, but very fast

---

### Gemma 2 7B

**Quality:** ⭐⭐⭐⭐ (Very Good)  
**Speed on M1:** ⭐⭐⭐⭐ (20-35 tok/sec)  
**Memory:** 7GB RAM

```bash
ollama pull gemma2:7b
```

**Best for:** Google ecosystem fans, good alternative to Llama

---

### Command-R 7B (Cohere)

**Quality:** ⭐⭐⭐⭐ (Excellent at conversation)  
**Speed on M1:** ⭐⭐⭐⭐ (20-40 tok/sec)  
**Memory:** 7GB RAM

```bash
ollama pull command-r:7b
```

**Best for:** Dialogue-heavy campaigns, NPC conversations

---

## Mac Hardware Recommendations

### M1 MacBook Air (8GB)
- ✅ Works: Llama 8B, Mistral 7B, Phi-3
- ⚠️ Tight: Llama 13B (possible but slow)
- **Recommended:** Mistral 7B or Llama 8B quantized

### M1/M2 MacBook Pro (16GB)
- ✅ Works great: All 7-8B models
- ✅ Works: Llama 13B
- **Recommended:** Llama 3.1 8B full precision

### M1/M2/M3 Max (32GB+)
- ✅ Works: Everything including 13B, 70B models
- ✅ Can run multiple models simultaneously
- **Recommended:** Llama 3.1 8B + specialist models

### Intel Mac
- ⚠️ Works but slow: 7-8B models (5-15 tok/sec)
- **Recommended:** Phi-3 Mini for speed, or use API instead

---

## Performance Benchmarks (Real-World)

**Test:** Generate 100-word DM narration

| Mac Model | Llama 8B | Mistral 7B | Phi-3 Mini |
|-----------|----------|------------|------------|
| M1 8GB | 3-5 sec | 2-4 sec | 1-2 sec |
| M1 Pro 16GB | 2-3 sec | 1.5-2.5 sec | 0.8-1.5 sec |
| M2 | 2-4 sec | 2-3 sec | 1-2 sec |
| M3 Max | 1.5-2 sec | 1-2 sec | 0.5-1 sec |
| Intel i5 | 8-15 sec | 6-12 sec | 4-8 sec |

**For D&D:** 2-4 seconds is perfect! Fast enough to maintain flow.

---

## Setup Examples for Each Option

### Ollama Setup (Recommended)

```bash
# Install
brew install ollama

# Start server (in background)
ollama serve &

# Download model
ollama pull llama3.1:8b

# Test it
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "You are a D&D DM. Describe a goblin ambush.",
  "stream": false
}'
```

**Python Integration:**
```python
from ollama import Client

client = Client()
response = client.generate(
    model='llama3.1:8b',
    prompt='You are a D&D DM. Describe a dark forest.'
)
print(response['response'])
```

---

### LM Studio Setup

1. Download from https://lmstudio.ai
2. Open app
3. Browse models → Search "Llama 3.1 8B"
4. Download (one-click)
5. Go to "Chat" tab to test
6. Go to "Local Server" tab → Start server
7. Use at `http://localhost:1234`

**Python Integration:**
```python
import requests

response = requests.post('http://localhost:1234/v1/chat/completions', json={
    'model': 'llama-3.1-8b',
    'messages': [
        {'role': 'system', 'content': 'You are a D&D DM'},
        {'role': 'user', 'content': 'Describe a goblin ambush'}
    ]
})

print(response.json()['choices'][0]['message']['content'])
```

---

### llama.cpp Setup

```bash
# Install dependencies
brew install cmake

# Clone and build
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_METAL=1  # Metal = GPU acceleration

# Download model (GGUF format)
# Go to https://huggingface.co/
# Search: "llama-3.1-8b-instruct GGUF"
# Download to models/ folder

# Run
./main -m models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
       -n 256 \
       -p "You are a D&D Dungeon Master. Describe a goblin ambush on a forest road."
```

---

## Quantization Options (Speed vs Quality)

Models come in different "quantization" levels:

| Version | Size | Speed | Quality | Recommended For |
|---------|------|-------|---------|-----------------|
| Q8 | ~8GB | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 16GB+ RAM, want max quality |
| Q6 | ~6GB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Good balance |
| Q4 | ~4GB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **Most popular - best balance** |
| Q3 | ~3GB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 8GB RAM Macs |
| Q2 | ~2GB | ⭐⭐⭐⭐⭐ | ⭐⭐ | Emergency only |

**Ollama defaults to Q4** - this is perfect!

To specify:
```bash
ollama pull llama3.1:8b-q4_0  # 4-bit
ollama pull llama3.1:8b-q6_K  # 6-bit (better quality)
```

---

## Which Should You Choose?

### For Beginners:
**Use Ollama + Llama 3.1 8B**
- Easiest setup
- Best documentation
- Active community

### For GUI Lovers:
**Use LM Studio + Llama 3.1 8B**
- Beautiful interface
- Easy model management
- Great for experimentation

### For Maximum Performance:
**Use llama.cpp + Llama 3.1 8B Q4**
- Fastest possible
- Most control
- Requires terminal comfort

### For Limited RAM (8GB Mac):
**Use Ollama + Phi-3 Mini**
- Very fast
- Low memory
- Still decent quality

---

## Mac-Specific Tips

### Enable Metal Acceleration
Ollama does this automatically, but for llama.cpp:
```bash
# When building
make LLAMA_METAL=1

# When running
./main -m model.gguf --gpu-layers 99
```

### Monitor Resource Usage
```bash
# Terminal 1: Run model
ollama serve

# Terminal 2: Watch usage
sudo powermetrics --samplers cpu_power,gpu_power -i 1000

# Or use Activity Monitor app
```

### Optimize for Battery Life
```bash
# Use smaller model when on battery
if on_battery:
    model = "phi3:mini"  # Fast, efficient
else:
    model = "llama3.1:8b"  # Better quality
```

### Keep Mac Cool
Large models generate heat. For long sessions:
- Use cooling pad
- Don't block vents
- Monitor temps: Download "Macs Fan Control"

---

## Troubleshooting Mac Issues

### "Model too slow"
→ Try quantized version: `ollama pull llama3.1:8b-q4_0`

### "Out of memory"
→ Use smaller model: `ollama pull phi3:mini`

### "Ollama won't start"
→ Check port: `lsof -i :11434` and kill if needed

### "Model not using GPU"
→ Ollama auto-enables Metal. For llama.cpp, build with `LLAMA_METAL=1`

### Intel Mac too slow
→ Use Phi-3 Mini or switch to API (OpenAI/Anthropic)

---

## Complete Mac Setup Script

Save as `setup_dm.sh`:

```bash
#!/bin/bash

echo "🎲 Setting up Local D&D AI DM for Mac"

# Install Ollama
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    brew install ollama
fi

# Start Ollama server
echo "Starting Ollama server..."
ollama serve &
sleep 3

# Download model
echo "Downloading Llama 3.1 8B..."
ollama pull llama3.1:8b

# Test it
echo "Testing model..."
ollama run llama3.1:8b "You are a D&D DM. Describe a goblin ambush in one sentence."

echo "✅ Setup complete!"
echo "Run 'ollama serve' to start the server"
echo "Run 'ollama run llama3.1:8b' to test"
```

Run:
```bash
chmod +x setup_dm.sh
./setup_dm.sh
```

---

## My Mac Recommendation

**For M1/M2/M3 Mac with 16GB+ RAM:**
```bash
brew install ollama
ollama serve &
ollama pull llama3.1:8b
```

**For M1 Mac with 8GB RAM:**
```bash
brew install ollama
ollama serve &
ollama pull mistral:7b-instruct-q4_0
```

**For Intel Mac:**
Consider using API instead (OpenAI/Anthropic), or:
```bash
ollama pull phi3:mini  # Fastest on Intel
```

---

## Next Steps

1. Install Ollama: `brew install ollama`
2. Download model: `ollama pull llama3.1:8b`
3. Test it: `ollama run llama3.1:8b "Describe a dungeon"`
4. Build your web app with the model!

Mac is actually **ideal** for local AI models thanks to unified memory and Metal acceleration! 🎲🍎
