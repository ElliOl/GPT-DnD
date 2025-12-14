/**
 * Session State Storage Service
 * 
 * Handles loading and saving session states in the format of current_session.json
 * This includes campaign info, quest logs, world state, party inventory, etc.
 */

export interface QuestLogEntry {
  name: string
  status: 'not_started' | 'in_progress' | 'completed' | 'failed'
  description: string
  notes?: string
}

export interface SessionState {
  campaign: string
  session_number: number
  date_started: string
  current_location?: string
  active_encounter?: string
  party: string[] // Character names
  quest_log: QuestLogEntry[]
  world_state: Record<string, any>
  party_inventory: {
    shared_items: string[]
    gold_pool?: number
  }
  notes: string[]
}

const SESSION_STORAGE_KEY = 'dnd-current-session'

export const sessionStorage = {
  /**
   * Load session state from localStorage
   */
  loadSession(): SessionState | null {
    try {
      const stored = localStorage.getItem(SESSION_STORAGE_KEY)
      if (!stored) return null
      return JSON.parse(stored)
    } catch (error) {
      console.error('Failed to load session state:', error)
      return null
    }
  },

  /**
   * Save session state to localStorage
   */
  saveSession(session: SessionState): void {
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
    } catch (error) {
      console.error('Failed to save session state:', error)
    }
  },

  /**
   * Load session state from JSON file
   */
  async loadFromFile(file: File): Promise<SessionState> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string
          const session: SessionState = JSON.parse(text)
          
          // Validate required fields
          if (!session.campaign || !session.party) {
            throw new Error('Invalid session file format: missing required fields')
          }
          
          // Ensure all fields exist with defaults
          const validatedSession: SessionState = {
            campaign: session.campaign,
            session_number: session.session_number || 1,
            date_started: session.date_started || new Date().toISOString().split('T')[0],
            current_location: session.current_location,
            active_encounter: session.active_encounter,
            party: session.party || [],
            quest_log: session.quest_log || [],
            world_state: session.world_state || {},
            party_inventory: session.party_inventory || { shared_items: [] },
            notes: session.notes || [],
          }
          
          resolve(validatedSession)
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsText(file)
    })
  },

  /**
   * Export session state to JSON file
   */
  exportToFile(session?: SessionState): void {
    const data = session || this.loadSession()
    if (!data) {
      throw new Error('No session state to export')
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session-${data.campaign.toLowerCase().replace(/\s+/g, '-')}-session${data.session_number}-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  /**
   * Clear session state
   */
  clearSession(): void {
    localStorage.removeItem(SESSION_STORAGE_KEY)
  },

  /**
   * Update session state (merge with existing)
   */
  updateSession(updates: Partial<SessionState>): SessionState | null {
    const existing = this.loadSession()
    if (!existing) {
      // Create new session if none exists
      const newSession: SessionState = {
        campaign: updates.campaign || 'Unknown Campaign',
        session_number: updates.session_number || 1,
        date_started: updates.date_started || new Date().toISOString().split('T')[0],
        party: updates.party || [],
        quest_log: updates.quest_log || [],
        world_state: updates.world_state || {},
        party_inventory: updates.party_inventory || { shared_items: [] },
        notes: updates.notes || [],
        ...updates,
      }
      this.saveSession(newSession)
      return newSession
    }
    
    const updated: SessionState = {
      ...existing,
      ...updates,
      // Merge nested objects
      world_state: { ...existing.world_state, ...(updates.world_state || {}) },
      party_inventory: {
        ...existing.party_inventory,
        ...(updates.party_inventory || {}),
        shared_items: updates.party_inventory?.shared_items || existing.party_inventory.shared_items,
      },
    }
    
    this.saveSession(updated)
    return updated
  },
}
