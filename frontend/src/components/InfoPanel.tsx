import { Info, MessageSquare, Dice6, AudioWaveform } from 'lucide-react'

export function InfoPanel() {
  return (
    <div className="bg-card border border-border p-3">
      <h2 className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
        <Info className="w-5 h-5" />
        Info
      </h2>
      <div className="space-y-1.5 text-[10px] text-muted-foreground">
        <p className="flex items-center gap-1.5">
          <MessageSquare className="w-5 h-5" />
          Type your action in the chat
        </p>
        <p className="flex items-center gap-1.5">
          <Dice6 className="w-5 h-5" />
          DM will call for rolls when needed
        </p>
        <p className="flex items-center gap-1.5">
          <AudioWaveform className="w-5 h-5" />
          Toggle voice narration on/off
        </p>
        <p className="flex items-center gap-1.5">
          <Info className="w-5 h-5" />
          Character stats update in real-time
        </p>
      </div>
    </div>
  )
}

