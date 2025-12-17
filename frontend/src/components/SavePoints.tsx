import { useState } from 'react'
import { RotateCcw, Save, Edit2, Check, X, Trash2 } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import type { Adventure } from '../services/adventureStorage'
import { adventureStorage } from '../services/adventureStorage'

interface SavePointsProps {
  currentAdventure?: Adventure | null
  onLoadSavePoint?: (savePointId: string) => void
  onCreateSavePoint?: () => void
  onAdventureUpdate?: (adventure: Adventure | null) => void
}

export function SavePoints({ currentAdventure, onLoadSavePoint, onCreateSavePoint, onAdventureUpdate }: SavePointsProps) {
  const savePoints = currentAdventure?.history || []
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState<string>('')

  return (
    <div className="bg-card border border-border p-2">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="text-[10px] text-muted-foreground font-semibold">Save Points</div>
          {onCreateSavePoint && (
            <Button
              onClick={onCreateSavePoint}
              className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors border-0 bg-transparent"
              title="Save current game state"
            >
              <Save className="w-4 h-4" />
            </Button>
          )}
        </div>
        {savePoints.length === 0 ? (
          <div className="text-[10px] text-muted-foreground text-center py-2">
            No save points yet. Click Save to create one.
          </div>
        ) : (
          <div className="space-y-1 max-h-[200px] overflow-y-auto">
            {savePoints.map((savePoint) => {
              const isEditing = editingId === savePoint.id
              
              const handleStartEdit = () => {
                setEditingId(savePoint.id)
                setEditValue(savePoint.description)
              }
              
              const handleSaveEdit = () => {
                if (currentAdventure && editValue.trim()) {
                  adventureStorage.updateSavePointDescription(
                    currentAdventure.id,
                    savePoint.id,
                    editValue.trim()
                  )
                  const updated = adventureStorage.getCurrentAdventure()
                  if (updated) {
                    onAdventureUpdate?.(updated)
                  }
                }
                setEditingId(null)
                setEditValue('')
              }
              
              const handleCancelEdit = () => {
                setEditingId(null)
                setEditValue('')
              }
              
              const handleDelete = () => {
                if (currentAdventure && confirm(`Are you sure you want to delete "${savePoint.description}"?`)) {
                  adventureStorage.deleteSavePoint(currentAdventure.id, savePoint.id)
                  const updated = adventureStorage.getCurrentAdventure()
                  if (updated) {
                    onAdventureUpdate?.(updated)
                  }
                }
              }
              
              return (
                <div
                  key={savePoint.id}
                  className="flex items-center justify-between gap-2 bg-background border border-border p-1.5"
                >
                  {isEditing ? (
                    <>
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit()
                          if (e.key === 'Escape') handleCancelEdit()
                        }}
                        className="flex-1 text-[10px] px-1 py-0.5 bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                        autoFocus
                      />
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Button
                          onClick={handleSaveEdit}
                          className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors border-0 bg-transparent"
                          title="Save"
                        >
                          <Check className="w-3 h-3" />
                        </Button>
                        <Button
                          onClick={handleCancelEdit}
                          className="p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors border-0 bg-transparent"
                          title="Cancel"
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                    </>
                  ) : (
                    <>
                      <span 
                        className="text-[10px] text-foreground truncate flex-1 cursor-pointer hover:text-primary"
                        onClick={handleStartEdit}
                        title="Click to edit"
                      >
                        {savePoint.description}
                      </span>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Button
                          onClick={handleStartEdit}
                          className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors border-0 bg-transparent"
                          title="Edit name"
                        >
                          <Edit2 className="w-3 h-3" />
                        </Button>
                        <Button
                          onClick={handleDelete}
                          className="p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors border-0 bg-transparent"
                          title="Delete save point"
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                        {onLoadSavePoint && (
                          <Button
                            onClick={() => onLoadSavePoint(savePoint.id)}
                            className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors border-0 bg-transparent"
                            title="Load save point"
                          >
                            <RotateCcw className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
