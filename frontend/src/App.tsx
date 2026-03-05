import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { ChatPanel } from './components/ChatPanel'
import { CharacterPanel } from './components/CharacterPanel'
import { DieRoller } from './components/DieRoller'
import { SavePoints } from './components/SavePoints'
import { Players } from './components/Players'
import { DMSettings } from './components/DMSettings'
import { AdventureSetup } from './components/AdventureSetup'
import { TabNavigation } from './components/TabNavigation'
import { useSpeechRecognition } from './hooks/useSpeechRecognition'
import { useConversation } from './hooks/useConversation'
import { useAdventure } from './hooks/useAdventure'
import { useCharacters } from './hooks/useCharacters'
import { useAudio } from './hooks/useAudio'
import { useSavePoint } from './hooks/useSavePoint'
import { useHeaderImages } from './hooks/useHeaderImages'
import { api } from './services/api'
import { sessionStorage } from './services/sessionStorage'
import { partyStorage } from './services/partyStorage'
import { Tabs } from '@base-ui/react/tabs'

function App() {
  const [activeTab, setActiveTab] = useState('game')
  const [message, setMessage] = useState('')
  const [voiceEnabled, setVoiceEnabled] = useState(true)

  // Custom hooks
  const { images: headerImages, refreshImages: refreshHeaderImages } = useHeaderImages()
  const { currentAdventure, setCurrentAdventure, restoreConversationHistory } = useAdventure()
  const { characters, setCharacters } = useCharacters()
  const { currentAudio, playAudio, stopAudio } = useAudio()

  // CRITICAL: Always sync characters to partyStorage whenever they change
  // This ensures characters are always available for tool execution
  useEffect(() => {
    if (characters && Object.keys(characters).length > 0) {
      const saved = partyStorage.loadParty()
      // Only save if different to avoid unnecessary writes
      if (JSON.stringify(saved) !== JSON.stringify(characters)) {
        partyStorage.saveParty(characters)
        console.log(`💾 Synced ${Object.keys(characters).length} characters to partyStorage`)
      }
    }
  }, [characters])

  const {
    conversation,
    setConversation,
    loading,
    setLoading,
    sendMessage: sendMessageToDM,
    archiveChat: archiveChatBase,
    restoreChat,
  } = useConversation({
    currentAdventure,
    voiceEnabled,
    onAdventureUpdate: setCurrentAdventure,
    onCharactersUpdate: setCharacters,
    characters, // Pass characters directly as fallback
  })

  // Wrapper for archiveChat to refresh header images
  const archiveChat = async () => {
    await archiveChatBase()
    refreshHeaderImages()
  }

  const { loadSavePoint, createSavePoint } = useSavePoint({
    currentAdventure,
    conversation,
    voiceEnabled,
    onConversationUpdate: setConversation,
    onAdventureUpdate: setCurrentAdventure,
    onCharactersUpdate: setCharacters,
  })

  const { isListening, toggleListening } = useSpeechRecognition((transcript) => {
    setMessage(transcript)
  })

  // Restore conversation history when adventure loads or changes
  // Only restore if conversation is currently empty (don't overwrite restored archived chats)
  useEffect(() => {
    if (currentAdventure && conversation.length === 0) {
      const restoredMessages = restoreConversationHistory()
      if (restoredMessages.length > 0) {
        console.log(`Restoring ${restoredMessages.length} messages from conversation history`)
        setConversation(restoredMessages)
        // Also restore to backend DM agent
        const conversationMessages = restoredMessages.filter(msg => 
          msg.role === 'user' || msg.role === 'assistant'
        )
        if (conversationMessages.length > 0) {
          api.restoreConversation(conversationMessages).catch(err => {
            console.error('Failed to restore conversation history to backend:', err)
          })
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentAdventure?.id]) // Run when adventure loads or changes

  // Refresh header images when tab changes
  useEffect(() => {
    refreshHeaderImages()
  }, [activeTab, refreshHeaderImages])

  // Refresh header images when adventure loads
  useEffect(() => {
    if (currentAdventure) {
      refreshHeaderImages()
    }
  }, [currentAdventure?.id, refreshHeaderImages])

  const sendMessage = async () => {
    if (!message.trim() || loading) return

    const userMessage = message
    setMessage('')

    try {
      const response = await sendMessageToDM(userMessage)

      // Play audio if available
      if (response?.audio_url && voiceEnabled) {
        playAudio(response.audio_url)
      }
    } catch (error) {
      // Error already handled in useConversation
    }
  }

  const handleLoadSavePoint = async (savePointId: string) => {
    setLoading(true)
    try {
      const response = await loadSavePoint(savePointId)
      
      // Play audio if available
      if (response?.audio_url && voiceEnabled) {
        playAudio(response.audio_url)
      }
    } catch (error) {
      // Error already handled in useSavePoint
    } finally {
      setLoading(false)
    }
  }

  const handleCreateSavePoint = async () => {
    if (!currentAdventure) {
      alert('Please load an adventure first')
      return
    }

    try {
      const savePoint = await createSavePoint()
      if (savePoint) {
        alert(`✅ Save point created: ${savePoint.description}`)
      }
    } catch (error) {
      console.error('Failed to create save point:', error)
      alert(`Failed to create save point: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleReplayAudio = async (message: { role: string; content: string; audio?: string }) => {
    // If audio exists, replay it
    if (message.audio) {
      playAudio(message.audio)
      return
    }

    // If no audio exists and voice is enabled, try to generate it
    if (message.role === 'assistant' && !message.audio && voiceEnabled) {
      try {
        console.log('Generating TTS audio for message...')
        const response = await api.generateTTS(message.content, undefined, false)
        
        if (response.audio_url) {
          // Update the message with the new audio URL
          setConversation((prev) => 
            prev.map((msg) => 
              msg === message 
                ? { ...msg, audio: response.audio_url }
                : msg
            )
          )
          playAudio(response.audio_url)
          console.log('TTS audio generated and playing')
        }
      } catch (error) {
        console.error('Failed to generate TTS audio:', error)
        // Show error to user somehow? Or just fail silently
      }
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground dark">
      <div className="container mx-auto p-3 max-w-7xl">
        <Header leftImage={headerImages[0]} rightImage={headerImages[1]} />

        <Tabs.Root value={activeTab} onValueChange={(value: string | null) => setActiveTab(value || 'game')}>
          <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />

          <Tabs.Panel value="game">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <ChatPanel
                messages={conversation}
                loading={loading}
                message={message}
                setMessage={setMessage}
                onSend={sendMessage}
                voiceEnabled={voiceEnabled}
                setVoiceEnabled={setVoiceEnabled}
                isListening={isListening}
                toggleListening={toggleListening}
                currentAudio={currentAudio}
                stopAudio={stopAudio}
                currentAdventure={currentAdventure}
                onArchiveChat={archiveChat}
                onReplayAudio={handleReplayAudio}
              />

              <div className="space-y-3">
                <CharacterPanel characters={characters} />
                <DieRoller />
                <SavePoints
                  currentAdventure={currentAdventure}
                  onLoadSavePoint={handleLoadSavePoint}
                  onCreateSavePoint={handleCreateSavePoint}
                  onAdventureUpdate={setCurrentAdventure}
                />
              </div>
            </div>
          </Tabs.Panel>

          <Tabs.Panel value="players">
            <Players 
              characters={characters} 
              onCharactersChange={setCharacters}
            />
          </Tabs.Panel>

          <Tabs.Panel value="adventure">
            <div className="max-w-2xl">
              <AdventureSetup />
            </div>
          </Tabs.Panel>

          <Tabs.Panel value="dm-settings">
            <div className="max-w-2xl">
              <DMSettings onRestoreChat={restoreChat} />
            </div>
          </Tabs.Panel>
        </Tabs.Root>
      </div>
    </div>
  )
}

export default App
