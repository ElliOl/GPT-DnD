import { Dice6 } from 'lucide-react'

export function Header() {
  return (
    <header className="text-center py-3 border-b border-border mb-3">
      <div className="flex items-center justify-center gap-2">
        <Dice6 className="w-4 h-4 text-primary" />
        <h1 className="text-sm font-medium text-foreground">
          AI Dungeon Master
        </h1>
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        AI-powered D&D with voice narration and strict 5e rules
      </p>
    </header>
  )
}

