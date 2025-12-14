import { useState, useEffect } from 'react'
import { adventureStorage, type Adventure } from '../services/adventureStorage'
import type { Message } from './useConversation'

export function useAdventure() {
  const [currentAdventure, setCurrentAdventure] = useState<Adventure | null>(null)

  useEffect(() => {
    // Load current adventure
    const adventure = adventureStorage.getCurrentAdventure()
    if (adventure) {
      setCurrentAdventure(adventure)
    } else {
      // If no current adventure, try to load default from file
      const allAdventures = adventureStorage.loadAdventures()
      if (allAdventures.length > 0) {
        const firstAdventure = allAdventures[0]
        adventureStorage.setCurrentAdventure(firstAdventure.id)
        setCurrentAdventure(firstAdventure)
      }
    }
  }, [])

  const restoreConversationHistory = (): Message[] => {
    if (!currentAdventure?.conversationHistory || currentAdventure.conversationHistory.length === 0) {
      return []
    }
    return currentAdventure.conversationHistory.map(msg => ({
      role: msg.role,
      content: msg.content,
    }))
  }

  return {
    currentAdventure,
    setCurrentAdventure,
    restoreConversationHistory,
  }
}
