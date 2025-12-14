# Local AI Setup for Intel Mac

## Quick Start

Since you're on an Intel Mac, local AI models will run slower than on Apple Silicon. Here's the best setup:

### Recommended Model: Phi-3 Mini

**Why:** Fastest on Intel Mac (4-8 seconds per 100 tokens)

```bash
# Install Ollama
brew install ollama

# Start server
ollama serve

# Pull the model
ollama pull phi3:mini
```

### Alternative: Llama 3.1 8B

**Why:** Better quality, but slower (8-15 seconds per 100 tokens)

```bash
ollama pull llama3.1:8b
```

## Performance Expectations

| Model | Response Time (100 tokens) | Quality | Best For |
|-------|---------------------------|---------|----------|
| phi3:mini | 4-8 seconds | ⭐⭐⭐ | Fast gameplay |
| llama3.1:8b | 8-15 seconds | ⭐⭐⭐⭐ | Better narration |
| mistral:7b-instruct | 6-12 seconds | ⭐⭐⭐⭐ | Balanced |

**Note:** For D&D, 4-8 seconds is acceptable but not ideal. If you find it too slow, consider:
- Using a cloud API (Anthropic/OpenAI) for better speed
- Or accepting the slower responses for free, private gameplay

## Setup Script

Run the automated setup:

```bash
./setup_local_ai_intel_mac.sh
```

This will:
1. Check if Ollama is installed
2. Start the Ollama server
3. Download the recommended model
4. Test the model
5. Create/update your `.env` file

## Configuration

After setup, your `.env` should have:

```env
AI_PROVIDER=ollama
AI_MODEL=phi3:mini
OLLAMA_BASE_URL=http://localhost:11434
```

## Testing

Test if Ollama is working:

```bash
# Test via command line
ollama run phi3:mini "You are a D&D DM. Describe a goblin ambush."

# Or check health via API
curl http://localhost:8000/api/health/ollama
```

## Troubleshooting

### Ollama server won't start
```bash
# Check if port is in use
lsof -i :11434

# Kill existing process if needed
kill -9 <PID>

# Start again
ollama serve
```

### Model too slow
- Try `phi3:mini` instead of larger models
- Close other applications to free up RAM
- Consider using cloud API instead

### Out of memory
- Use `phi3:mini` (smallest model)
- Close other applications
- Restart your Mac

### Model not found
```bash
# List installed models
ollama list

# Pull model again
ollama pull phi3:mini
```

## Next Steps

1. ✅ Install Ollama
2. ✅ Download model
3. ✅ Configure `.env`
4. ✅ Start backend: `cd backend && python main.py`
5. ✅ Start frontend: `cd frontend && npm run dev`
6. ✅ Play!

## When to Use Cloud API Instead

Consider using Anthropic/OpenAI if:
- Responses are too slow (you want <2 seconds)
- You have budget for API costs
- You want the best quality narration
- You're running a long campaign

Local AI is great for:
- Privacy (no data leaves your machine)
- Free gameplay
- Offline play
- Experimentation

