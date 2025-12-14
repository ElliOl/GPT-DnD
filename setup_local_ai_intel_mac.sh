#!/bin/bash

echo "🎲 Setting up Local AI D&D DM for Intel Mac"
echo "============================================"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Installing Ollama..."
    echo ""
    echo "Please install Ollama:"
    echo "  1. Visit https://ollama.com/download/mac"
    echo "  2. Download and install the app"
    echo "  3. Or use Homebrew: brew install ollama"
    echo ""
    read -p "Press Enter after installing Ollama to continue..."
    
    # Check again
    if ! command -v ollama &> /dev/null; then
        echo "❌ Ollama still not found. Please install it and run this script again."
        exit 1
    fi
fi

echo "✅ Ollama found"
echo ""

# Start Ollama server (if not running)
echo "Starting Ollama server..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama in background..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
    echo "✅ Ollama server started"
else
    echo "✅ Ollama server already running"
fi
echo ""

# Check available models
echo "Checking installed models..."
INSTALLED_MODELS=$(ollama list 2>/dev/null | grep -v "NAME" | awk '{print $1}' || echo "")

# Recommend model for Intel Mac
RECOMMENDED_MODEL="phi3:mini"
echo "Recommended model for Intel Mac: $RECOMMENDED_MODEL"
echo "  - Fastest on Intel (4-8 seconds per 100 tokens)"
echo "  - Good quality for D&D DMing"
echo "  - Low memory usage (~4GB RAM)"
echo ""

# Alternative models
echo "Alternative models (slower but better quality):"
echo "  - llama3.1:8b (8-15 sec/100 tokens, better quality)"
echo "  - mistral:7b-instruct (6-12 sec/100 tokens, good balance)"
echo ""

# Ask user which model to install
read -p "Which model would you like to install? [phi3:mini/llama3.1:8b/mistral:7b-instruct/skip]: " MODEL_CHOICE

if [ -z "$MODEL_CHOICE" ]; then
    MODEL_CHOICE="phi3:mini"
fi

if [ "$MODEL_CHOICE" != "skip" ]; then
    # Check if model is already installed
    if echo "$INSTALLED_MODELS" | grep -q "^${MODEL_CHOICE}$"; then
        echo "✅ Model $MODEL_CHOICE is already installed"
    else
        echo "Downloading $MODEL_CHOICE (this may take a few minutes)..."
        ollama pull "$MODEL_CHOICE"
        
        if [ $? -eq 0 ]; then
            echo "✅ Model $MODEL_CHOICE downloaded successfully"
        else
            echo "❌ Failed to download model. Please check your internet connection."
            exit 1
        fi
    fi
    echo ""
fi

# Test the model
if [ "$MODEL_CHOICE" != "skip" ]; then
    echo "Testing model with a D&D prompt..."
    echo ""
    TEST_RESPONSE=$(ollama run "$MODEL_CHOICE" "You are a D&D DM. Describe a goblin ambush in one sentence." 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "✅ Model test successful!"
        echo "Response: $TEST_RESPONSE"
    else
        echo "⚠️  Model test failed, but model may still work"
    fi
    echo ""
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    
    # Update .env with selected model
    if [ "$MODEL_CHOICE" != "skip" ]; then
        sed -i '' "s/AI_MODEL=.*/AI_MODEL=$MODEL_CHOICE/" .env 2>/dev/null || \
        sed -i "s/AI_MODEL=.*/AI_MODEL=$MODEL_CHOICE/" .env
        echo "✅ .env file created with model: $MODEL_CHOICE"
    else
        echo "✅ .env file created (using default model)"
    fi
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your OPENAI_API_KEY for TTS (text-to-speech)"
    echo "   Even if using local AI for DM, you need OpenAI API key for voice narration"
    echo ""
else
    echo "✅ .env file already exists"
    echo "   Update AI_PROVIDER=ollama and AI_MODEL=$MODEL_CHOICE if needed"
    echo ""
fi

# Summary
echo "============================================"
echo "✅ Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add OPENAI_API_KEY for TTS"
echo "2. Start the backend: cd backend && python main.py"
echo "3. Start the frontend: cd frontend && npm run dev"
echo ""
echo "Performance expectations on Intel Mac:"
if [ "$MODEL_CHOICE" = "phi3:mini" ]; then
    echo "  - Response time: 4-8 seconds per 100 tokens"
    echo "  - Good for: Fast gameplay, quick responses"
elif [ "$MODEL_CHOICE" = "llama3.1:8b" ]; then
    echo "  - Response time: 8-15 seconds per 100 tokens"
    echo "  - Good for: Better quality narration"
elif [ "$MODEL_CHOICE" = "mistral:7b-instruct" ]; then
    echo "  - Response time: 6-12 seconds per 100 tokens"
    echo "  - Good for: Balanced speed and quality"
fi
echo ""
echo "If responses are too slow, consider:"
echo "  - Using a cloud API (Anthropic/OpenAI) instead"
echo "  - Or trying phi3:mini for faster responses"
echo ""

