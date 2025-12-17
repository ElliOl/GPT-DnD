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
  onReplayAudio?: (message: Message) => void
}

export function Conversation({ 
  messages, 
  loading, 
  currentAdventure,
  onArchiveChat,
  onReplayAudio,
}: ConversationProps) {
  
  const handleAudioClick = (message: Message) => {
    if (message.audio) {
      // Play cached audio
      const audio = new Audio(message.audio)
      audio.play().catch((err) => {
        console.error('Audio playback failed:', err)
        // If playback fails, try to regenerate
        if (onReplayAudio) {
          onReplayAudio(message)
        }
      })
    } else if (onReplayAudio) {
      // Generate audio if it doesn't exist
      onReplayAudio(message)
    }
  }

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
          className={`flex items-start gap-1.5 ${
            msg.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          {/* Audio button for assistant messages */}
          {msg.role === 'assistant' && (
            <Button
              onClick={() => handleAudioClick(msg)}
              className="flex-shrink-0 w-5 h-5 p-0 bg-transparent text-foreground hover:text-primary transition-colors flex items-center justify-center"
              title="Play audio"
            >
              <AudioWaveform className="w-4 h-4" />
            </Button>
          )}
          
          <div
            className={`max-w-[85%] px-2 py-1.5 ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : msg.role === 'system'
                ? 'bg-destructive text-destructive-foreground'
                : 'bg-card text-foreground'
            }`}
          >
            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
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

