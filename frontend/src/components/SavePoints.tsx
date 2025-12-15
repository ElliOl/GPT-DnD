import { RotateCcw } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import type { Adventure } from '../services/adventureStorage'

interface SavePointsProps {
  currentAdventure?: Adventure | null
  onLoadSavePoint?: (savePointId: string) => void
}

export function SavePoints({ currentAdventure, onLoadSavePoint }: SavePointsProps) {
  const savePoints = currentAdventure?.history || []

  if (savePoints.length === 0) {
    return null
  }

  return (
    <div className="bg-card border border-border p-2">
      <div className="space-y-1.5">
        <div className="text-[10px] text-muted-foreground font-semibold">Save Points</div>
        <div className="space-y-1 max-h-[200px] overflow-y-auto">
          {savePoints.map((savePoint) => (
            <div
              key={savePoint.id}
              className="flex items-center justify-between gap-2 bg-background border border-border p-1.5"
            >
              <span className="text-[10px] text-foreground truncate flex-1">
                {savePoint.description}
              </span>
              {onLoadSavePoint && (
                <Button
                  onClick={() => onLoadSavePoint(savePoint.id)}
                  className="px-1.5 py-0.5 text-[9px] bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1 whitespace-nowrap flex-shrink-0"
                >
                  <RotateCcw className="w-4 h-4" />
                  Load
                </Button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
