// TypeScript declarations for Speech Recognition API
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition
    webkitSpeechRecognition: typeof SpeechRecognition
  }
}

export interface SpeechRecognition extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start(): void
  stop(): void
  onresult: (event: SpeechRecognitionEvent) => void
  onerror: (event: SpeechRecognitionErrorEvent) => void
  onend: () => void
}

export interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList
}

export interface SpeechRecognitionResultList {
  [index: number]: SpeechRecognitionResult
  length: number
}

export interface SpeechRecognitionResult {
  [index: number]: SpeechRecognitionAlternative
  length: number
  isFinal: boolean
}

export interface SpeechRecognitionAlternative {
  transcript: string
  confidence: number
}

export interface SpeechRecognitionErrorEvent {
  error: string
  message: string
}

declare var SpeechRecognition: {
  prototype: SpeechRecognition
  new (): SpeechRecognition
}

