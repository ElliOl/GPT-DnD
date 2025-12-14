import { useState, useEffect, useRef } from 'react'
import type { SpeechRecognition } from '../types/speech-recognition'

export function useSpeechRecognition(onTranscript: (text: string) => void) {
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = false
      recognition.lang = 'en-US'

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript
        onTranscript(transcript)
        setIsListening(false)
      }

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current = recognition
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
    }
  }, [onTranscript])

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition not supported in this browser')
      return
    }

    if (isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    } else {
      recognitionRef.current.start()
      setIsListening(true)
    }
  }

  return { isListening, toggleListening }
}

