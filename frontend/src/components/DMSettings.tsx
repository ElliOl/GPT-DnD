import { Settings, Save, Trash2, RotateCcw, Archive, ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { chatArchive, type ArchivedChat } from '../services/chatArchive'
import { Button } from '@base-ui/react/button'

interface DMSettingsProps {
  onRestoreChat?: (messages: Array<{ role: string; content: string }>) => void
}

export function DMSettings({ onRestoreChat }: DMSettingsProps) {
  const [additionalRulesContent, setAdditionalRulesContent] = useState('')
  const [additionalRulesLoading, setAdditionalRulesLoading] = useState(true)
  const [additionalRulesSaving, setAdditionalRulesSaving] = useState(false)
  const [additionalRulesSaveStatus, setAdditionalRulesSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [archivedChats, setArchivedChats] = useState<ArchivedChat[]>([])
  const [archivedChatsExpanded, setArchivedChatsExpanded] = useState(true)
  const [expandedArchives, setExpandedArchives] = useState<Set<string>>(new Set())
  const [additionalRulesExpanded, setAdditionalRulesExpanded] = useState(false)

  // Load additional rules and archived chats on mount
  useEffect(() => {
    loadAdditionalRules()
    loadArchivedChats()
  }, [])

  const loadArchivedChats = () => {
    const archives = chatArchive.getAllArchives()
    // Sort by timestamp, newest first
    setArchivedChats(archives.sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    ))
  }

  const handleDeleteArchive = (archiveId: string) => {
    if (confirm('Are you sure you want to permanently delete this archived chat?')) {
      chatArchive.deleteArchive(archiveId)
      loadArchivedChats()
    }
  }

  const handleRestoreArchive = (archiveId: string) => {
    const messages = chatArchive.restoreArchive(archiveId)
    if (messages && onRestoreChat) {
      onRestoreChat(messages)
    }
  }

  const loadAdditionalRules = async () => {
    try {
      setAdditionalRulesLoading(true)
      setAdditionalRulesSaveStatus('idle')
      const data = await api.getAdditionalRules()
      setAdditionalRulesContent(data.content)
    } catch (error) {
      console.error('Error loading additional rules:', error)
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      setAdditionalRulesSaveStatus('error')
      setAdditionalRulesContent(`Error loading additional rules: ${errorMessage}`)
    } finally {
      setAdditionalRulesLoading(false)
    }
  }

  const handleSaveAdditionalRules = async () => {
    try {
      setAdditionalRulesSaving(true)
      setAdditionalRulesSaveStatus('idle')
      const result = await api.saveAdditionalRules(additionalRulesContent)
      setAdditionalRulesSaveStatus('success')
      setTimeout(() => setAdditionalRulesSaveStatus('idle'), 3000)
    } catch (error) {
      console.error('Error saving additional rules:', error)
      setAdditionalRulesSaveStatus('error')
      setTimeout(() => setAdditionalRulesSaveStatus('idle'), 5000)
    } finally {
      setAdditionalRulesSaving(false)
    }
  }

  return (
    <div className="bg-card border border-border p-3">
      <h2 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
        <Settings className="w-5 h-5" />
        DM Settings
      </h2>

      <div className="space-y-3">
        {/* Additional Rules Accordion - Add to existing D&D rules */}
        <div className="bg-background border border-border">
          <div
            className="flex items-center justify-between p-2 cursor-pointer hover:bg-card/50 transition-colors"
            onClick={() => setAdditionalRulesExpanded(!additionalRulesExpanded)}
          >
            <div className="flex items-center gap-1.5">
              {additionalRulesExpanded ? (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-5 h-5 text-muted-foreground" />
              )}
              <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                <Plus className="w-5 h-5" />
                Additional Rules (adds to core D&D rules)
              </label>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleSaveAdditionalRules()
              }}
              disabled={additionalRulesSaving || additionalRulesLoading}
              className="text-xs px-2 py-1 rounded border border-border hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <Save className="w-5 h-5" />
              {additionalRulesSaving ? 'Saving...' : 'Save'}
            </button>
          </div>
          
          {additionalRulesExpanded && (
            <div className="border-t border-border p-2 space-y-2">
              {additionalRulesSaveStatus === 'success' && (
                <div className="text-xs text-green-500">✅ Additional rules saved successfully!</div>
              )}
              {additionalRulesSaveStatus === 'error' && (
                <div className="text-xs text-red-500">❌ Error saving additional rules. Check console for details.</div>
              )}

              {additionalRulesLoading ? (
                <div className="text-xs text-muted-foreground">Loading additional rules...</div>
              ) : (
                <textarea
                  value={additionalRulesContent}
                  onChange={(e) => setAdditionalRulesContent(e.target.value)}
                  className="w-full h-96 p-2 text-xs font-mono bg-background border border-border rounded resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Add your custom rules here. These will be appended to the core D&D 5e rules that the AI already knows..."
                  spellCheck={false}
                />
              )}
              
              <p className="text-xs text-muted-foreground">
                Add custom rules, house rules, or homebrew mechanics here. These are automatically added to the core D&D 5e rules (ability checks, combat, etc.) that the AI already uses. The AI will read both the core rules and your additions.
              </p>
            </div>
          )}
        </div>

        {/* Archived Chats Section Accordion */}
        <div className="bg-background border border-border">
          <div
            className="flex items-center justify-between p-2 cursor-pointer hover:bg-card/50 transition-colors"
            onClick={() => setArchivedChatsExpanded(!archivedChatsExpanded)}
          >
            <div className="flex items-center gap-1.5">
              {archivedChatsExpanded ? (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-5 h-5 text-muted-foreground" />
              )}
              <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                <Archive className="w-5 h-5" />
                Archived Chats
                {archivedChats.length > 0 && (
                  <span className="text-[10px] text-muted-foreground">
                    ({archivedChats.length})
                  </span>
                )}
              </label>
            </div>
            {archivedChats.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm('Delete all archived chats? This cannot be undone.')) {
                    chatArchive.clearAllArchives()
                    loadArchivedChats()
                  }
                }}
                className="text-xs px-2 py-1 rounded border border-destructive text-destructive hover:bg-destructive/10 disabled:opacity-50"
              >
                Clear All
              </button>
            )}
          </div>

          {archivedChatsExpanded && (
            <div className="border-t border-border p-2">
              {archivedChats.length === 0 ? (
                <div className="text-xs text-muted-foreground p-4 border border-border rounded text-center">
                  No archived chats. Archive chats from the Game tab to view them here.
                </div>
              ) : (
                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                  {archivedChats.map((archive) => {
                    const isExpanded = expandedArchives.has(archive.id)
                    
                    return (
                      <div
                        key={archive.id}
                        className="bg-background border border-border rounded"
                      >
                        <div
                          className="flex items-start justify-between gap-2 p-2 cursor-pointer hover:bg-card/50 transition-colors"
                          onClick={() => {
                            const newExpanded = new Set(expandedArchives)
                            if (isExpanded) {
                              newExpanded.delete(archive.id)
                            } else {
                              newExpanded.add(archive.id)
                            }
                            setExpandedArchives(newExpanded)
                          }}
                        >
                          <div className="flex items-start gap-1.5 flex-1 min-w-0">
                            {isExpanded ? (
                              <ChevronDown className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                            ) : (
                              <ChevronRight className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="text-xs font-semibold text-foreground">
                                {archive.adventureName || 'Unknown Adventure'}
                              </div>
                              {archive.savePointDescription && (
                                <div className="text-[10px] text-muted-foreground mt-0.5">
                                  Save Point: {archive.savePointDescription}
                                </div>
                              )}
                              <div className="text-[9px] text-muted-foreground mt-0.5">
                                {new Date(archive.timestamp).toLocaleString()} • {archive.messages.length} messages
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                            {onRestoreChat && (
                              <Button
                                onClick={() => handleRestoreArchive(archive.id)}
                                className="px-2 py-1 text-[10px] bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1"
                              >
                                <RotateCcw className="w-5 h-5" />
                                Restore
                              </Button>
                            )}
                            <Button
                              onClick={() => handleDeleteArchive(archive.id)}
                              className="px-2 py-1 text-[10px] bg-destructive border border-destructive text-destructive-foreground hover:bg-destructive/80 transition-colors flex items-center gap-1"
                            >
                              <Trash2 className="w-5 h-5" />
                              Delete
                            </Button>
                          </div>
                        </div>
                        {isExpanded && archive.messages.length > 0 && (
                          <div className="border-t border-border p-2 space-y-2 bg-card/30 max-h-[300px] overflow-y-auto">
                            <div className="text-[9px] font-semibold text-muted-foreground mb-1">
                              Chat Messages ({archive.messages.length}):
                            </div>
                            {archive.messages.map((msg, idx) => (
                              <div
                                key={idx}
                                className="bg-background border border-border p-2 rounded"
                              >
                                <div className="flex items-center gap-2 mb-1">
                                  <span className={`text-[9px] font-semibold ${
                                    msg.role === 'user' 
                                      ? 'text-primary' 
                                      : msg.role === 'system'
                                      ? 'text-destructive'
                                      : 'text-muted-foreground'
                                  }`}>
                                    {msg.role === 'user' ? 'Player' : msg.role === 'assistant' ? 'DM' : 'System'}
                                  </span>
                                  {msg.timestamp && (
                                    <span className="text-[8px] text-muted-foreground">
                                      {new Date(msg.timestamp).toLocaleString()}
                                    </span>
                                  )}
                                </div>
                                <div className="text-[10px] text-foreground whitespace-pre-wrap leading-relaxed">
                                  {msg.content}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
