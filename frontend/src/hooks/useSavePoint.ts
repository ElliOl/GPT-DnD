import { useCallback } from 'react'
import { api, type DMResponse } from '../services/api'
import { adventureStorage, type Adventure } from '../services/adventureStorage'
import { sessionStorage } from '../services/sessionStorage'
import { chatArchive } from '../services/chatArchive'
import type { SessionState } from '../services/sessionStorage'
import type { Message } from './useConversation'

interface UseSavePointOptions {
  currentAdventure: Adventure | null
  conversation: Message[]
  voiceEnabled: boolean
  onConversationUpdate: (messages: Message[]) => void
  onAdventureUpdate: (adventure: Adventure | null) => void
}

export function useSavePoint({
  currentAdventure,
  conversation,
  voiceEnabled,
  onConversationUpdate,
  onAdventureUpdate,
}: UseSavePointOptions) {
  const loadSavePoint = useCallback(async (savePointId: string): Promise<DMResponse | null> => {
    if (!currentAdventure) return

    const savePoint = currentAdventure.history?.find(s => s.id === savePointId)
    if (!savePoint) return

    // Archive current chat if there are messages
    if (conversation.length > 0) {
      chatArchive.archiveChat(
        conversation,
        currentAdventure.id,
        currentAdventure.name,
        savePointId,
        savePoint.description
      )
    }

    // Reset backend conversation to start fresh
    try {
      await api.resetSession()
    } catch (err) {
      console.error('Failed to reset backend session:', err)
    }

    // Restore session state if save point has gameState
    if (savePoint.gameState) {
      const sessionData = savePoint.gameState as SessionState
      sessionStorage.saveSession(sessionData)
    }

    // Clear conversation - do NOT restore conversationHistory
    // We want to start fresh from the save point narrative only
    onConversationUpdate([])
    
    // Clear adventure's conversation history so it doesn't get restored later
    // We're starting from this save point, not continuing from previous conversation
    adventureStorage.updateAdventure(currentAdventure.id, {
      conversationHistory: [],
    })
    const updated = adventureStorage.getCurrentAdventure()
    if (updated) {
      onAdventureUpdate(updated)
    }

    // Trigger DM narration of the restored state
    const narrationPrompt = savePoint.narrative 
      ? `Continue from: ${savePoint.narrative}`
      : `Describe the current situation. We are at: ${savePoint.description}`

    try {
      // Get adventure context and session state
      const adventureContext = currentAdventure ? {
        id: currentAdventure.id,
        name: currentAdventure.name,
        description: currentAdventure.description,
        notes: currentAdventure.notes,
      } : undefined

      const sessionState = sessionStorage.loadSession()

      const response: DMResponse = await api.sendAction({
        message: narrationPrompt,
        voice: voiceEnabled,
        adventure_context: adventureContext,
        session_state: sessionState,
      })

      // Add DM response to conversation
      onConversationUpdate([
        {
          role: 'assistant',
          content: response.narrative,
          audio: response.audio_url,
        },
      ])

      // Update adventure state
      if (currentAdventure) {
        adventureStorage.updateAdventureState(
          currentAdventure.id,
          response.narrative,
          response.game_state,
          narrationPrompt
        )
        const updated = adventureStorage.getCurrentAdventure()
        if (updated) {
          onAdventureUpdate(updated)
        }
      }

      return response
    } catch (error) {
      console.error('Failed to get DM narration:', error)
      onConversationUpdate([
        {
          role: 'system',
          content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ])
      throw error
    }
  }, [currentAdventure, conversation, voiceEnabled, onConversationUpdate, onAdventureUpdate])

  return {
    loadSavePoint,
  }
}
