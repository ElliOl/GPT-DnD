import type { Character } from './api'

const PARTY_STORAGE_KEY = 'dnd-party-data'

export interface PartyData {
  characters: Record<string, Character>
  lastUpdated: string
}

export const partyStorage = {
  /**
   * Save party data to localStorage
   */
  saveParty(party: Record<string, Character>): void {
    const partyData: PartyData = {
      characters: party,
      lastUpdated: new Date().toISOString(),
    }
    try {
      localStorage.setItem(PARTY_STORAGE_KEY, JSON.stringify(partyData))
    } catch (error) {
      console.error('Failed to save party data:', error)
    }
  },

  /**
   * Load party data from localStorage
   */
  loadParty(): Record<string, Character> | null {
    try {
      const stored = localStorage.getItem(PARTY_STORAGE_KEY)
      if (!stored) return null
      
      const partyData: PartyData = JSON.parse(stored)
      return partyData.characters
    } catch (error) {
      console.error('Failed to load party data:', error)
      return null
    }
  },

  /**
   * Clear party data from localStorage
   */
  clearParty(): void {
    try {
      localStorage.removeItem(PARTY_STORAGE_KEY)
    } catch (error) {
      console.error('Failed to clear party data:', error)
    }
  },

  /**
   * Import party from JSON file
   */
  async importFromFile(file: File): Promise<Record<string, Character>> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const text = e.target?.result as string
          const data = JSON.parse(text)
          
          // Handle both direct character objects and party data format
          let characters: Record<string, Character>
          if (data.characters) {
            characters = data.characters
          } else if (Array.isArray(data)) {
            characters = {}
            data.forEach((char: Character) => {
              characters[char.name] = char
            })
          } else if (typeof data === 'object' && data.name) {
            // Single character
            characters = { [data.name]: data }
          } else {
            throw new Error('Invalid party file format')
          }
          
          resolve(characters)
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsText(file)
    })
  },

  /**
   * Export party to JSON file
   */
  exportToFile(party: Record<string, Character>): void {
    const partyData: PartyData = {
      characters: party,
      lastUpdated: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(partyData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dnd-party-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },
}

