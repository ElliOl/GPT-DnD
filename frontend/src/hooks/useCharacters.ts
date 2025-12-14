import { useState, useEffect } from 'react'
import { api, type Character } from '../services/api'
import { partyStorage } from '../services/partyStorage'

export function useCharacters() {
  const [characters, setCharacters] = useState<Record<string, Character>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // First try to load from localStorage
    const savedParty = partyStorage.loadParty()
    if (savedParty && Object.keys(savedParty).length > 0) {
      setCharacters(savedParty)
      setLoading(false)
    } else {
      // Try to load default party file
      fetch('/data/party_elara_thorin.json')
        .then(res => res.json())
        .then(data => {
          if (data.characters) {
            partyStorage.saveParty(data.characters)
            setCharacters(data.characters)
          } else {
            // Fallback to API
            api.getCharacters()
              .then((data) => setCharacters(data.characters))
              .catch((err) => console.error('Failed to load characters:', err))
          }
        })
        .catch(() => {
          // Fallback to API if file not found
          api.getCharacters()
            .then((data) => setCharacters(data.characters))
            .catch((err) => console.error('Failed to load characters:', err))
        })
        .finally(() => setLoading(false))
    }
  }, [])

  return {
    characters,
    setCharacters,
    loading,
  }
}
