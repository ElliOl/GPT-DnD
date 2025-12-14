#!/bin/bash

echo "🎲 AI D&D Dungeon Master - Setup Script"
echo "========================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || {
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
}

# Check Node.js version
echo "Checking Node.js version..."
node --version || {
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
}

# Setup backend
echo ""
echo "Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

cd ..

# Setup frontend
echo ""
echo "Setting up frontend..."
cd frontend

echo "Installing npm dependencies..."
npm install

cd ..

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys!"
fi

# Create audio cache directory
mkdir -p audio_cache

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys"
echo "2. Run 'cd backend && source venv/bin/activate && python main.py'"
echo "3. In a new terminal: 'cd frontend && npm run dev'"
echo "4. Open http://localhost:5173"
echo ""
echo "See QUICKSTART.md for detailed instructions."
