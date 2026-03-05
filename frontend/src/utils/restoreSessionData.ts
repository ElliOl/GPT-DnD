/**
 * Utility to restore session data from current_session.json format
 * This will:
 * 1. Save to sessionStorage
 * 2. Create/update Campaign in campaignStorage
 * 3. Create a save point in the adventure's history
 */

import { sessionStorage, type SessionState } from '../services/sessionStorage'
import { campaignStorage, type Campaign } from '../services/campaignStorage'
import { adventureStorage } from '../services/adventureStorage'

export interface SessionDataFile {
  campaign: string
  session_number: number
  date_started: string
  current_location?: string
  active_encounter?: string
  party: string[]
  quest_log: Array<{
    name: string
    status: 'not_started' | 'in_progress' | 'completed' | 'failed'
    description: string
    notes?: string
  }>
  world_state: Record<string, any>
  party_inventory: {
    shared_items: string[]
    gold_pool?: number
  }
  notes: string[]
}

/**
 * Restore session data from the current_session.json format
 */
export function restoreSessionData(
  sessionData: SessionDataFile,
  adventureId: string = 'adv-lost-mines-phandelver'
): {
  sessionState: SessionState
  campaign: Campaign
  savePointId?: string
} {
  // 1. Convert to SessionState and save
  const sessionState: SessionState = {
    campaign: sessionData.campaign,
    session_number: sessionData.session_number,
    date_started: sessionData.date_started,
    current_location: sessionData.current_location,
    active_encounter: sessionData.active_encounter,
    party: sessionData.party,
    quest_log: sessionData.quest_log,
    world_state: sessionData.world_state,
    party_inventory: {
      shared_items: sessionData.party_inventory.shared_items,
      gold_pool: sessionData.party_inventory.gold_pool,
    },
    notes: sessionData.notes,
  }
  
  sessionStorage.saveSession(sessionState)
  console.log('✅ Session state restored to sessionStorage')

  // 2. Convert to Campaign and save
  const existingCampaign = campaignStorage.getCampaignForAdventure(adventureId)
  
  const questLog = sessionData.quest_log.map((q, idx) => ({
    id: `quest-${Date.now()}-${idx}`,
    name: q.name,
    status: q.status || 'in_progress',
    description: q.description,
    notes: q.notes,
    timestamp: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }))

  const campaign: Campaign = {
    id: existingCampaign?.id || `campaign-${Date.now()}`,
    adventureId,
    campaignName: sessionData.campaign,
    sessionNumber: sessionData.session_number,
    dateStarted: sessionData.date_started,
    lastPlayed: new Date().toISOString(),
    currentLocation: sessionData.current_location,
    activeEncounter: sessionData.active_encounter,
    party: sessionData.party,
    questLog,
    worldState: sessionData.world_state,
    partyInventory: {
      sharedItems: sessionData.party_inventory.shared_items,
      goldPool: sessionData.party_inventory.gold_pool,
    },
    notes: sessionData.notes,
  }

  campaignStorage.saveCampaign(campaign)
  campaignStorage.setCurrentCampaign(campaign.id)
  console.log('✅ Campaign restored to campaignStorage')

  // 3. Create a save point in the adventure's history
  let savePointId: string | undefined
  
  let adventure = adventureStorage.getCurrentAdventure()
  if (!adventure || adventure.id !== adventureId) {
    adventure = adventureStorage.loadAdventures().find(a => a.id === adventureId) || null
  }
  
  if (adventure) {
    // Set as current adventure if not already
    if (adventureStorage.getCurrentAdventure()?.id !== adventure.id) {
      adventureStorage.setCurrentAdventure(adventure.id)
    }
    const savePointDescription = `Session ${sessionData.session_number} - ${sessionData.current_location || 'Current State'}`
    const narrative = `You are at ${sessionData.current_location || 'your current location'}. ${sessionData.notes.join(' ')}`
    
    // Create game state object for the save point
    const gameState = {
      campaign: sessionData.campaign,
      session_number: sessionData.session_number,
      current_location: sessionData.current_location,
      active_encounter: sessionData.active_encounter,
      party: sessionData.party,
      quest_log: sessionData.quest_log,
      world_state: sessionData.world_state,
      party_inventory: sessionData.party_inventory,
    }

    const savePoint = adventureStorage.addSavePoint(
      adventure.id,
      savePointDescription,
      narrative,
      gameState
    )
    
    savePointId = savePoint.id
    console.log('✅ Save point created in adventure history:', savePoint.id)
  } else {
    console.warn('⚠️ Adventure not found, skipping save point creation')
  }

  return {
    sessionState,
    campaign,
    savePointId,
  }
}

/**
 * Load and restore session data from a file
 */
export async function restoreSessionDataFromFile(file: File, adventureId?: string): Promise<{
  sessionState: SessionState
  campaign: Campaign
  savePointId?: string
}> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string
        const sessionData: SessionDataFile = JSON.parse(text)
        const result = restoreSessionData(sessionData, adventureId)
        resolve(result)
      } catch (error) {
        reject(error)
      }
    }
    reader.onerror = reject
    reader.readAsText(file)
  })
}

