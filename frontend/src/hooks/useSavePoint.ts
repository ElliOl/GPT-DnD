import { useCallback } from 'react'
import { api, type DMResponse } from '../services/api'
import { adventureStorage, type Adventure, type SavePoint } from '../services/adventureStorage'
import { sessionStorage } from '../services/sessionStorage'
import { campaignStorage } from '../services/campaignStorage'
import { chatArchive } from '../services/chatArchive'
import { partyStorage } from '../services/partyStorage'
import type { SessionState } from '../services/sessionStorage'
import type { Message } from './useConversation'

interface UseSavePointOptions {
  currentAdventure: Adventure | null
  conversation: Message[]
  voiceEnabled: boolean
  onConversationUpdate: (messages: Message[]) => void
  onAdventureUpdate: (adventure: Adventure | null) => void
  onCharactersUpdate?: (characters: Record<string, any>) => void
}

interface CreateSavePointOptions {
  description?: string
  narrative?: string
}

export function useSavePoint({
  currentAdventure,
  conversation,
  voiceEnabled,
  onConversationUpdate,
  onAdventureUpdate,
  onCharactersUpdate,
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

    // Restore session state and game state (characters) if save point has gameState
    let restoredCharacters: Record<string, any> = {}
    if (savePoint.gameState) {
      const sessionData = savePoint.gameState as any
      sessionStorage.saveSession(sessionData)
      
      // Update adventure metadata with current location from session state
      // This ensures the AdventureContext knows where the players are
      if (sessionData.current_location) {
        try {
          await api.updateAdventureState({
            location: sessionData.current_location,
          })
          console.log(`Updated adventure location to: ${sessionData.current_location}`)
        } catch (err) {
          console.error('Failed to update adventure location:', err)
          // Don't throw - continue with restore even if location update fails
        }
      }
      
      // Update session number if available
      // NOTE: This may fail if adventure isn't loaded on backend - that's okay, continue anyway
      if (sessionData.session_number) {
        try {
          await api.updateAdventureState({
            session_number: sessionData.session_number,
          })
        } catch (err) {
          // This is non-critical - the adventure might not be loaded on backend yet
          // The session_state will still have the session_number, so DM will see it
          console.warn('Could not update adventure session number (adventure may not be loaded on backend):', err)
        }
      }
      
      // Restore characters from game state
      // Save points store party as an object (Record<string, Character>)
      if (sessionData.party) {
        if (Array.isArray(sessionData.party)) {
          // Legacy format: party is an array
          sessionData.party.forEach((char: any) => {
            if (char && typeof char === 'object' && char.name) {
              restoredCharacters[char.name] = char
            } else if (typeof char === 'string') {
              // Just a name string - try to load from partyStorage
              const existingChar = partyStorage.loadParty()?.[char]
              if (existingChar) {
                restoredCharacters[char] = existingChar
              }
            }
          })
        } else if (typeof sessionData.party === 'object' && sessionData.party !== null) {
          // Modern format: party is an object (Record<string, Character>)
          // Check if it's empty
          const partyKeys = Object.keys(sessionData.party)
          if (partyKeys.length > 0) {
            // It's a character object
            Object.assign(restoredCharacters, sessionData.party)
          } else {
            console.warn('Save point has party object but it is empty')
          }
        }
        
        if (Object.keys(restoredCharacters).length > 0) {
          partyStorage.saveParty(restoredCharacters)
          onCharactersUpdate?.(restoredCharacters)
          console.log(`✅ Restored ${Object.keys(restoredCharacters).length} characters from save point:`, Object.keys(restoredCharacters))
        } else {
          console.warn('⚠️  Save point has party data but no characters were extracted. Party data:', {
            type: typeof sessionData.party,
            isArray: Array.isArray(sessionData.party),
            keys: sessionData.party ? Object.keys(sessionData.party) : 'null',
            value: sessionData.party,
          })
        }
      } else {
        console.warn('⚠️  Save point has no party data in gameState')
      }
    }
    
    // If no characters were restored from save point, try to load from partyStorage
    if (Object.keys(restoredCharacters).length === 0) {
      const existingCharacters = partyStorage.loadParty()
      if (existingCharacters && Object.keys(existingCharacters).length > 0) {
        restoredCharacters = existingCharacters
        console.log(`Using existing characters from partyStorage: ${Object.keys(restoredCharacters).length} characters`)
      }
    }
    
    // Log character restoration status
    console.log('Character restoration status:', {
      restoredFromSavePoint: Object.keys(restoredCharacters).length > 0,
      characterCount: Object.keys(restoredCharacters).length,
      characterNames: Object.keys(restoredCharacters),
      savePointHasParty: !!(savePoint.gameState?.party),
      partyType: savePoint.gameState?.party ? typeof savePoint.gameState.party : 'none',
    })

    // Restore conversation history from save point if available
    let conversationHistoryToRestore: Array<{ role: string; content: string }> = []
    if (savePoint.conversationHistory && savePoint.conversationHistory.length > 0) {
      // Filter out messages with empty content (Anthropic API doesn't allow them)
      conversationHistoryToRestore = savePoint.conversationHistory
        .filter(msg => msg.content && msg.content.trim() !== '') // Only include messages with content
        .map(msg => ({
          role: msg.role,
          content: msg.content,
        }))
      console.log(`Restoring ${conversationHistoryToRestore.length} messages from save point conversation history (filtered out empty messages)`)
    }

    // Check if we have characters but they're not mentioned in conversation history
    // If so, add a system message to inform the DM about the existing party
    const finalCharacters = Object.keys(restoredCharacters).length > 0 
      ? restoredCharacters 
      : (partyStorage.loadParty() || {})
    
    if (Object.keys(finalCharacters).length > 0 && conversationHistoryToRestore.length > 0) {
      // Check if any character names appear in the conversation history
      const charNames = Object.keys(finalCharacters)
      const conversationText = conversationHistoryToRestore
        .map(msg => msg.content)
        .join(' ')
        .toLowerCase()
      
      const charactersMentioned = charNames.some(name => 
        conversationText.includes(name.toLowerCase())
      )
      
      // If characters exist but aren't mentioned, prepend a system message
      if (!charactersMentioned) {
        const charList = charNames.map(name => {
          const char = finalCharacters[name]
          const charClass = char.char_class || char.class || 'Adventurer'
          const level = char.level || 1
          return `${name} (Level ${level} ${charClass})`
        }).join(', ')
        
        conversationHistoryToRestore.unshift({
          role: 'system',
          content: `[SYSTEM: We are continuing an existing adventure. The party consists of: ${charList}. This is not a new game - these characters already exist and have been playing.]`,
        })
        console.log('Added system message about existing party to conversation history')
      }
    }

    // Restore conversation history to backend DM agent
    if (conversationHistoryToRestore.length > 0) {
      try {
        await api.restoreConversation(conversationHistoryToRestore)
        console.log('Restored conversation history to backend DM agent')
      } catch (err) {
        console.error('Failed to restore conversation history to backend:', err)
      }
    }

    // Restore conversation in frontend
    const frontendMessages = conversationHistoryToRestore.map(msg => ({
      role: msg.role,
      content: msg.content,
      audio: savePoint.conversationHistory?.find(m => 
        m.role === msg.role && m.content === msg.content
      )?.audio,
    }))
    onConversationUpdate(frontendMessages)
    
    // Update adventure conversation history to match save point
    adventureStorage.updateAdventure(currentAdventure.id, {
      conversationHistory: savePoint.conversationHistory || [],
    })

    // If we have conversation history, the DM already knows the context
    // Only send narration prompt if we don't have conversation history
    // (for backward compatibility with old save points)
    if (conversationHistoryToRestore.length === 0) {
      // Trigger DM narration of the restored state (for old save points without conversation history)
      const narrationPrompt = savePoint.narrative 
        ? `Continue from: ${savePoint.narrative}`
        : `Describe the current situation. We are at: ${savePoint.description}`

      try {
        // Get session state
        const sessionState = sessionStorage.loadSession()
        
        // Get current campaign to ensure we have the latest quest log (includes DM notes)
        const currentCampaign = campaignStorage.getCurrentCampaign()
        
        // Use restored characters or load from partyStorage
        const characters = Object.keys(restoredCharacters).length > 0 
          ? restoredCharacters 
          : (partyStorage.loadParty() || {})
        
        // Include character information in session state so DM knows about the party
        const enhancedSessionState = {
          ...sessionState,
          // Use quest log from campaign if available (it has the latest updates including DM notes)
          // Fall back to sessionState quest_log if no campaign
          quest_log: currentCampaign?.questLog?.map(q => ({
            name: q.name,
            status: q.status,
            description: q.description,
            notes: q.notes, // This includes DM notes
          })) || sessionState?.quest_log || [],
          // Add character information to session state
          party_members: Object.keys(characters).map(name => ({
            name,
            ...characters[name],
          })),
          // Also keep the party array for compatibility
          party: sessionState?.party || Object.keys(characters),
        }

        // Don't pass adventure_context - let the backend's modular adventure system
        // handle it automatically based on the current location in session_state
        // This ensures the DM gets the right location-specific context
        const response: DMResponse = await api.sendAction({
          message: narrationPrompt,
          voice: voiceEnabled,
          adventure_context: undefined, // Let backend use modular adventure system
          session_state: enhancedSessionState,
        })

            // Update characters if game state changed
            // Merge with existing to preserve user edits
            if (response.game_state?.characters) {
              const gameStateCharacters = response.game_state.characters
              const existingCharacters = partyStorage.loadParty() || {}
              
              // Merge: Keep existing character data, but update with game state changes
              const mergedCharacters: Record<string, any> = { ...existingCharacters }
              for (const [name, gameStateChar] of Object.entries(gameStateCharacters)) {
                if (mergedCharacters[name]) {
                  mergedCharacters[name] = {
                    ...mergedCharacters[name], // Preserve user edits
                    ...gameStateChar, // Apply game state updates
                  }
                } else {
                  mergedCharacters[name] = gameStateChar
                }
              }
              
              partyStorage.saveParty(mergedCharacters)
              onCharactersUpdate?.(mergedCharacters)
            }

        // Add DM response to conversation state
        const newMessages = [
          ...frontendMessages,
          {
            role: 'assistant' as const,
            content: response.narrative,
            audio: response.audio_url,
          },
        ]
        onConversationUpdate(newMessages)

        // IMPORTANT: Save to conversation history so it persists across refreshes
        // This includes the audio URL so it can be restored
        if (currentAdventure) {
          adventureStorage.updateAdventureState(
            currentAdventure.id,
            response.narrative,
            response.game_state,
            narrationPrompt,
            response.audio_url
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
          ...frontendMessages,
          {
            role: 'system',
            content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
          },
        ])
        throw error
      }
    } else {
      // We have conversation history, but we still need to refresh the DM's context
      // with current session state (location, quest log, world state, characters, etc.)
      // The DM agent gets session_state context on every message, so we need to send one
      // to ensure it has the current state. We'll send a simple context refresh message.
      try {
        const sessionState = sessionStorage.loadSession()
        
        // Get current campaign to ensure we have the latest quest log (includes DM notes)
        const currentCampaign = campaignStorage.getCurrentCampaign()
        
        // Use restored characters or load from partyStorage
        // CRITICAL: Always ensure we have characters, even if save point didn't have them
        let characters = Object.keys(restoredCharacters).length > 0 
          ? restoredCharacters 
          : (partyStorage.loadParty() || {})
        
        // Final fallback: if still no characters, try one more time
        if (Object.keys(characters).length === 0) {
          console.warn('🚨 No characters found in restoredCharacters or partyStorage. Attempting emergency load...')
          const emergencyLoad = partyStorage.loadParty()
          if (emergencyLoad && Object.keys(emergencyLoad).length > 0) {
            characters = emergencyLoad
            console.log(`✅ Emergency load successful: ${Object.keys(characters).length} characters`)
          }
        }
        
        // Log what we're about to send
        console.log('📤 Preparing to send context refresh with characters:', {
          characterCount: Object.keys(characters).length,
          characterNames: Object.keys(characters),
          characterDetails: Object.keys(characters).map(name => ({
            name,
            class: characters[name]?.char_class || characters[name]?.class,
            level: characters[name]?.level,
          })),
        })
        
        // Include character information in session state so DM knows about the party
        const enhancedSessionState = {
          ...sessionState,
          // Use quest log from campaign if available (it has the latest updates including DM notes)
          // Fall back to sessionState quest_log if no campaign
          quest_log: currentCampaign?.questLog?.map(q => ({
            name: q.name,
            status: q.status,
            description: q.description,
            notes: q.notes, // This includes DM notes
          })) || sessionState?.quest_log || [],
          // Add character information to session state - CRITICAL for DM to know about party
          party_members: Object.keys(characters).length > 0 
            ? Object.keys(characters).map(name => ({
                name,
                ...characters[name],
              }))
            : [], // Explicitly set to empty array if no characters
          // Also keep the party array for compatibility
          party: sessionState?.party || (Object.keys(characters).length > 0 ? Object.keys(characters) : []),
        }
        
        // Final verification before sending
        if (!enhancedSessionState.party_members || enhancedSessionState.party_members.length === 0) {
          console.error('❌ CRITICAL ERROR: enhancedSessionState.party_members is empty!', {
            charactersObject: characters,
            characterKeys: Object.keys(characters),
            sessionStateParty: sessionState?.party,
          })
        } else {
          console.log('✅ enhancedSessionState.party_members populated:', {
            count: enhancedSessionState.party_members.length,
            names: enhancedSessionState.party_members.map((p: any) => p.name),
          })
        }
        
        console.log('Sending context refresh with:', {
          location: enhancedSessionState.current_location,
          partyMembers: enhancedSessionState.party_members?.length || 0,
          hasQuestLog: (enhancedSessionState.quest_log?.length || 0) > 0,
          questLogEntries: enhancedSessionState.quest_log?.map(q => ({
            name: q.name,
            hasDescription: !!q.description,
            hasNotes: !!q.notes,
          })),
          characterNames: enhancedSessionState.party_members?.map((p: any) => p.name) || [],
          partyMembersData: enhancedSessionState.party_members?.map((p: any) => ({
            name: p.name,
            class: p.char_class || p.class,
            level: p.level,
          })) || [],
        })
        
        // CRITICAL: If no characters found, log warning and try to load from partyStorage one more time
        if (!enhancedSessionState.party_members || enhancedSessionState.party_members.length === 0) {
          console.warn('⚠️  No party_members in session_state! Attempting to load from partyStorage...')
          const lastChanceCharacters = partyStorage.loadParty()
          if (lastChanceCharacters && Object.keys(lastChanceCharacters).length > 0) {
            console.log(`✅ Found ${Object.keys(lastChanceCharacters).length} characters in partyStorage, adding to session_state`)
            enhancedSessionState.party_members = Object.keys(lastChanceCharacters).map(name => ({
              name,
              ...lastChanceCharacters[name],
            }))
            enhancedSessionState.party = Object.keys(lastChanceCharacters)
          } else {
            console.error('❌ No characters found in partyStorage either! Characters may not be saved.')
          }
        }

        // Build a more explicit context refresh message that tells the DM we're continuing
        // This helps prevent the DM from thinking we're starting fresh
        let contextMessage = "We are continuing our adventure. "
        
        // CRITICAL: Ensure we have characters before building the message
        if (!enhancedSessionState.party_members || enhancedSessionState.party_members.length === 0) {
          // Last attempt: load directly from partyStorage
          const emergencyCharacters = partyStorage.loadParty()
          if (emergencyCharacters && Object.keys(emergencyCharacters).length > 0) {
            console.log('🚨 Emergency: Loading characters directly from partyStorage for context message')
            enhancedSessionState.party_members = Object.keys(emergencyCharacters).map(name => ({
              name,
              ...emergencyCharacters[name],
            }))
            enhancedSessionState.party = Object.keys(emergencyCharacters)
          }
        }
        
        if (enhancedSessionState.party_members && enhancedSessionState.party_members.length > 0) {
          const charDetails = enhancedSessionState.party_members.map((p: any) => {
            const name = p.name || p
            const charClass = p.char_class || p.class || 'Adventurer'
            const level = p.level || 1
            return `${name} (Level ${level} ${charClass})`
          }).join(', ')
          contextMessage += `Our party consists of: ${charDetails}. `
        } else {
          console.error('❌ CRITICAL: No characters found even after emergency load!')
          contextMessage += `[WARNING: Character data not found in save point. Please verify characters are saved.] `
        }
        
        if (enhancedSessionState.current_location) {
          contextMessage += `We are currently at: ${enhancedSessionState.current_location}. `
        }
        
        if (enhancedSessionState.quest_log && enhancedSessionState.quest_log.length > 0) {
          const activeQuests = enhancedSessionState.quest_log
            .filter((q: any) => q.status === 'in_progress' || q.status === 'not_started')
            .map((q: any) => q.name)
          if (activeQuests.length > 0) {
            contextMessage += `Our active quests are: ${activeQuests.join(', ')}. `
          }
        }
        
        contextMessage += "What is our current situation?"

        // Final check: Log exactly what we're sending to the backend
        console.log('🚀 FINAL CHECK - About to send to backend:', {
          message: contextMessage.substring(0, 100) + '...',
          sessionStateKeys: Object.keys(enhancedSessionState),
          partyMembersCount: enhancedSessionState.party_members?.length || 0,
          partyMembers: enhancedSessionState.party_members?.map((p: any) => ({
            name: p.name,
            hasClass: !!(p.char_class || p.class),
            hasLevel: !!p.level,
            keys: Object.keys(p),
          })) || [],
          partyArray: enhancedSessionState.party,
        })

        // Don't pass adventure_context - let the backend's modular adventure system
        // handle it automatically based on the current location in session_state
        // This ensures the DM gets the right location-specific context
        const response: DMResponse = await api.sendAction({
          message: contextMessage, // Explicit context message that includes party info
          voice: voiceEnabled, // Generate audio if enabled
          adventure_context: undefined, // Let backend use modular adventure system
          session_state: enhancedSessionState,
        })

            // Update characters if game state changed
            // Merge with existing to preserve user edits
            if (response.game_state?.characters) {
              const gameStateCharacters = response.game_state.characters
              const existingCharacters = partyStorage.loadParty() || {}
              
              // Merge: Keep existing character data, but update with game state changes
              const mergedCharacters: Record<string, any> = { ...existingCharacters }
              for (const [name, gameStateChar] of Object.entries(gameStateCharacters)) {
                if (mergedCharacters[name]) {
                  mergedCharacters[name] = {
                    ...mergedCharacters[name], // Preserve user edits
                    ...gameStateChar, // Apply game state updates
                  }
                } else {
                  mergedCharacters[name] = gameStateChar
                }
              }
              
              partyStorage.saveParty(mergedCharacters)
              onCharactersUpdate?.(mergedCharacters)
            }

        // Add the context refresh to conversation (it ensures DM has all current info)
        const updatedMessages = [
          ...frontendMessages,
          {
            role: 'user' as const,
            content: contextMessage,
          },
          {
            role: 'assistant' as const,
            content: response.narrative,
            audio: response.audio_url,
          },
        ]
        onConversationUpdate(updatedMessages)

        // Update conversation history in adventure storage
        if (currentAdventure) {
          adventureStorage.updateAdventureState(
            currentAdventure.id,
            response.narrative,
            response.game_state,
            contextMessage,
            response.audio_url
          )
        }

        console.log('Context refreshed with current session state and game state')
        return response
      } catch (error) {
        console.error('Failed to refresh context:', error)
        // Don't throw - we still have conversation history restored
        return null
      }
    }
  }, [currentAdventure, conversation, voiceEnabled, onConversationUpdate, onAdventureUpdate, onCharactersUpdate])

  const createSavePoint = useCallback(async (options: CreateSavePointOptions = {}): Promise<SavePoint | null> => {
    if (!currentAdventure) {
      console.error('Cannot create save point: No adventure loaded')
      return null
    }

    try {
      // Get current session state
      const sessionState = sessionStorage.loadSession()
      
      // Get current campaign to ensure we have the latest quest log (includes DM notes)
      const currentCampaign = campaignStorage.getCurrentCampaign()
      
      // Get current characters
      const characters = partyStorage.loadParty() || {}
      
      // Get the last DM narrative from conversation
      const lastDMNarrative = conversation
        .filter(msg => msg.role === 'assistant')
        .map(msg => msg.content)
        .pop() || ''
      
      // Create description if not provided
      const description = options.description || 
        (sessionState.current_location 
          ? `Session ${sessionState.session_number || '?'} - ${sessionState.current_location}`
          : `Save Point - ${new Date().toLocaleString()}`)
      
      // Use provided narrative or last DM narrative or description
      const narrative = options.narrative || lastDMNarrative || description
      
      // Use quest log from campaign if available (it has the latest updates including DM notes)
      // Fall back to sessionState quest_log if no campaign
      const questLog = currentCampaign?.questLog?.map(q => ({
        name: q.name,
        status: q.status,
        description: q.description,
        notes: q.notes, // This includes DM notes
      })) || sessionState?.quest_log || []
      
      // CRITICAL: Ensure we have characters before creating save point
      if (Object.keys(characters).length === 0) {
        console.warn('⚠️  No characters found when creating save point! Attempting to load from partyStorage...')
        const emergencyChars = partyStorage.loadParty()
        if (emergencyChars && Object.keys(emergencyChars).length > 0) {
          characters = emergencyChars
          console.log(`✅ Loaded ${Object.keys(characters).length} characters from partyStorage for save point`)
        } else {
          console.error('❌ No characters found in partyStorage either! Save point will be created without character data.')
        }
      }
      
      // Log what we're saving
      console.log('💾 Creating save point with:', {
        characterCount: Object.keys(characters).length,
        characterNames: Object.keys(characters),
        location: sessionState.current_location,
        questLogCount: questLog.length,
      })
      
      // Create game state snapshot
      // Note: party in SessionState is string[] (character names), but we store full character objects in gameState
      const gameState: any = {
        campaign: sessionState.campaign || currentAdventure.name,
        session_number: sessionState.session_number || 1,
        date_started: sessionState.date_started || new Date().toISOString(),
        current_location: sessionState.current_location || '',
        active_encounter: sessionState.active_encounter || '',
        party: characters, // Store full character objects in save point gameState - CRITICAL for restoration
        quest_log: questLog, // Use latest quest log from campaign
        world_state: sessionState.world_state || {},
        party_inventory: sessionState.party_inventory || { shared_items: [] },
        notes: sessionState.notes || [],
      }
      
      // Verify characters are in gameState
      if (!gameState.party || Object.keys(gameState.party).length === 0) {
        console.error('❌ CRITICAL: Save point gameState.party is empty! This will cause restoration issues.')
      } else {
        console.log(`✅ Save point will include ${Object.keys(gameState.party).length} characters in gameState.party`)
      }
      
      // Get conversation history
      const conversationHistory = currentAdventure.conversationHistory || conversation.map(msg => ({
        role: msg.role,
        content: msg.content,
        timestamp: new Date().toISOString(),
        audio: msg.audio,
      }))
      
      // Create save point
      const savePoint = adventureStorage.addSavePoint(
        currentAdventure.id,
        description,
        narrative,
        gameState,
        conversationHistory
      )
      
      // Update current adventure to reflect new save point
      const updated = adventureStorage.getCurrentAdventure()
      if (updated) {
        onAdventureUpdate(updated)
      }
      
      console.log(`✅ Created save point: ${savePoint.id} - ${description}`)
      return savePoint
    } catch (error) {
      console.error('Failed to create save point:', error)
      throw error
    }
  }, [currentAdventure, conversation, onAdventureUpdate])

  return {
    loadSavePoint,
    createSavePoint,
  }
}
