import { Conversation } from './Conversation'
import { ChatInput } from './ChatInput'
import type { SpeechRecognition } from '../types/speech-recognition'
import type { Adventure } from '../services/adventureStorage'

interface Message {
  role: string
  content: string
  audio?: string
}

interface ChatPanelProps {
  messages: Message[]
  loading: boolean
  message: string
  setMessage: (value: string) => void
  onSend: () => void
  voiceEnabled: boolean
  setVoiceEnabled: (enabled: boolean) => void
  isListening: boolean
  toggleListening: () => void
  currentAudio: HTMLAudioElement | null
  stopAudio: () => void
  currentAdventure?: Adventure | null
  onArchiveChat?: () => void
  onReplayAudio?: (message: Message) => void
}

export function ChatPanel({
  messages,
  loading,
  message,
  setMessage,
  onSend,
  voiceEnabled,
  setVoiceEnabled,
  isListening,
  toggleListening,
  currentAudio,
  stopAudio,
  currentAdventure,
  onArchiveChat,
  onReplayAudio,
}: ChatPanelProps) {
  return (
    <div className="lg:col-span-2">
      <div className="bg-card border border-border">
        <Conversation 
          messages={messages} 
          loading={loading}
          currentAdventure={currentAdventure}
          onArchiveChat={onArchiveChat}
          onReplayAudio={onReplayAudio}
        />
        <ChatInput
          message={message}
          setMessage={setMessage}
          onSend={onSend}
          loading={loading}
          voiceEnabled={voiceEnabled}
          setVoiceEnabled={setVoiceEnabled}
          isListening={isListening}
          toggleListening={toggleListening}
          currentAudio={currentAudio}
          stopAudio={stopAudio}
        />
      </div>
    </div>
  )
}

