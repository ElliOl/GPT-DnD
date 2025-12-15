/**
 * API Service for communicating with the backend
 */

const API_BASE = '/api'

export interface PlayerAction {
  message: string
  character?: string
  voice: boolean
  adventure_context?: any
  session_state?: any
}

export interface DMResponse {
  narrative: string
  audio_url?: string
  game_state: any
  tool_results: any[]
  cost?: {
    input_tokens: number
    output_tokens: number
  }
}

export interface Character {
  name: string
  race: string
  char_class: string
  class?: string
  level: number
  max_hp: number
  current_hp: number
  hp?: number
  temp_hp?: number
  armor_class: number
  ac?: number
  speed?: number
  background?: string
  abilities: {
    STR: number
    DEX: number
    CON: number
    INT: number
    WIS: number
    CHA: number
    [key: string]: number // Allow lowercase variants
  }
  proficiency_bonus: number
  skills: Record<string, boolean>
  proficiencies?: string[]
  save_proficiencies?: string[]
  weapons?: Array<{
    name: string
    attack_bonus: number
    damage_dice: string
    damage_bonus: number
    damage_type: string
    ranged?: boolean
    thrown?: boolean
    range?: string
  }>
  armor?: {
    name: string
    ac_base: number
    type: string
  }
  shield?: {
    name: string
    ac_bonus: number
  }
  spellcasting?: {
    ability: string
    spell_save_dc: number
    spell_attack_bonus: number
    spell_slots?: Record<string, number>
    spells_prepared?: string[]
    cantrips?: string[]
  }
  inventory: string[]
  gold?: number
  features?: string[]
  personality?: {
    trait?: string
    ideal?: string
    bond?: string
    flaw?: string
  }
  notes?: string
  conditions: string[]
  active_spells?: Array<string | { name: string; duration?: string }>
  spell_slots_used?: Record<string, number>
  spell_details?: Record<string, {
    level: string
    school: string
    casting_time: string
    range: string
    components: string
    duration: string
    description: string
  }>
}

export const api = {
  /**
   * Send player action to DM
   */
  async sendAction(action: PlayerAction): Promise<DMResponse> {
    // Create AbortController for timeout (120 seconds for Intel Mac)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 120000) // 120 seconds

    try {
      const response = await fetch(`${API_BASE}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`API error: ${response.statusText} - ${errorText}`)
      }

      return response.json()
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request timed out after 120 seconds. The AI model may be taking longer than expected on Intel Mac.')
      }
      throw error
    }
  },

  /**
   * Get current game state
   */
  async getGameState(): Promise<any> {
    const response = await fetch(`${API_BASE}/game-state`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Get all characters
   */
  async getCharacters(): Promise<{ characters: Record<string, Character> }> {
    const response = await fetch(`${API_BASE}/characters`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Get specific character
   */
  async getCharacter(name: string): Promise<Character> {
    const response = await fetch(`${API_BASE}/characters/${encodeURIComponent(name)}`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Reset DM conversation
   */
  async resetSession(): Promise<void> {
    const response = await fetch(`${API_BASE}/reset`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
  },

  /**
   * Get additional rules file content (adds to core D&D rules)
   */
  async getAdditionalRules(): Promise<{ content: string; file: string }> {
    const response = await fetch(`${API_BASE}/additional-rules`)
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API error: ${response.status} ${response.statusText} - ${errorText}`)
    }
    return response.json()
  },

  /**
   * Save additional rules file content (adds to core D&D rules)
   */
  async saveAdditionalRules(content: string): Promise<{ message: string; length: number }> {
    const response = await fetch(`${API_BASE}/additional-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API error: ${response.statusText} - ${errorText}`)
    }
    return response.json()
  },

  /**
   * Get available AI providers and models
   */
  async getProviders(): Promise<any> {
    const response = await fetch(`${API_BASE}/config/providers`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Get available adventure modules
   */
  async getAvailableAdventures(): Promise<any> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout

    try {
      const response = await fetch(`${API_BASE}/adventures/available`, {
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`)
      }
      return response.json()
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request timed out. Is the backend server running?')
      }
      throw error
    }
  },

  /**
   * Load an adventure module
   */
  async loadAdventure(adventureId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ adventure_id: adventureId }),
    })
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API error: ${response.statusText} - ${errorText}`)
    }
    return response.json()
  },

  /**
   * Get currently loaded adventure
   */
  async getCurrentAdventure(): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/current`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Update adventure state
   */
  async updateAdventureState(updates: any): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API error: ${response.statusText} - ${errorText}`)
    }
    return response.json()
  },

  /**
   * Get adventure context at specified detail level
   */
  async getAdventureContext(contextType: 'minimal' | 'standard' | 'detailed'): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/context/${contextType}`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Get location details
   */
  async getLocationDetails(locationId: string, areaId?: string): Promise<any> {
    const url = areaId
      ? `${API_BASE}/adventures/location/${locationId}?area_id=${areaId}`
      : `${API_BASE}/adventures/location/${locationId}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * Get NPC information
   */
  async getNPCInfo(npcId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/npc/${npcId}`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * List available chapters
   */
  async listChapters(): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/chapters`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * List available locations
   */
  async listLocations(): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/locations`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },

  /**
   * List available NPCs
   */
  async listNPCs(): Promise<any> {
    const response = await fetch(`${API_BASE}/adventures/npcs`)
    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`)
    }
    return response.json()
  },
}

/**
 * WebSocket connection for real-time game state updates
 */
export function connectWebSocket(
  onMessage: (data: any) => void,
  onError?: (error: Event) => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/game`)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onMessage(data)
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    onError?.(error)
  }

  return ws
}
