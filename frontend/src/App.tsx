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
  })

  // Wrapper for archiveChat to refresh header images
  const archiveChat = async () => {
    await archiveChatBase()
    refreshHeaderImages()
  }

  const { loadSavePoint } = useSavePoint({
    currentAdventure,
    conversation,
    voiceEnabled,
    onConversationUpdate: setConversation,
    onAdventureUpdate: setCurrentAdventure,
  })

  const { isListening, toggleListening } = useSpeechRecognition((transcript) => {
    setMessage(transcript)
  })

  // Restore conversation history on mount
  useEffect(() => {
    const restoredMessages = restoreConversationHistory()
    if (restoredMessages.length > 0) {
      setConversation(restoredMessages)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

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
              />

              <div className="space-y-3">
                <CharacterPanel characters={characters} />
                <DieRoller />
                <SavePoints 
                  currentAdventure={currentAdventure}
                  onLoadSavePoint={handleLoadSavePoint}
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
