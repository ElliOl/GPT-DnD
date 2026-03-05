# Loading Adventures from the Frontend

## Quick Answer

**No restart needed!** The backend already has all adventure files in `backend/adventures/`. The frontend just needs to call the API to activate one.

## How It Works

### Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   Frontend      │         │    Backend       │
│                 │         │                  │
│  React App      │────────▶│  FastAPI Server  │
│  (Browser)      │  API    │  (Port 8000)     │
│                 │  Call   │                  │
└─────────────────┘         └──────────────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │  backend/        │
                            │  adventures/     │
                            │  ├── lost_mines_ │
                            │  │   of_phandelver│
                            │  │   ├── adventure.json
                            │  │   ├── chapters/
                            │  │   ├── locations/
                            │  │   └── npcs/
                            └──────────────────┘
```

**Key Point:** The adventure files are **already on the backend server**. The frontend doesn't upload files - it just tells the backend "activate this adventure".

## How to Load an Adventure

### Option 1: Using the UI (Easiest)

1. **Open your app** in the browser
2. **Go to the Adventure tab**
3. **Look for "Modular Adventures (Backend)" section**
4. **Click "Load"** next to "Lost Mine of Phandelver"
5. **Done!** The adventure is now active

### Option 2: Using the Hook in Code

```typescript
import { useModularAdventure } from '../hooks/useModularAdventure'

function MyComponent() {
  const { 
    availableAdventures, 
    loadAdventure, 
    currentAdventure,
    loadingAdventures 
  } = useModularAdventure()

  // Load adventure on mount
  useEffect(() => {
    if (availableAdventures.length > 0) {
      loadAdventure('lost_mines_of_phandelver')
    }
  }, [availableAdventures])

  return (
    <div>
      {currentAdventure?.loaded ? (
        <p>✅ {currentAdventure.adventure_info.name} is active!</p>
      ) : (
        <button onClick={() => loadAdventure('lost_mines_of_phandelver')}>
          Load Lost Mines
        </button>
      )}
    </div>
  )
}
```

### Option 3: Direct API Call

```typescript
import { api } from '../services/api'

// Load adventure
await api.loadAdventure('lost_mines_of_phandelver')

// Check if loaded
const current = await api.getCurrentAdventure()
if (current.loaded) {
  console.log('Adventure active:', current.adventure_info.name)
}
```

## What Happens When You Load

1. **Frontend** calls `POST /api/adventures/load` with `{ "adventure_id": "lost_mines_of_phandelver" }`
2. **Backend** reads `backend/adventures/lost_mines_of_phandelver/adventure.json`
3. **Backend** initializes `AdventureContext` with that adventure
4. **Backend** returns success
5. **Frontend** shows "✓ Loaded" status

**No files are uploaded. No restart needed. It's instant!**

## Available Adventures

The backend automatically discovers adventures in `backend/adventures/`:

```bash
backend/adventures/
├── lost_mines_of_phandelver/  ← Automatically detected
│   ├── adventure.json
│   ├── chapters/
│   ├── locations/
│   └── npcs/
└── [future adventures...]     ← Just add folders here
```

To see available adventures:
```typescript
const { availableAdventures } = useModularAdventure()
console.log(availableAdventures)
// [
//   {
//     id: "lost_mines_of_phandelver",
//     name: "Lost Mine of Phandelver",
//     level_range: [1, 5],
//     estimated_sessions: 12
//   }
// ]
```

## Integration with Existing System

The modular adventure system **works alongside** your existing campaign system:

```typescript
// Load modular adventure (backend)
await loadModularAdventure('lost_mines_of_phandelver')

// Create campaign (localStorage)
const campaign = campaignStorage.createCampaign(
  'lost_mines_of_phandelver',
  'My Campaign'
)

// Both systems work together:
// - Modular adventure: Provides context to AI (chapters, locations, NPCs)
// - Campaign: Tracks your progress (quest log, world state, notes)
```

## Troubleshooting

### "No adventures found"

**Check:** Is the backend running?
```bash
cd backend
uvicorn main:app --reload
```

**Check:** Do adventure files exist?
```bash
ls backend/adventures/
# Should show: lost_mines_of_phandelver/
```

### "Failed to load adventure"

**Check:** Backend logs for errors
```bash
# Look for error messages in terminal running uvicorn
```

**Check:** Adventure folder name matches exactly
```bash
# Must be: lost_mines_of_phandelver
# Not: lost_mine_phandelver or Lost_Mines_Of_Phandelver
```

### Adventure loads but doesn't work

**Check:** Is adventure actually loaded?
```typescript
const current = await api.getCurrentAdventure()
console.log(current)
// Should show: { loaded: true, adventure_info: {...} }
```

**Check:** Are you sending actions to the backend?
```typescript
// Make sure your chat sends to /api/action
// The backend automatically uses loaded adventure context
```

## FAQ

### Q: Do I need to restart the backend?

**A: No!** The backend already has the files. Loading just activates one.

### Q: Can I load multiple adventures?

**A: No, only one adventure is active at a time.** Loading a new one replaces the current.

### Q: Do I need to upload files from frontend?

**A: No!** Files are already on the backend server in `backend/adventures/`.

### Q: How do I add a new adventure?

**A:** 
1. Create folder: `backend/adventures/my_adventure/`
2. Add `adventure.json` and content files
3. Restart backend (to discover new folder)
4. It will appear in the list automatically

### Q: What's the difference between "Modular Adventures" and "Legacy Adventures"?

**A:**
- **Modular Adventures:** Backend-based, optimized for AI, tracks state automatically
- **Legacy Adventures:** Frontend localStorage, simpler structure, manual tracking

You can use both! Modular adventures provide AI context, legacy adventures track your campaign progress.

## Example: Complete Flow

```typescript
// 1. Component loads
function GameComponent() {
  const { 
    availableAdventures, 
    loadAdventure, 
    currentAdventure 
  } = useModularAdventure()

  // 2. Auto-load on mount
  useEffect(() => {
    if (availableAdventures.length > 0 && !currentAdventure?.loaded) {
      loadAdventure('lost_mines_of_phandelver')
    }
  }, [availableAdventures, currentAdventure])

  // 3. Show status
  return (
    <div>
      {currentAdventure?.loaded ? (
        <p>✅ Playing: {currentAdventure.adventure_info.name}</p>
      ) : (
        <p>Loading adventure...</p>
      )}
    </div>
  )
}

// 4. When player sends message
// Backend automatically uses loaded adventure context
// No additional code needed!
```

## Summary

✅ **No restart needed** - Backend has files already  
✅ **Just call API** - `loadAdventure('lost_mines_of_phandelver')`  
✅ **Works automatically** - AI gets context on every turn  
✅ **UI included** - Adventure tab shows load button  

**It's that simple!** 🎲

