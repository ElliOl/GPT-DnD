/**
 * Campaign Storage Service
 * 
 * Campaigns are save states tied to Adventures.
 * They contain: quest log, world state, session state, party inventory, notes.
 */

export interface QuestLogEntry {
  id: string
  name: string
  status: 'not_started' | 'in_progress' | 'completed' | 'failed'
  description: string
  notes?: string
  timestamp: string
  updatedAt: string
}

export interface Campaign {
  id: string
  adventureId: string // Links to an Adventure
  campaignName: string
  sessionNumber: number
  dateStarted: string
  lastPlayed: string
  currentLocation?: string
  activeEncounter?: string
  party: string[] // Character names
  questLog: QuestLogEntry[]
  worldState: Record<string, any>
  partyInventory: {
    sharedItems: string[]
    goldPool?: number
  }
  notes: string[] // Session notes
  conversationHistory?: Array<{ role: string; content: string; timestamp: string }>
}

const CAMPAIGN_STORAGE_KEY = 'dnd-campaigns'
const CURRENT_CAMPAIGN_KEY = 'dnd-current-campaign-id'

export const campaignStorage = {
  /**
   * Save campaigns to localStorage
   */
  saveCampaigns(campaigns: Campaign[]): void {
    try {
      localStorage.setItem(CAMPAIGN_STORAGE_KEY, JSON.stringify(campaigns))
    } catch (error) {
      console.error('Failed to save campaigns:', error)
    }
  },

  /**
   * Load all campaigns
   */
  loadCampaigns(): Campaign[] {
    try {
      const stored = localStorage.getItem(CAMPAIGN_STORAGE_KEY)
      if (!stored) return []
      return JSON.parse(stored)
    } catch (error) {
      console.error('Failed to load campaigns:', error)
      return []
    }
  },

  /**
   * Get campaign for a specific adventure
   */
  getCampaignForAdventure(adventureId: string): Campaign | null {
    const campaigns = this.loadCampaigns()
    return campaigns.find(c => c.adventureId === adventureId) || null
  },

  /**
   * Save or update a campaign
   */
  saveCampaign(campaign: Campaign): void {
    const campaigns = this.loadCampaigns()
    const index = campaigns.findIndex(c => c.id === campaign.id)
    
    if (index >= 0) {
      campaigns[index] = { ...campaign, lastPlayed: new Date().toISOString() }
    } else {
      campaigns.push({ ...campaign, lastPlayed: new Date().toISOString() })
    }
    
    this.saveCampaigns(campaigns)
  },

  /**
   * Create a new campaign for an adventure
   */
  createCampaign(adventureId: string, campaignName: string, sessionState?: any): Campaign {
    const campaign: Campaign = {
      id: `campaign-${Date.now()}`,
      adventureId,
      campaignName,
      sessionNumber: 1,
      dateStarted: new Date().toISOString().split('T')[0],
      lastPlayed: new Date().toISOString(),
      party: [],
      questLog: [],
      worldState: {},
      partyInventory: {
        sharedItems: [],
      },
      notes: [],
      ...(sessionState || {}),
    }

    this.saveCampaign(campaign)
    return campaign
  },

  /**
   * Update campaign quest log
   */
  updateQuestLog(campaignId: string, quest: QuestLogEntry): void {
    const campaigns = this.loadCampaigns()
    const campaign = campaigns.find(c => c.id === campaignId)
    if (!campaign) return

    const index = campaign.questLog.findIndex(q => q.id === quest.id)
    if (index >= 0) {
      campaign.questLog[index] = quest
    } else {
      campaign.questLog.push(quest)
    }

    this.saveCampaign(campaign)
  },

  /**
   * Delete a campaign
   */
  deleteCampaign(campaignId: string): void {
    const campaigns = this.loadCampaigns().filter(c => c.id !== campaignId)
    this.saveCampaigns(campaigns)
    
    // Clear current campaign if it was deleted
    const currentId = localStorage.getItem(CURRENT_CAMPAIGN_KEY)
    if (currentId === campaignId) {
      localStorage.removeItem(CURRENT_CAMPAIGN_KEY)
    }
  },

  /**
   * Set current active campaign
   */
  setCurrentCampaign(campaignId: string | null): void {
    if (campaignId) {
      localStorage.setItem(CURRENT_CAMPAIGN_KEY, campaignId)
    } else {
      localStorage.removeItem(CURRENT_CAMPAIGN_KEY)
    }
  },

  /**
   * Get current active campaign
   */
  getCurrentCampaign(): Campaign | null {
    const campaignId = localStorage.getItem(CURRENT_CAMPAIGN_KEY)
    if (!campaignId) return null
    
    const campaigns = this.loadCampaigns()
    return campaigns.find(c => c.id === campaignId) || null
  },

  /**
   * Load campaign from session state file
   */
  async loadFromSessionFile(file: File, adventureId: string): Promise<Campaign> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const sessionData = JSON.parse(e.target?.result as string)
          
          // Convert session state to campaign format
          const campaign: Campaign = {
            id: `campaign-${Date.now()}`,
            adventureId,
            campaignName: sessionData.campaign || 'Imported Campaign',
            sessionNumber: sessionData.session_number || 1,
            dateStarted: sessionData.date_started || new Date().toISOString().split('T')[0],
            lastPlayed: new Date().toISOString(),
            currentLocation: sessionData.current_location,
            activeEncounter: sessionData.active_encounter,
            party: sessionData.party || [],
            questLog: (sessionData.quest_log || []).map((q: any, idx: number) => ({
              id: `quest-${Date.now()}-${idx}`,
              name: q.name,
              status: q.status || 'in_progress',
              description: q.description,
              notes: q.notes,
              timestamp: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            })),
            worldState: sessionData.world_state || {},
            partyInventory: sessionData.party_inventory || {
              sharedItems: [],
            },
            notes: sessionData.notes || [],
          }

          resolve(campaign)
        } catch (error) {
          reject(error)
        }
      }
      reader.onerror = reject
      reader.readAsText(file)
    })
  },

  /**
   * Export campaign to file
   */
  exportToFile(campaign: Campaign): void {
    // Convert back to session state format for compatibility
    const sessionData = {
      campaign: campaign.campaignName,
      session_number: campaign.sessionNumber,
      date_started: campaign.dateStarted,
      current_location: campaign.currentLocation,
      active_encounter: campaign.activeEncounter,
      party: campaign.party,
      quest_log: campaign.questLog.map(q => ({
        name: q.name,
        status: q.status,
        description: q.description,
        notes: q.notes,
      })),
      world_state: campaign.worldState,
      party_inventory: campaign.partyInventory,
      notes: campaign.notes,
    }

    const blob = new Blob([JSON.stringify(sessionData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `campaign-${campaign.campaignName.toLowerCase().replace(/\s+/g, '-')}-session${campaign.sessionNumber}-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },
}
