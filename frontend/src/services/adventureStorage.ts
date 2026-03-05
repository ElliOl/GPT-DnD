export interface SavePoint {
  id: string
  timestamp: string
  description: string
  narrative: string // Last DM narrative at this point
  gameState?: any // Snapshot of game state
  dmNotes?: string // DM notes for this save point
  conversationHistory?: Array<{ role: string; content: string; timestamp: string; audio?: string }> // Conversation history up to this point
}

export interface Adventure {
  id: string
  name: string
  description?: string
  // Adventure structure/template info
  structure?: string // Adventure structure/outline for DM
  notes?: string // DM notes about the adventure module
  createdAt: string
  updatedAt: string
  // Legacy fields - keeping for backward compatibility
  // These should now be in Campaign
  currentState?: any
  history?: SavePoint[] // Deprecated - use Campaign questLog instead
  currentSavePoint?: string
  conversationHistory?: Array<{ role: string; content: string; timestamp: string; audio?: string }>
}

const ADVENTURE_STORAGE_KEY = 'dnd-adventures'
const CURRENT_ADVENTURE_KEY = 'dnd-current-adventure-id'

export const adventureStorage = {
  /**
   * Save adventures to localStorage
   */
  saveAdventures(adventures: Adventure[]): void {
    try {
      localStorage.setItem(ADVENTURE_STORAGE_KEY, JSON.stringify(adventures))
    } catch (error) {
      console.error('Failed to save adventures:', error)
    }
  },

  /**
   * Load adventures from localStorage
   */
  loadAdventures(): Adventure[] {
    try {
      const stored = localStorage.getItem(ADVENTURE_STORAGE_KEY)
      if (!stored) return []
      return JSON.parse(stored)
    } catch (error) {
      console.error('Failed to load adventures:', error)
      return []
    }
  },

  /**
   * Add a new adventure
   */
  addAdventure(adventure: Omit<Adventure, 'id' | 'createdAt' | 'updatedAt'>): Adventure {
    const adventures = this.loadAdventures()
    const newAdventure: Adventure = {
      ...adventure,
      id: `adv-${Date.now()}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    adventures.push(newAdventure)
    this.saveAdventures(adventures)
    return newAdventure
  },

  /**
   * Update an adventure
   */
  updateAdventure(id: string, updates: Partial<Adventure>): void {
    const adventures = this.loadAdventures()
    const index = adventures.findIndex(a => a.id === id)
    if (index !== -1) {
      adventures[index] = {
        ...adventures[index],
        ...updates,
        updatedAt: new Date().toISOString(),
      }
      this.saveAdventures(adventures)
    }
  },

  /**
   * Delete an adventure
   */
  deleteAdventure(id: string): void {
    const adventures = this.loadAdventures()
    const filtered = adventures.filter(a => a.id !== id)
    this.saveAdventures(filtered)
  },

  /**
   * Import adventures from JSON file
   */
  async importFromFile(file: File): Promise<Adventure[]> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string
          const data = JSON.parse(text)
          
          let adventures: Adventure[]
          if (Array.isArray(data)) {
            adventures = data
          } else if (data.adventures) {
            adventures = data.adventures
          } else {
            throw new Error('Invalid adventure file format')
          }
          
          // Merge with existing adventures
          const existing = this.loadAdventures()
          const merged = [...existing, ...adventures]
          this.saveAdventures(merged)
          resolve(merged)
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsText(file)
    })
  },

  /**
   * Export adventures to JSON file
   */
  exportToFile(adventures?: Adventure[]): void {
    const data = adventures || this.loadAdventures()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dnd-adventures-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  /**
   * Save a single adventure to file (like party files)
   */
  exportAdventureToFile(adventure: Adventure): void {
    const blob = new Blob([JSON.stringify(adventure, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dnd-adventure-${adventure.name.toLowerCase().replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  /**
   * Import a single adventure from file
   */
  async importAdventureFromFile(file: File): Promise<Adventure> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string
          const adventure: Adventure = JSON.parse(text)
          
          // Validate it's an adventure
          if (!adventure.id || !adventure.name) {
            throw new Error('Invalid adventure file format')
          }
          
          // Merge with existing adventures (update if exists, add if new)
          const adventures = this.loadAdventures()
          const existingIndex = adventures.findIndex(a => a.id === adventure.id)
          
          if (existingIndex >= 0) {
            adventures[existingIndex] = adventure
          } else {
            adventures.push(adventure)
          }
          
          this.saveAdventures(adventures)
          resolve(adventure)
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsText(file)
    })
  },

  /**
   * Set current active adventure
   */
  setCurrentAdventure(adventureId: string | null): void {
    if (adventureId) {
      localStorage.setItem(CURRENT_ADVENTURE_KEY, adventureId)
    } else {
      localStorage.removeItem(CURRENT_ADVENTURE_KEY)
    }
  },

  /**
   * Get current active adventure
   */
  getCurrentAdventure(): Adventure | null {
    const adventureId = localStorage.getItem(CURRENT_ADVENTURE_KEY)
    if (!adventureId) return null
    
    const adventures = this.loadAdventures()
    return adventures.find(a => a.id === adventureId) || null
  },

  /**
   * Add a save point to an adventure
   */
  addSavePoint(
    adventureId: string, 
    description: string, 
    narrative: string, 
    gameState?: any,
    conversationHistory?: Array<{ role: string; content: string; timestamp: string; audio?: string }>
  ): SavePoint {
    const adventures = this.loadAdventures()
    const adventure = adventures.find(a => a.id === adventureId)
    if (!adventure) {
      throw new Error(`Adventure ${adventureId} not found`)
    }

    if (!adventure.history) {
      adventure.history = []
    }

    // If conversation history not provided, use current adventure conversation history
    const historyToStore = conversationHistory || adventure.conversationHistory || []

    const savePoint: SavePoint = {
      id: `save-${Date.now()}`,
      timestamp: new Date().toISOString(),
      description,
      narrative,
      gameState,
      conversationHistory: historyToStore.map(msg => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
        audio: msg.audio,
      })),
    }

    adventure.history.push(savePoint)
    adventure.currentSavePoint = savePoint.id
    adventure.updatedAt = new Date().toISOString()
    
    this.saveAdventures(adventures)
    return savePoint
  },

  /**
   * Update adventure state and conversation
   */
  updateAdventureState(
    adventureId: string,
    narrative: string,
    gameState?: any,
    userMessage?: string,
    audioUrl?: string
  ): void {
    const adventures = this.loadAdventures()
    const adventure = adventures.find(a => a.id === adventureId)
    if (!adventure) return

    // Update current state
    adventure.currentState = gameState
    adventure.updatedAt = new Date().toISOString()

    // Add to conversation history
    if (!adventure.conversationHistory) {
      adventure.conversationHistory = []
    }

    if (userMessage) {
      adventure.conversationHistory.push({
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString(),
      })
    }

    adventure.conversationHistory.push({
      role: 'assistant',
      content: narrative,
      timestamp: new Date().toISOString(),
      audio: audioUrl,
    })

    // Update latest save point narrative if exists
    if (adventure.currentSavePoint && adventure.history) {
      const savePoint = adventure.history.find(s => s.id === adventure.currentSavePoint)
      if (savePoint) {
        savePoint.narrative = narrative
        if (gameState) {
          savePoint.gameState = gameState
        }
      }
    }

    this.saveAdventures(adventures)
  },

  /**
   * Update notes for a save point
   */
  updateSavePointNotes(adventureId: string, savePointId: string, notes: string): void {
    const adventures = this.loadAdventures()
    const adventure = adventures.find(a => a.id === adventureId)
    if (!adventure || !adventure.history) return

    const savePoint = adventure.history.find(sp => sp.id === savePointId)
    if (savePoint) {
      savePoint.dmNotes = notes
      adventure.updatedAt = new Date().toISOString()
      this.saveAdventures(adventures)
    }
  },

  /**
   * Update description for a save point
   */
  updateSavePointDescription(adventureId: string, savePointId: string, description: string): void {
    const adventures = this.loadAdventures()
    const adventure = adventures.find(a => a.id === adventureId)
    if (!adventure || !adventure.history) return

    const savePoint = adventure.history.find(sp => sp.id === savePointId)
    if (savePoint) {
      savePoint.description = description.trim()
      adventure.updatedAt = new Date().toISOString()
      this.saveAdventures(adventures)
    }
  },

  /**
   * Delete a save point
   */
  deleteSavePoint(adventureId: string, savePointId: string): void {
    const adventures = this.loadAdventures()
    const adventure = adventures.find(a => a.id === adventureId)
    if (!adventure || !adventure.history) return

    const index = adventure.history.findIndex(sp => sp.id === savePointId)
    if (index >= 0) {
      adventure.history.splice(index, 1)
      // If this was the current save point, clear it
      if (adventure.currentSavePoint === savePointId) {
        adventure.currentSavePoint = undefined
      }
      adventure.updatedAt = new Date().toISOString()
      this.saveAdventures(adventures)
    }
  },

  /**
   * Get summary of adventure (what's happened so far)
   */
  getAdventureSummary(adventureId: string): string {
    const adventures = this.loadAdventures()
    const adventure = adventures.find(a => a.id === adventureId)
    if (!adventure) return ''

    const parts: string[] = []

    if (adventure.description) {
      parts.push(`**Adventure:** ${adventure.description}`)
    }

    if (adventure.history && adventure.history.length > 0) {
      parts.push(`\n**Save Points:** ${adventure.history.length}`)
      adventure.history.forEach((save, idx) => {
        parts.push(`\n${idx + 1}. ${save.description} (${new Date(save.timestamp).toLocaleString()})`)
      })
    }

    if (adventure.conversationHistory && adventure.conversationHistory.length > 0) {
      parts.push(`\n**Conversation:** ${adventure.conversationHistory.length} messages`)
    }

    return parts.join('\n')
  },
}

