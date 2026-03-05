import { useState, useRef, useEffect } from 'react'
import { BookOpen, Upload, Download, Plus, Trash2, Save, FolderOpen, ChevronDown, ChevronRight, FileDown, FileUp, History, FileText, X, Check, Loader2, RotateCcw, CheckCircle2 } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import { Input } from '@base-ui/react/input'
import { campaignStorage, type Campaign, type QuestLogEntry } from '../services/campaignStorage'
import { sessionStorage } from '../services/sessionStorage'
import { useModularAdventure } from '../hooks/useModularAdventure'

interface AdventureSetupProps {
  onCampaignLoaded?: (campaign: Campaign) => void
  onQuestLogUpdated?: (questLog: QuestLogEntry[]) => void
}

export function AdventureSetup({ onAdventureLoaded, onCampaignLoaded, onQuestLogUpdated }: AdventureSetupProps = {}) {
  // Modular Adventure System (Backend)
  const {
    availableAdventures,
    loadingAdventures,
    currentAdventure: modularAdventure,
    loadingCurrent,
    loadAdventure: loadModularAdventure,
    error: modularError,
  } = useModularAdventure()

  // Campaign System
  const [currentCampaign, setCurrentCampaign] = useState<Campaign | null>(null)
  const [isCreatingQuest, setIsCreatingQuest] = useState(false)
  const [newQuestName, setNewQuestName] = useState('')
  const [newQuestDescription, setNewQuestDescription] = useState('')
  const campaignFileInputRef = useRef<HTMLInputElement>(null)
  const [expandedQuests, setExpandedQuests] = useState<Set<string>>(new Set())
  const [editingQuestNotes, setEditingQuestNotes] = useState<Set<string>>(new Set())
  const [openStatusDropdown, setOpenStatusDropdown] = useState<string | null>(null)
  const statusDropdownRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const [dropdownPosition, setDropdownPosition] = useState<{ top: number; left: number } | null>(null)

  // Close dropdown when clicking outside and calculate position
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (openStatusDropdown) {
        const buttonElement = statusDropdownRefs.current.get(openStatusDropdown)
        const dropdownElement = document.querySelector(`[data-status-dropdown="${openStatusDropdown}"]`)
        if (buttonElement && dropdownElement) {
          if (!buttonElement.contains(event.target as Node) && !dropdownElement.contains(event.target as Node)) {
            setOpenStatusDropdown(null)
            setDropdownPosition(null)
          }
        }
      }
    }
    
    const updatePosition = () => {
      if (openStatusDropdown) {
        const buttonElement = statusDropdownRefs.current.get(openStatusDropdown)
        if (buttonElement) {
          const rect = buttonElement.getBoundingClientRect()
          setDropdownPosition({
            top: rect.bottom + 4, // Fixed positioning is relative to viewport, not document
            left: rect.left
          })
        }
      }
    }

    if (openStatusDropdown) {
      updatePosition()
      window.addEventListener('scroll', updatePosition, true)
      window.addEventListener('resize', updatePosition)
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        window.removeEventListener('scroll', updatePosition, true)
        window.removeEventListener('resize', updatePosition)
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [openStatusDropdown])

  // Load current campaign on mount and sync with session state
  useEffect(() => {
    const campaign = campaignStorage.getCurrentCampaign()
    if (campaign) {
      // Sync with current session state to ensure location and quest log are up to date
      const sessionState = sessionStorage.loadSession()
      if (sessionState) {
        campaignStorage.syncWithSessionState(sessionState)
        const syncedCampaign = campaignStorage.getCurrentCampaign()
        if (syncedCampaign) {
          setCurrentCampaign(syncedCampaign)
          if (onCampaignLoaded) {
            onCampaignLoaded(syncedCampaign)
          }
          if (onQuestLogUpdated) {
            onQuestLogUpdated(syncedCampaign.questLog)
          }
          return
        }
      }
      
      setCurrentCampaign(campaign)
      if (onCampaignLoaded) {
        onCampaignLoaded(campaign)
      }
      if (onQuestLogUpdated) {
        onQuestLogUpdated(campaign.questLog)
      }
    }
  }, [])

  // Listen for session state changes and sync campaign
  useEffect(() => {
    const handleStorageChange = () => {
      const campaign = campaignStorage.getCurrentCampaign()
      if (campaign) {
        const sessionState = sessionStorage.loadSession()
        if (sessionState) {
          campaignStorage.syncWithSessionState(sessionState)
          const syncedCampaign = campaignStorage.getCurrentCampaign()
          if (syncedCampaign) {
            setCurrentCampaign(syncedCampaign)
            if (onCampaignLoaded) {
              onCampaignLoaded(syncedCampaign)
            }
            if (onQuestLogUpdated) {
              onQuestLogUpdated(syncedCampaign.questLog)
            }
          }
        }
      }
    }

    // Listen for localStorage changes (session state updates)
    window.addEventListener('storage', handleStorageChange)
    
    // Also check periodically (for same-tab updates)
    const interval = setInterval(() => {
      handleStorageChange()
    }, 2000) // Check every 2 seconds

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      clearInterval(interval)
    }
  }, [onCampaignLoaded, onQuestLogUpdated])


  const handleLoadCampaignFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      // First, read the file to get the campaign data
      const fileText = await file.text()
      const campaignData = JSON.parse(fileText)

      // Get or determine the adventure ID from modular adventure or campaign data
      let targetAdventureId = campaignData.adventureId
      
      if (!targetAdventureId && modularAdventure?.loaded) {
        // Use current modular adventure if available
        targetAdventureId = modularAdventure.adventure_info?.id
      }
      
      if (!targetAdventureId) {
        alert('Campaign file must specify an adventureId, or a modular adventure must be loaded.')
        return
      }

      // Ensure campaign has proper structure
      const campaign: Campaign = {
        id: campaignData.id || `campaign-${Date.now()}`,
        adventureId: targetAdventureId,
        campaignName: campaignData.campaignName || 'Imported Campaign',
        sessionNumber: campaignData.sessionNumber || 1,
        dateStarted: campaignData.dateStarted || new Date().toISOString().split('T')[0],
        lastPlayed: new Date().toISOString(),
        currentLocation: campaignData.currentLocation,
        activeEncounter: campaignData.activeEncounter,
        party: campaignData.party || [],
        questLog: (campaignData.questLog || []).map((q: any, idx: number) => ({
          id: q.id || `quest-${Date.now()}-${idx}`,
          name: q.name,
          status: q.status || 'in_progress',
          description: q.description || '',
          notes: q.notes,
          timestamp: q.timestamp || new Date().toISOString(),
          updatedAt: q.updatedAt || new Date().toISOString(),
        })),
        worldState: campaignData.worldState || {},
        partyInventory: campaignData.partyInventory || {
          sharedItems: [],
        },
        notes: campaignData.notes || [],
        conversationHistory: campaignData.conversationHistory,
      }

      // Save campaign
      campaignStorage.saveCampaign(campaign)
      setCurrentCampaign(campaign)
      campaignStorage.setCurrentCampaign(campaign.id)
      
      if (onCampaignLoaded) {
        onCampaignLoaded(campaign)
      }
      if (onQuestLogUpdated) {
        onQuestLogUpdated(campaign.questLog)
      }
    } catch (error) {
      console.error('Failed to load campaign file:', error)
      alert('Failed to load campaign file. Please check the file format.')
    }
    
    if (campaignFileInputRef.current) {
      campaignFileInputRef.current.value = ''
    }
  }

  const handleCreateCampaign = () => {
    if (!modularAdventure?.loaded) {
      alert('Please load a modular adventure first.')
      return
    }
    
    const adventureName = modularAdventure.adventure_info?.name || 'Adventure'
    const campaignName = prompt('Campaign name:', `${adventureName} - Campaign 1`)
    if (!campaignName) return

    const adventureId = modularAdventure.adventure_info?.id || 'unknown'
    const campaign = campaignStorage.createCampaign(adventureId, campaignName)
    setCurrentCampaign(campaign)
    campaignStorage.setCurrentCampaign(campaign.id)
    
    if (onCampaignLoaded) {
      onCampaignLoaded(campaign)
    }
  }


  const handleCreateQuest = () => {
    if (!currentCampaign || !newQuestName.trim()) return

    const quest: QuestLogEntry = {
      id: `quest-${Date.now()}`,
      name: newQuestName.trim(),
      description: newQuestDescription.trim(),
      status: 'not_started',
      timestamp: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }

    campaignStorage.updateQuestLog(currentCampaign.id, quest)
    // Reload the campaign to get updated quest log
    const campaigns = campaignStorage.loadCampaigns()
    const updated = campaigns.find(c => c.id === currentCampaign.id)
    if (updated) {
      setCurrentCampaign(updated)
      if (onQuestLogUpdated) {
        onQuestLogUpdated(updated.questLog)
      }
    }

    setNewQuestName('')
    setNewQuestDescription('')
    setIsCreatingQuest(false)
  }

  const handleUpdateQuest = (quest: QuestLogEntry) => {
    if (!currentCampaign) return
    campaignStorage.updateQuestLog(currentCampaign.id, quest)
    // Reload the campaign to get updated quest log
    const campaigns = campaignStorage.loadCampaigns()
    const updated = campaigns.find(c => c.id === currentCampaign.id)
    if (updated) {
      setCurrentCampaign(updated)
      if (onQuestLogUpdated) {
        onQuestLogUpdated(updated.questLog)
      }
    }
  }

  // Generate summary from quest log
  const generateCampaignSummary = (campaign: Campaign | null): string => {
    if (!campaign) return 'No campaign loaded. Load or create a campaign to start playing.'

    const parts: string[] = []
    parts.push(`**Campaign:** ${campaign.campaignName}`)
    parts.push(`**Session:** ${campaign.sessionNumber}`)
    parts.push(`**Started:** ${new Date(campaign.dateStarted).toLocaleDateString()}`)
    if (campaign.currentLocation) {
      parts.push(`**Current Location:** ${campaign.currentLocation.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`)
    }
    parts.push('')
    parts.push(`**Quests:** ${campaign.questLog.length} total`)
    const activeQuests = campaign.questLog.filter(q => q.status === 'in_progress')
    if (activeQuests.length > 0) {
      parts.push(`- ${activeQuests.length} active`)
    }
    const completedQuests = campaign.questLog.filter(q => q.status === 'completed')
    if (completedQuests.length > 0) {
      parts.push(`- ${completedQuests.length} completed`)
    }

    return parts.join('\n')
  }

  return (
    <div className="bg-card border border-border p-3">
      <h2 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
        <BookOpen className="w-5 h-5" />
        Adventure & Campaign
      </h2>

      <div className="space-y-3">
        {/* Modular Adventure System (Backend) */}
        <div className="bg-background border border-primary/30 p-2 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[10px] font-semibold text-primary">Modular Adventures (Backend)</label>
            {modularError && (
              <span className="text-[9px] text-destructive">{modularError}</span>
            )}
          </div>
          
          {loadingAdventures ? (
            <div className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading adventures from backend...
            </div>
          ) : modularError ? (
            <div className="text-[10px] text-destructive p-2 bg-destructive/10 border border-destructive/30 rounded">
              <div className="font-semibold mb-1">Error loading adventures:</div>
              <div>{modularError}</div>
              <div className="mt-2 text-[9px] text-muted-foreground">
                Make sure the backend server is running on port 8000
              </div>
            </div>
          ) : availableAdventures.length > 0 ? (
            <div className="space-y-1">
              {availableAdventures.map((adv) => (
                <div
                  key={adv.id}
                  className="flex items-center justify-between p-1.5 bg-card border border-border rounded"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-semibold text-foreground truncate">
                      {adv.name}
                    </div>
                    <div className="text-[9px] text-muted-foreground">
                      Levels {adv.level_range[0]}-{adv.level_range[1]} • {adv.estimated_sessions || '?'} sessions
                    </div>
                  </div>
                  <Button
                    onClick={async () => {
                      try {
                        await loadModularAdventure(adv.id)
                        alert(`✅ Loaded ${adv.name}!\n\nThe adventure is now active on the backend. Start playing!`)
                      } catch (err) {
                        alert(`Failed to load adventure: ${err}`)
                      }
                    }}
                    disabled={loadingCurrent || (modularAdventure?.loaded && modularAdventure.adventure_info?.id === adv.id)}
                    className="px-2 py-1 text-[9px] bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors disabled:opacity-50"
                  >
                    {loadingCurrent ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : modularAdventure?.loaded && modularAdventure.adventure_info?.id === adv.id ? (
                      <span className="flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4" />
                        Loaded
                      </span>
                    ) : (
                      'Load'
                    )}
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[10px] text-muted-foreground text-center py-2">
              No modular adventures found in backend
            </div>
          )}
          
          {modularAdventure?.loaded && (
            <div className="mt-2 p-2 bg-primary/10 border border-primary/30 rounded">
              <div className="text-[9px] font-semibold text-primary mb-1">
                ✓ Active: {modularAdventure.adventure_info?.name}
              </div>
              {modularAdventure.metadata?.current_state && (
                <div className="text-[9px] text-muted-foreground">
                  Chapter: {modularAdventure.metadata.current_state.chapter?.replace('part', 'Part ') || 'Unknown'}<br />
                  Location: {modularAdventure.metadata.current_state.location?.replace(/_/g, ' ') || 'Unknown'}<br />
                  Level: {modularAdventure.metadata.current_state.party_level || 1}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Campaign Section */}
        {modularAdventure?.loaded && (
          <div className="bg-background border border-border p-2 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-semibold text-muted-foreground">Campaign (Save State)</label>
              <div className="flex gap-1">
                <input
                  ref={campaignFileInputRef}
                  type="file"
                  accept=".json,application/json,text/json"
                  onChange={handleLoadCampaignFile}
                  className="hidden"
                />
                <Button
                  onClick={() => campaignFileInputRef.current?.click()}
                  className="px-2 py-1 text-xs bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1"
                  title="Load Campaign (auto-loads associated adventure if different)"
                >
                  <FolderOpen className="w-5 h-5" />
                  Load Campaign
                </Button>
                {!currentCampaign && (
                  <Button
                    onClick={handleCreateCampaign}
                    className="px-2 py-1 text-xs bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1"
                  >
                    <Plus className="w-5 h-5" />
                    New Campaign
                  </Button>
                )}
                {currentCampaign && (
                  <>
                    <Button
                      onClick={() => {
                        if (confirm(`Start a new session? This will increment the session number from ${currentCampaign.sessionNumber} to ${currentCampaign.sessionNumber + 1}.`)) {
                          const updated = campaignStorage.startNewSession()
                          if (updated) {
                            setCurrentCampaign(updated)
                            // Also update session state
                            const sessionState = sessionStorage.loadSession()
                            if (sessionState) {
                              sessionStorage.saveSession({
                                ...sessionState,
                                session_number: updated.sessionNumber,
                              })
                            }
                            if (onCampaignLoaded) {
                              onCampaignLoaded(updated)
                            }
                          }
                        }
                      }}
                      className="px-2 py-1 text-xs bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1"
                      title="Start a new session (increments session number)"
                    >
                      <Plus className="w-5 h-5" />
                      New Session
                    </Button>
                    <Button
                      onClick={() => {
                        if (currentCampaign) campaignStorage.exportToFile(currentCampaign)
                      }}
                      className="px-2 py-1 text-xs bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors flex items-center gap-1"
                      title="Export Campaign"
                    >
                      <FileDown className="w-5 h-5" />
                    </Button>
                    <Button
                      onClick={() => {
                        if (confirm('Clear current campaign? (Not deleted, can be reloaded)')) {
                          setCurrentCampaign(null)
                          campaignStorage.setCurrentCampaign(null)
                          if (onCampaignLoaded) {
                            onCampaignLoaded(null as any)
                          }
                        }
                      }}
                      className="px-2 py-1 text-xs bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors flex items-center gap-1"
                      title="Clear Campaign"
                    >
                      <X className="w-5 h-5" />
                    </Button>
                  </>
                )}
              </div>
            </div>

            {currentCampaign ? (
              <>
                <Input
                  value={currentCampaign.campaignName}
                  onChange={(e) => {
                    const updated = { ...currentCampaign, campaignName: e.target.value }
                    campaignStorage.saveCampaign(updated)
                    setCurrentCampaign(updated)
                  }}
                  className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none"
                  placeholder="Campaign name..."
                />

                {/* Campaign Summary */}
                <div className="bg-card border border-border p-2">
                  <div className="flex items-center gap-1.5 mb-1">
                    <FileText className="w-5 h-5 text-muted-foreground" />
                    <h4 className="text-xs font-semibold text-foreground">Summary</h4>
                  </div>
                  <div className="text-[10px] text-muted-foreground whitespace-pre-wrap leading-relaxed">
                    {generateCampaignSummary(currentCampaign)}
                  </div>
                </div>

                {/* Quest Log */}
                <div className="bg-card border border-border p-2">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5">
                      <History className="w-5 h-5 text-muted-foreground" />
                      <h4 className="text-xs font-semibold text-foreground">Quest Log</h4>
                      <span className="text-[9px] text-muted-foreground">({currentCampaign.questLog.length})</span>
                    </div>
                    <Button
                      onClick={() => setIsCreatingQuest(true)}
                      className="px-2 py-1 text-xs bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1"
                    >
                      <Plus className="w-5 h-5" />
                      Entry
                    </Button>
                  </div>

                  {isCreatingQuest && (
                    <div className="bg-background border border-primary/30 p-2 space-y-2 mb-2">
                      <Input
                        value={newQuestName}
                        onChange={(e) => setNewQuestName(e.target.value)}
                        placeholder="Quest name..."
                        className="w-full px-2 py-1 text-[10px] bg-background text-foreground border border-border focus:border-primary focus:outline-none"
                      />
                      <Input
                        value={newQuestDescription}
                        onChange={(e) => setNewQuestDescription(e.target.value)}
                        placeholder="Quest description..."
                        className="w-full px-2 py-1 text-[10px] bg-background text-foreground border border-border focus:border-primary focus:outline-none"
                      />
                      <div className="flex gap-1">
                        <Button
                          onClick={handleCreateQuest}
                          disabled={!newQuestName.trim()}
                          className="px-1.5 py-0.5 text-[9px] bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors disabled:opacity-50"
                        >
                          Create
                        </Button>
                        <Button
                          onClick={() => {
                            setIsCreatingQuest(false)
                            setNewQuestName('')
                            setNewQuestDescription('')
                          }}
                          className="px-1.5 py-0.5 text-[9px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}

                  <div className="space-y-1 max-h-[300px] overflow-y-auto">
                    {currentCampaign.questLog.length === 0 ? (
                      <div className="text-[10px] text-muted-foreground text-center py-2">
                        No quests. Add a quest to track progress.
                      </div>
                    ) : (
                      currentCampaign.questLog.map((quest) => {
                        const isExpanded = expandedQuests.has(quest.id)
                        const isEditingNote = editingQuestNotes.has(quest.id)
                        const noteValue = quest.notes || ''

                        return (
                          <div
                            key={quest.id}
                            className="border-l-2 border-l-border pl-2 py-1"
                          >
                            <div
                              className="flex items-start gap-1.5 cursor-pointer hover:bg-card/50 transition-colors p-1 rounded"
                              onClick={() => {
                                const newExpanded = new Set(expandedQuests)
                                if (isExpanded) {
                                  newExpanded.delete(quest.id)
                                } else {
                                  newExpanded.add(quest.id)
                                }
                                setExpandedQuests(newExpanded)
                              }}
                            >
                              {isExpanded ? (
                                <ChevronDown className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                              ) : (
                                <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className={`text-[9px] px-1 py-0.5 rounded border ${
                                    quest.status === 'completed' ? 'bg-green-500/20 text-green-600 border-green-500/30' :
                                    quest.status === 'in_progress' ? 'bg-primary/20 text-primary border-primary/30' :
                                    quest.status === 'failed' ? 'bg-destructive/20 text-destructive border-destructive/30' :
                                    'bg-muted text-muted-foreground border-border'
                                  }`}>
                                    {quest.status.replace('_', ' ').toUpperCase()}
                                  </span>
                                  <span className="text-[10px] font-semibold text-foreground">
                                    {quest.name}
                                  </span>
                                </div>
                                {quest.description && !isExpanded && (
                                  <div className="text-[9px] text-muted-foreground mt-0.5 line-clamp-1">
                                    {quest.description}
                                  </div>
                                )}
                              </div>
                              <div className="relative">
                                <button
                                  ref={(el) => {
                                    if (el) {
                                      statusDropdownRefs.current.set(quest.id, el)
                                    } else {
                                      statusDropdownRefs.current.delete(quest.id)
                                    }
                                  }}
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    if (openStatusDropdown === quest.id) {
                                      setOpenStatusDropdown(null)
                                      setDropdownPosition(null)
                                    } else {
                                      setOpenStatusDropdown(quest.id)
                                    }
                                  }}
                                  className="retro text-[9px] px-1 py-0.5 bg-background text-foreground border border-border hover:bg-primary/10 hover:border-primary focus:outline-none flex items-center gap-1 whitespace-nowrap"
                                  style={{ fontFamily: "'Press Start 2P', monospace" }}
                                >
                                  {quest.status.replace('_', ' ').toUpperCase()}
                                  <ChevronDown className="w-3 h-3" />
                                </button>
                                {openStatusDropdown === quest.id && dropdownPosition && (
                                  <div 
                                    data-status-dropdown={quest.id}
                                    className="fixed bg-background border border-border z-[9999] min-w-[120px] retro text-[9px]"
                                    style={{ 
                                      fontFamily: "'Press Start 2P', monospace",
                                      top: `${dropdownPosition.top}px`,
                                      left: `${dropdownPosition.left}px`
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    {(['not_started', 'in_progress', 'completed', 'failed'] as const).map((status) => (
                                      <button
                                        key={status}
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          handleUpdateQuest({ ...quest, status, updatedAt: new Date().toISOString() })
                                          setOpenStatusDropdown(null)
                                          setDropdownPosition(null)
                                        }}
                                        className={`w-full text-left px-2 py-1 hover:bg-primary/20 hover:text-primary flex items-center gap-1.5 whitespace-nowrap ${
                                          quest.status === status ? 'bg-primary/30 text-primary' : 'text-foreground'
                                        }`}
                                      >
                                        {quest.status === status && <Check className="w-3 h-3 flex-shrink-0" />}
                                        <span>{status.replace('_', ' ').toUpperCase()}</span>
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                            {isExpanded && (
                              <div className="ml-4 mt-1 space-y-2 p-2 bg-card/30 border border-border rounded">
                                <div>
                                  <div className="text-[9px] font-semibold text-muted-foreground mb-1">
                                    Description:
                                  </div>
                                  <textarea
                                    value={quest.description}
                                    onChange={(e) => {
                                      handleUpdateQuest({ ...quest, description: e.target.value, updatedAt: new Date().toISOString() })
                                    }}
                                    className="w-full px-2 py-1 text-[10px] bg-background text-foreground border border-border focus:border-primary focus:outline-none resize-none"
                                    rows={2}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                </div>
                                <div>
                                  <div className="flex items-center justify-between mb-1">
                                    <div className="text-[9px] font-semibold text-muted-foreground">
                                      DM Notes:
                                    </div>
                                    {!isEditingNote && (
                                      <Button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          setEditingQuestNotes(new Set([...editingQuestNotes, quest.id]))
                                        }}
                                        className="px-1 py-0.5 text-[8px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors"
                                      >
                                        {noteValue ? 'Edit' : 'Add Note'}
                                      </Button>
                                    )}
                                  </div>
                                  {isEditingNote ? (
                                    <div className="space-y-1">
                                      <textarea
                                        value={noteValue}
                                        onChange={(e) => {
                                          handleUpdateQuest({ ...quest, notes: e.target.value, updatedAt: new Date().toISOString() })
                                        }}
                                        placeholder="Add notes for this quest..."
                                        className="w-full px-2 py-1 text-[10px] bg-background text-foreground border border-border focus:border-primary focus:outline-none resize-none"
                                        rows={3}
                                        onClick={(e) => e.stopPropagation()}
                                      />
                                      <div className="flex gap-1">
                                        <Button
                                          onClick={(e) => {
                                            e.stopPropagation()
                                            setEditingQuestNotes(new Set([...editingQuestNotes].filter(id => id !== quest.id)))
                                          }}
                                          className="px-1.5 py-0.5 text-[9px] bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors"
                                        >
                                          Done
                                        </Button>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="text-[10px] text-muted-foreground whitespace-pre-wrap leading-relaxed min-h-[1rem]">
                                      {noteValue || <span className="italic">No notes</span>}
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-[10px] text-muted-foreground text-center py-4 border border-dashed border-border rounded">
                No campaign loaded. Create a new campaign or load an existing one to start playing.
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
