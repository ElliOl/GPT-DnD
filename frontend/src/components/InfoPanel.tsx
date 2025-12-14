import { Info, MessageSquare, Dice6, Volume2 } from 'lucide-react'

export function InfoPanel() {
  return (
    <div className="bg-card border border-border p-3">
      <h2 className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
        <Info className="w-3 h-3" />
        Info
      </h2>
      <div className="space-y-1.5 text-[10px] text-muted-foreground">
        <p className="flex items-center gap-1.5">
          <MessageSquare className="w-3 h-3" />
          Type your action in the chat
        </p>
        <p className="flex items-center gap-1.5">
          <Dice6 className="w-3 h-3" />
          DM will call for rolls when needed
        </p>
        <p className="flex items-center gap-1.5">
          <Volume2 className="w-3 h-3" />
          Toggle voice narration on/off
        </p>
        <p className="flex items-center gap-1.5">
          <Info className="w-3 h-3" />
          Character stats update in real-time
        </p>
      </div>
    </div>
  )
}

