# Local AI Integration Plan - Intel Mac

## Overview

Your D&D AI DM project already has Ollama support built in! This plan outlines how to optimize it for your Intel Mac and get it running.

## Current State

✅ **Already Implemented:**
- `OllamaClient` class in `backend/services/ollama_client.py`
- AI factory pattern that supports Ollama
- Environment variable configuration
- Tool calling via prompt engineering

## Changes Made

### 1. Updated Default Model for Intel Mac
- Changed default from `llama2` to `phi3:mini` (fastest on Intel)
- Updated in:
  - `backend/config/ai_providers.py` (PROVIDER_DEFAULTS)
  - `backend/services/ollama_client.py` (default parameter)

### 2. Updated Recommended Models List
Added Intel Mac-optimized models with performance notes:
- `phi3:mini` - Fastest (4-8 sec/100 tokens) ⭐ Recommended
- `llama3.1:8b` - Better quality (8-15 sec/100 tokens)
- `mistral:7b-instruct` - Balanced (6-12 sec/100 tokens)

### 3. Created Setup Script
- `setup_local_ai_intel_mac.sh` - Automated setup for Intel Mac
- Checks Ollama installation
- Starts server
- Downloads recommended model
- Tests the model
- Creates/updates `.env` file

### 4. Added Health Check Endpoint
- `GET /api/health/ollama` - Verifies Ollama server is running
- Lists available models
- Provides helpful error messages

### 5. Updated Documentation
- Updated `README.md` with Intel Mac-specific instructions
- Created `docs/INTEL_MAC_SETUP.md` with detailed guide
- Performance expectations clearly documented

## Next Steps for You

### Step 1: Install Ollama
```bash
brew install ollama
# Or download from https://ollama.com/download/mac
```

### Step 2: Run Setup Script
```bash
./setup_local_ai_intel_mac.sh
```

This will:
- Check Ollama installation
- Start the server
- Download `phi3:mini` (or your choice)
- Test the model
- Configure your `.env` file

### Step 3: Configure Environment
The script creates `.env`, but you still need to add:
```env
AI_PROVIDER=ollama
AI_MODEL=phi3:mini
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-...  # Still needed for TTS
```

### Step 4: Test
```bash
# Start backend
cd backend
source venv/bin/activate
python main.py

# In another terminal, test health
curl http://localhost:8000/api/health/ollama
```

### Step 5: Start Playing
```bash
# Start frontend
cd frontend
npm run dev
```

## Architecture

```
┌─────────────────┐
│  Frontend       │  React + TypeScript
│  (Browser)      │
└────────┬────────┘
         │ HTTP
┌────────▼────────┐
│  FastAPI        │  Python Backend
│  Backend       │
│                 │
│  ┌──────────┐  │
│  │DM Agent  │  │  Uses AI Client
│  └────┬─────┘  │
│       │        │
│  ┌────▼─────┐  │
│  │AI Factory│  │  Creates OllamaClient
│  └────┬─────┘  │
│       │        │
│  ┌────▼─────┐  │
│  │Ollama    │  │  HTTP Client
│  │Client    │  │
│  └────┬─────┘  │
└───────┼────────┘
        │ HTTP
┌───────▼────────┐
│  Ollama Server │  Local (localhost:11434)
│  (phi3:mini)   │  Runs on your Mac
└────────────────┘
```

## Performance Expectations

**Intel Mac (your setup):**
- phi3:mini: 4-8 seconds per 100 tokens
- llama3.1:8b: 8-15 seconds per 100 tokens

**For comparison:**
- M1 Mac: 2-5 seconds per 100 tokens
- Cloud API: 1-3 seconds per 100 tokens

**Is this acceptable?**
- For casual play: Yes (4-8 seconds is fine)
- For fast-paced combat: Maybe (consider cloud API)
- For narrative scenes: Yes (perfectly fine)

## Model Recommendations

### For Speed (Recommended)
```env
AI_MODEL=phi3:mini
```
- Fastest on Intel Mac
- Good enough quality for D&D
- Low memory usage

### For Quality
```env
AI_MODEL=llama3.1:8b
```
- Better narration quality
- More creative descriptions
- Slower (8-15 seconds)

### For Balance
```env
AI_MODEL=mistral:7b-instruct
```
- Good speed/quality balance
- 6-12 seconds per response

## Troubleshooting

### Ollama not found
```bash
# Install via Homebrew
brew install ollama

# Or download app from https://ollama.com/download/mac
```

### Server won't start
```bash
# Check if port is in use
lsof -i :11434

# Kill existing process
kill -9 <PID>

# Start server
ollama serve
```

### Model too slow
- Use `phi3:mini` instead
- Close other applications
- Consider cloud API (Anthropic/OpenAI)

### Out of memory
- Use `phi3:mini` (smallest)
- Close other apps
- Restart Mac

## When to Use Cloud API Instead

**Use local AI (Ollama) when:**
- ✅ You want privacy (no data leaves your machine)
- ✅ You want free gameplay
- ✅ You want offline play
- ✅ 4-8 second responses are acceptable

**Use cloud API (Anthropic/OpenAI) when:**
- ✅ You need <2 second responses
- ✅ You have budget ($5-15 per session)
- ✅ You want best quality narration
- ✅ You're running long campaigns

## Files Modified

1. `backend/config/ai_providers.py` - Updated defaults and recommendations
2. `backend/services/ollama_client.py` - Updated default model
3. `backend/main.py` - Added health check endpoint
4. `README.md` - Added Intel Mac instructions
5. `setup_local_ai_intel_mac.sh` - New setup script
6. `docs/INTEL_MAC_SETUP.md` - New detailed guide

## Testing Checklist

- [ ] Ollama installed and running
- [ ] Model downloaded (`phi3:mini` or `llama3.1:8b`)
- [ ] `.env` configured with `AI_PROVIDER=ollama`
- [ ] Health check endpoint works: `curl http://localhost:8000/api/health/ollama`
- [ ] Backend starts without errors
- [ ] Can send player action and get DM response
- [ ] Response time is acceptable (4-8 seconds)

## Summary

Your project is **ready for local AI**! The infrastructure is already there. You just need to:

1. Install Ollama
2. Run the setup script
3. Configure `.env`
4. Start playing

The setup script handles most of the work automatically. For Intel Mac, `phi3:mini` is the recommended model for the best balance of speed and quality.

Good luck with your D&D campaign! 🎲

