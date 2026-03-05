import { useState, useCallback, useEffect } from 'react'
import { api, type DMResponse } from '../services/api'
import { adventureStorage, type Adventure } from '../services/adventureStorage'
import { partyStorage } from '../services/partyStorage'
import { sessionStorage } from '../services/sessionStorage'
import { campaignStorage, type QuestLogEntry } from '../services/campaignStorage'
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
  characters?: Record<string, any> // Pass characters directly as fallback
}

export function useConversation({
  currentAdventure,
  voiceEnabled,
  onAdventureUpdate,
  onCharactersUpdate,
  characters: charactersFromProps,
}: UseConversationOptions) {
  const [conversation, setConversation] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  // Debug: Log when conversation changes
  useEffect(() => {
    console.log('Conversation updated:', conversation.length, 'messages')
    if (conversation.length > 0) {
      console.log('Latest message:', conversation[conversation.length - 1])
    }
  }, [conversation])

  const sendMessage = useCallback(async (userMessage: string) => {
    if (!userMessage.trim()) {
      console.warn('Attempted to send empty message')
      return
    }

    console.log('Sending message:', userMessage)
    setLoading(true)

    // Add user message to conversation
    setConversation((prev) => {
      const updated = [...prev, { role: 'user', content: userMessage }]
      console.log('User message added to conversation. Total messages:', updated.length)
      return updated
    })

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
      
      // Get current campaign to ensure we have the latest quest log (includes DM notes)
      const currentCampaign = campaignStorage.getCurrentCampaign()
      
      // Include character information in session state so DM knows about the party
      // CRITICAL: Always ensure we have characters for tool execution
      // Try multiple sources: props -> partyStorage -> empty object
      let characters = charactersFromProps || partyStorage.loadParty() || {}
      
      // If still no characters found, log warning
      if (Object.keys(characters).length === 0) {
        console.error('❌ CRITICAL: No characters found! Tools requiring character names will fail.')
        console.error('   Sources checked:')
        console.error('   - charactersFromProps:', !!charactersFromProps)
        console.error('   - partyStorage:', !!partyStorage.loadParty())
        console.error('   💡 Solution: Load characters in the Players panel or load a save point with characters.')
      } else {
        const source = charactersFromProps ? 'props' : 'partyStorage'
        console.log(`✅ Loaded ${Object.keys(characters).length} characters from ${source}:`, Object.keys(characters))
        
        // If we got characters from props but not partyStorage, save them
        if (charactersFromProps && !partyStorage.loadParty()) {
          console.log('   Saving characters to partyStorage for future use')
          partyStorage.saveParty(characters)
        }
      }
      
      const enhancedSessionState = sessionState ? {
        ...sessionState,
        // Use quest log from campaign if available (it has the latest updates including DM notes)
        // Fall back to sessionState quest_log if no campaign
        quest_log: currentCampaign?.questLog?.map(q => ({
          name: q.name,
          status: q.status,
          description: q.description,
          notes: q.notes, // This includes DM notes
        })) || sessionState.quest_log || [],
        // Add character information to session state - CRITICAL for tool execution
        party_members: Object.keys(characters).length > 0 
          ? Object.keys(characters).map(name => ({
              name,
              ...characters[name],
            }))
          : [], // Explicitly set to empty array if no characters
        // Also keep the party array for compatibility
        party: sessionState.party || (Object.keys(characters).length > 0 ? Object.keys(characters) : []),
      } : undefined

      console.log('Calling API with:', { 
        message: userMessage.substring(0, 50) + '...', 
        hasAdventure: !!adventureContext, 
        hasSession: !!enhancedSessionState, 
        hasCharacters: Object.keys(characters).length,
        characterNames: Object.keys(characters),
        partyMembersInState: enhancedSessionState?.party_members?.length || 0,
      })
      const response: DMResponse = await api.sendAction({
        message: userMessage,
        voice: voiceEnabled,
        adventure_context: adventureContext,
        session_state: enhancedSessionState,
      })

      console.log('API response received:', { narrative: response.narrative?.substring(0, 50) + '...', hasAudio: !!response.audio_url })

      // Add DM response to conversation
      setConversation((prev) => {
        const updated = [
          ...prev,
          {
            role: 'assistant',
            content: response.narrative,
            audio: response.audio_url,
          },
        ]
        console.log('DM response added to conversation. Total messages:', updated.length)
        return updated
      })

      // Update characters with new game state
      // CRITICAL: Merge game state characters with existing characters to preserve user edits
      if (response.game_state?.characters) {
        const gameStateCharacters = response.game_state.characters
        const existingCharacters = partyStorage.loadParty() || {}
        
        // Merge: Keep existing character data, but update with game state changes
        // This preserves user edits (like manually updated HP, stats, etc.) while applying game state updates
        const mergedCharacters: Record<string, any> = { ...existingCharacters }
        
        for (const [name, gameStateChar] of Object.entries(gameStateCharacters)) {
          if (mergedCharacters[name]) {
            // Merge existing character with game state character
            // Game state takes precedence for fields it provides, but we keep all other fields
            mergedCharacters[name] = {
              ...mergedCharacters[name], // Keep all existing fields (user edits, custom fields, etc.)
              ...gameStateChar, // Override with game state updates (HP changes, level ups, etc.)
            }
          } else {
            // New character from game state
            mergedCharacters[name] = gameStateChar
          }
        }
        
        partyStorage.saveParty(mergedCharacters)
        onCharactersUpdate?.(mergedCharacters)
        console.log(`✅ Merged ${Object.keys(mergedCharacters).length} characters (preserved user edits, applied game state updates)`)
      } else {
        // If no characters in response, check if we have them in partyStorage
        // This ensures we don't lose character data between messages
        const existingCharacters = partyStorage.loadParty()
        if (existingCharacters && Object.keys(existingCharacters).length > 0) {
          console.log(`⚠️  No characters in game_state response, but ${Object.keys(existingCharacters).length} characters exist in partyStorage`)
        } else {
          console.warn('⚠️  No characters in game_state response AND partyStorage is empty! Tools will fail.')
        }
      }

      // Automatically update quest log from DM response
      if (response.quest_updates && response.quest_updates.length > 0) {
        const currentCampaign = campaignStorage.getCurrentCampaign()
        if (currentCampaign) {
          console.log(`Auto-updating quest log with ${response.quest_updates.length} updates`)
          response.quest_updates.forEach((update: any) => {
            if (update.action === 'create') {
              // Create new quest
              const newQuest: QuestLogEntry = {
                id: `quest-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                name: update.name,
                description: update.description || '',
                status: update.status as 'not_started' | 'in_progress' | 'completed' | 'failed',
                notes: update.notes || '',
                timestamp: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              }
              campaignStorage.updateQuestLog(currentCampaign.id, newQuest)
              console.log(`Created new quest: ${update.name}`)
            } else if (update.action === 'update' || update.action === 'complete' || update.action === 'fail') {
              // Update existing quest
              const existingQuest = currentCampaign.questLog.find(q => 
                q.id === update.quest_id || q.name.toLowerCase() === update.name.toLowerCase()
              )
              if (existingQuest) {
                const updatedQuest: QuestLogEntry = {
                  ...existingQuest,
                  status: update.status as 'not_started' | 'in_progress' | 'completed' | 'failed',
                  notes: update.notes 
                    ? (existingQuest.notes ? `${existingQuest.notes}\n\n${update.notes}` : update.notes)
                    : existingQuest.notes,
                  updatedAt: new Date().toISOString(),
                }
                campaignStorage.updateQuestLog(currentCampaign.id, updatedQuest)
                console.log(`Updated quest: ${update.name} -> ${update.status}`)
              } else {
                // Quest not found, create it
                const newQuest: QuestLogEntry = {
                  id: update.quest_id || `quest-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                  name: update.name,
                  description: update.description || '',
                  status: update.status as 'not_started' | 'in_progress' | 'completed' | 'failed',
                  notes: update.notes || '',
                  timestamp: new Date().toISOString(),
                  updatedAt: new Date().toISOString(),
                }
                campaignStorage.updateQuestLog(currentCampaign.id, newQuest)
                console.log(`Created quest (not found): ${update.name}`)
              }
            }
          })
          
          // Update session state quest log to match campaign
          const updatedCampaign = campaignStorage.getCurrentCampaign()
          if (updatedCampaign) {
            const sessionState = sessionStorage.loadSession()
            if (sessionState) {
              sessionStorage.saveSession({
                ...sessionState,
                quest_log: updatedCampaign.questLog.map(q => ({
                  name: q.name,
                  status: q.status,
                  description: q.description,
                  notes: q.notes,
                })),
              })
            }
          }
        }
      }

      // Save adventure state - IMPORTANT: Save conversation with audio URL
      if (currentAdventure) {
        adventureStorage.updateAdventureState(
          currentAdventure.id,
          response.narrative,
          response.game_state,
          userMessage,
          response.audio_url
        )
        const updated = adventureStorage.getCurrentAdventure()
        if (updated) {
          onAdventureUpdate?.(updated)
        }
      }

      // Sync campaign with session state (location, quest log, etc.)
      // Always sync after game state updates to keep campaign in sync
      // Reload session state to get latest updates
      let currentSessionState = sessionStorage.loadSession()
      
      // If no session state exists, create one from game state
      if (!currentSessionState && response.game_state) {
        const currentCampaign = campaignStorage.getCurrentCampaign()
        currentSessionState = {
          campaign: currentCampaign?.campaignName || 'Unknown Campaign',
          session_number: currentCampaign?.sessionNumber || 1,
          date_started: currentCampaign?.dateStarted || new Date().toISOString().split('T')[0],
          current_location: response.game_state.location,
          active_encounter: response.game_state.active_encounter,
          party: response.game_state.party || [],
          quest_log: response.game_state.quest_log || [],
          world_state: response.game_state.world_state || {},
          party_inventory: response.game_state.party_inventory || { shared_items: [] },
          notes: [],
        }
        sessionStorage.saveSession(currentSessionState)
      } else if (currentSessionState && response.game_state) {
        // Update existing session state with game state
        const updatedSessionState = {
          ...currentSessionState,
          current_location: response.game_state.location || currentSessionState.current_location,
          quest_log: response.game_state.quest_log || currentSessionState.quest_log,
          world_state: { ...currentSessionState.world_state, ...(response.game_state.world_state || {}) },
          active_encounter: response.game_state.active_encounter || currentSessionState.active_encounter,
          party: response.game_state.party || currentSessionState.party,
        }
        sessionStorage.saveSession(updatedSessionState)
        currentSessionState = updatedSessionState
      }
      
      // Sync campaign with session state (this updates location, quest log, etc.)
      if (currentSessionState) {
        campaignStorage.syncWithSessionState(currentSessionState)
        const syncedCampaign = campaignStorage.getCurrentCampaign()
        // Update session state with synced session number (in case it was auto-incremented)
        if (syncedCampaign && syncedCampaign.sessionNumber !== currentSessionState.session_number) {
          sessionStorage.saveSession({
            ...currentSessionState,
            session_number: syncedCampaign.sessionNumber,
          })
          console.log(`📅 Session number updated to ${syncedCampaign.sessionNumber}`)
        }
        console.log('✅ Campaign synced with session state:', {
          location: currentSessionState.current_location,
          sessionNumber: syncedCampaign?.sessionNumber || currentSessionState.session_number,
          questCount: currentSessionState.quest_log?.length || 0,
        })
      }

      return response
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      console.error('Error details:', errorMessage)
      setConversation((prev) => {
        const updated = [
          ...prev,
          {
            role: 'system',
            content: `Error: ${errorMessage}`,
          },
        ]
        console.log('Error message added to conversation. Total messages:', updated.length)
        return updated
      })
      throw error
    } finally {
      setLoading(false)
      console.log('Loading state set to false')
    }
  }, [currentAdventure, voiceEnabled, onAdventureUpdate, onCharactersUpdate])

  const archiveChat = useCallback(() => {
    if (conversation.length === 0) return

    // Ensure we're archiving messages with content
    const messagesToArchive = conversation.filter(msg => 
      msg.content && msg.content.trim().length > 0
    )
    
    if (messagesToArchive.length === 0) {
      console.warn('No messages with content to archive')
      return
    }
    
    console.log('Archiving', messagesToArchive.length, 'messages:', messagesToArchive.map(m => ({
      role: m.role,
      contentLength: m.content?.length || 0,
      contentPreview: m.content?.substring(0, 50) || 'empty'
    })))

    // Archive current chat
    chatArchive.archiveChat(
      messagesToArchive.map(msg => ({
        role: msg.role,
        content: msg.content,
      })),
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

  const restoreChat = useCallback(async (messages: Array<{ role: string; content: string }>) => {
    console.log('Restoring archived chat:', messages.length, 'messages')
    console.log('Messages:', messages)
    
    // Filter out messages with empty or missing content
    const validMessages = messages.filter(msg => 
      msg && 
      msg.content && 
      typeof msg.content === 'string' && 
      msg.content.trim().length > 0
    )
    
    if (validMessages.length === 0) {
      console.error('No valid messages to restore (all have empty content)')
      console.error('Original messages:', messages)
      alert('Cannot restore: Archived chat has no valid messages. The archive may be corrupted.')
      return
    }
    
    if (validMessages.length < messages.length) {
      console.warn(`Filtered out ${messages.length - validMessages.length} messages with empty content`)
    }
    
    // Ensure messages are in the correct format
    const formattedMessages = validMessages.map(msg => ({
      role: msg.role || 'assistant',
      content: msg.content.trim(),
      // Preserve audio if it exists in the archived message
      audio: (msg as any).audio,
    }))
    
    console.log('Formatted messages to restore:', formattedMessages.length)
    formattedMessages.forEach((msg, idx) => {
      console.log(`Message ${idx}: role=${msg.role}, contentLength=${msg.content.length}, preview=${msg.content.substring(0, 50)}...`)
    })
    
    // Restore conversation in frontend
    setConversation(formattedMessages)
    console.log('Conversation state updated with', formattedMessages.length, 'messages')
    
    // Also restore conversation history in backend DM agent
    // Filter out system messages as they're not part of the conversation history
    const conversationMessages = formattedMessages.filter(msg => 
      msg.role === 'user' || msg.role === 'assistant'
    )
    
    if (conversationMessages.length > 0) {
      try {
        await api.restoreConversation(conversationMessages)
        console.log(`Restored ${conversationMessages.length} messages to backend DM agent`)
      } catch (error) {
        console.error('Failed to restore conversation history to backend:', error)
        // Don't throw - frontend is already restored, just log the error
      }
    }
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
