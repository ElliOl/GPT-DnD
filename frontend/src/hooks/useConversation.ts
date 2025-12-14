import { useState, useCallback } from 'react'
import { api, type DMResponse } from '../services/api'
import { adventureStorage, type Adventure } from '../services/adventureStorage'
import { partyStorage } from '../services/partyStorage'
import { sessionStorage } from '../services/sessionStorage'
import { chatArchive } from '../services/chatArchive'

export interface Message {
  role: string
  content: string
  audio?: string
}

interface UseConversationOptions {
  currentAdventure: Adventure | null
  voiceEnabled: boolean
  onAdventureUpdate?: (adventure: Adventure | null) => void
  onCharactersUpdate?: (characters: Record<string, any>) => void
}

export function useConversation({
  currentAdventure,
  voiceEnabled,
  onAdventureUpdate,
  onCharactersUpdate,
}: UseConversationOptions) {
  const [conversation, setConversation] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  const sendMessage = useCallback(async (userMessage: string) => {
    if (!userMessage.trim()) return

    setLoading(true)

    // Add user message to conversation
    setConversation((prev) => [...prev, { role: 'user', content: userMessage }])

    try {
      // Get adventure context
      const adventureContext = currentAdventure ? {
        id: currentAdventure.id,
        name: currentAdventure.name,
        description: currentAdventure.description,
        notes: currentAdventure.notes,
      } : undefined

      // Load session state
      const sessionState = sessionStorage.loadSession()

      const response: DMResponse = await api.sendAction({
        message: userMessage,
        voice: voiceEnabled,
        adventure_context: adventureContext,
        session_state: sessionState,
      })

      // Add DM response to conversation
      setConversation((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.narrative,
          audio: response.audio_url,
        },
      ])

      // Update characters with new game state
      if (response.game_state?.characters) {
        partyStorage.saveParty(response.game_state.characters)
        onCharactersUpdate?.(response.game_state.characters)
      }

      // Save adventure state
      if (currentAdventure) {
        adventureStorage.updateAdventureState(
          currentAdventure.id,
          response.narrative,
          response.game_state,
          userMessage
        )
        const updated = adventureStorage.getCurrentAdventure()
        if (updated) {
          onAdventureUpdate?.(updated)
        }
      }

      return response
    } catch (error) {
      console.error('Failed to send message:', error)
      setConversation((prev) => [
        ...prev,
        {
          role: 'system',
          content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ])
      throw error
    } finally {
      setLoading(false)
    }
  }, [currentAdventure, voiceEnabled, onAdventureUpdate, onCharactersUpdate])

  const archiveChat = useCallback(() => {
    if (conversation.length === 0) return

    // Archive current chat
    chatArchive.archiveChat(
      conversation,
      currentAdventure?.id,
      currentAdventure?.name,
      currentAdventure?.currentSavePoint,
      currentAdventure?.history?.find(s => s.id === currentAdventure.currentSavePoint)?.description
    )

    // Clear current conversation
    setConversation([])

    // Clear adventure's conversation history so it doesn't restore on reload
    if (currentAdventure) {
      adventureStorage.updateAdventure(currentAdventure.id, {
        conversationHistory: [],
      })
      const updated = adventureStorage.getCurrentAdventure()
      if (updated) {
        onAdventureUpdate?.(updated)
      }
    }

    // Reset backend conversation
    api.resetSession().catch(err => {
      console.error('Failed to reset backend session:', err)
    })
  }, [conversation, currentAdventure, onAdventureUpdate])

  const restoreChat = useCallback((messages: Array<{ role: string; content: string }>) => {
    setConversation(messages)
  }, [])

  const clearConversation = useCallback(() => {
    setConversation([])
  }, [])

  return {
    conversation,
    setConversation,
    loading,
    setLoading,
    sendMessage,
    archiveChat,
    restoreChat,
    clearConversation,
  }
}
