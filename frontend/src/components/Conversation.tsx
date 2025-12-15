import { AudioWaveform, Archive } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import type { Adventure } from '../services/adventureStorage'

interface Message {
  role: string
  content: string
  audio?: string
}

interface ConversationProps {
  messages: Message[]
  loading: boolean
  currentAdventure?: Adventure | null
  onArchiveChat?: () => void
}

export function Conversation({ 
  messages, 
  loading, 
  currentAdventure,
  onArchiveChat,
}: ConversationProps) {

  return (
    <div className="h-[500px] overflow-y-auto p-3 space-y-2 text-xs">
      {/* Archive button */}
      {messages.length > 0 && onArchiveChat && (
        <div className="flex justify-end mb-2">
          <Button
            onClick={onArchiveChat}
            className="px-2 py-1 text-[10px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors flex items-center gap-1"
          >
            <Archive className="w-5 h-5" />
            Archive Chat
          </Button>
        </div>
      )}

      {messages.length === 0 && (
        <div className="text-center text-muted-foreground mt-10">
          <p className="text-xs">The Dungeon Master awaits...</p>
          <p className="text-[10px] mt-1">
            {currentAdventure 
              ? `Adventure: ${currentAdventure.name}`
              : 'Select an adventure in the Adventure tab to begin'}
          </p>
          {!currentAdventure && (
            <p className="text-[10px] mt-1">
              Describe your action and the DM will respond
            </p>
          )}
        </div>
      )}

      {messages.map((msg, idx) => (
        <div
          key={idx}
          className={`flex ${
            msg.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className={`max-w-[85%] px-2 py-1.5 ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : msg.role === 'system'
                ? 'bg-destructive text-destructive-foreground'
                : 'bg-card text-foreground border border-border'
            }`}
          >
            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            {msg.audio && (
              <Button
                onClick={() => {
                  const audio = new Audio(msg.audio)
                  audio.play()
                }}
                className="mt-1.5 flex items-center gap-1 text-[10px] text-primary hover:text-primary-hover transition-colors bg-transparent border-0 p-0"
              >
                <AudioWaveform className="w-5 h-5" />
                Play audio
              </Button>
            )}
          </div>
        </div>
      ))}

      {loading && (
        <div className="flex justify-start">
          <div className="bg-card text-muted-foreground px-2 py-1.5 border border-border">
            <p className="text-xs animate-pulse">The DM ponders...</p>
          </div>
        </div>
      )}

    </div>
  )
}

