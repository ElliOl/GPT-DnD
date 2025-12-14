import { useState, useCallback } from 'react'

export function useAudio() {
  const [currentAudio, setCurrentAudio] = useState<HTMLAudioElement | null>(null)

  const playAudio = useCallback((audioUrl: string) => {
    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.currentTime = 0
    }

    const audio = new Audio(audioUrl)
    setCurrentAudio(audio)
    audio.play().catch((err) => console.error('Audio playback failed:', err))
  }, [currentAudio])

  const stopAudio = useCallback(() => {
    if (currentAudio) {
      currentAudio.pause()
      currentAudio.currentTime = 0
      setCurrentAudio(null)
    }
  }, [currentAudio])

  return {
    currentAudio,
    playAudio,
    stopAudio,
  }
}
