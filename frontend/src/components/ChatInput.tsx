import { Mic, MicOff, Send, Volume2, Square } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import { Input } from '@base-ui/react/input'
import type { SpeechRecognition } from '../types/speech-recognition'

interface ChatInputProps {
  message: string
  setMessage: (value: string) => void
  onSend: () => void
  loading: boolean
  voiceEnabled: boolean
  setVoiceEnabled: (enabled: boolean) => void
  isListening: boolean
  toggleListening: () => void
  currentAudio: HTMLAudioElement | null
  stopAudio: () => void
}

export function ChatInput({
  message,
  setMessage,
  onSend,
  loading,
  voiceEnabled,
  setVoiceEnabled,
  isListening,
  toggleListening,
  currentAudio,
  stopAudio,
}: ChatInputProps) {
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="border-t border-border p-2">
      <div className="flex gap-1.5">
        <Input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Describe your action..."
          className="flex-1 bg-background text-foreground px-2 py-1.5 resize-none border border-border focus:border-primary focus:outline-none text-xs placeholder:text-muted-foreground"
          disabled={loading}
          render={(props) => (
            <textarea
              {...props}
              rows={2}
              onKeyPress={handleKeyPress}
            />
          )}
        />
        <Button
          onClick={toggleListening}
          className={`w-[52px] h-[52px] flex items-center justify-center border transition-colors ${
            isListening
              ? 'bg-destructive border-destructive text-destructive-foreground'
              : 'bg-card border-border text-foreground hover:bg-accent'
          }`}
          title="Voice input"
        >
          {isListening ? (
            <MicOff className="w-4 h-4" />
          ) : (
            <Mic className="w-4 h-4" />
          )}
        </Button>
        <Button
          onClick={() => setVoiceEnabled(!voiceEnabled)}
          className={`w-[52px] h-[52px] flex items-center justify-center border transition-colors ${
            voiceEnabled
              ? 'bg-primary border-primary text-primary-foreground'
              : 'bg-card border-border text-foreground hover:bg-accent'
          }`}
          title="Voice narration"
        >
          <Volume2 className="w-4 h-4" />
        </Button>
        <Button
          onClick={onSend}
          disabled={loading || !message.trim()}
          className="w-[52px] h-[52px] flex items-center justify-center bg-primary border-primary text-primary-foreground hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>

      {currentAudio && (
        <div className="flex gap-3 mt-1.5 items-center">
          <Button
            onClick={stopAudio}
            className="flex items-center gap-1 text-[10px] text-destructive hover:text-destructive/80 transition-colors bg-transparent border-0 p-0"
          >
            <Square className="w-3 h-3" />
            Stop audio
          </Button>
        </div>
      )}
    </div>
  )
}

