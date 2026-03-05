/**
 * Chat Archive Storage Service
 * 
 * Handles archiving chat conversations without deleting them.
 * Archived chats can be restored or permanently deleted.
 */

export interface ArchivedChat {
  id: string
  timestamp: string
  adventureId?: string
  adventureName?: string
  messages: Array<{
    role: string
    content: string
    timestamp?: string
  }>
  savePointId?: string
  savePointDescription?: string
}

const ARCHIVE_STORAGE_KEY = 'dnd-chat-archives'

export const chatArchive = {
  /**
   * Archive the current chat conversation
   */
  archiveChat(
    messages: Array<{ role: string; content: string }>,
    adventureId?: string,
    adventureName?: string,
    savePointId?: string,
    savePointDescription?: string
  ): ArchivedChat {
    if (!messages || messages.length === 0) {
      console.warn('Attempted to archive empty chat')
      throw new Error('Cannot archive empty chat')
    }

    const archive: ArchivedChat = {
      id: `archive-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      adventureId,
      adventureName,
      messages: messages.map(msg => ({
        ...msg,
        timestamp: new Date().toISOString(),
      })),
      savePointId,
      savePointDescription,
    }

    try {
      const archives = this.getAllArchives()
      archives.push(archive)
      this.saveArchives(archives)
      
      // Verify the save worked
      const verifyArchives = this.getAllArchives()
      const savedArchive = verifyArchives.find(a => a.id === archive.id)
      if (!savedArchive) {
        console.error('Failed to verify archive save - archive not found after save')
        throw new Error('Archive save verification failed')
      }
      
      console.log(`Archived chat successfully: ${archive.id} (${messages.length} messages)`)
    } catch (error) {
      console.error('Failed to archive chat:', error)
      // Try to recover by attempting save again
      try {
        const archives = this.getAllArchives()
        archives.push(archive)
        this.saveArchives(archives)
        console.log('Retry archive save succeeded')
      } catch (retryError) {
        console.error('Retry archive save also failed:', retryError)
        throw error
      }
    }

    return archive
  },

  /**
   * Get all archived chats
   */
  getAllArchives(): ArchivedChat[] {
    try {
      const stored = localStorage.getItem(ARCHIVE_STORAGE_KEY)
      if (!stored) {
        console.log('No archived chats found in localStorage')
        return []
      }
      const archives = JSON.parse(stored)
      if (!Array.isArray(archives)) {
        console.error('Archived chats data is not an array, resetting')
        localStorage.removeItem(ARCHIVE_STORAGE_KEY)
        return []
      }
      console.log(`Loaded ${archives.length} archived chats from localStorage`)
      return archives
    } catch (error) {
      console.error('Failed to load chat archives:', error)
      // Try to recover by clearing corrupted data
      try {
        localStorage.removeItem(ARCHIVE_STORAGE_KEY)
        console.log('Cleared corrupted archive data')
      } catch (clearError) {
        console.error('Failed to clear corrupted archive data:', clearError)
      }
      return []
    }
  },

  /**
   * Delete an archived chat
   */
  deleteArchive(archiveId: string): void {
    const archives = this.getAllArchives()
    const filtered = archives.filter(a => a.id !== archiveId)
    this.saveArchives(filtered)
  },

  /**
   * Restore an archived chat (returns the messages)
   */
  restoreArchive(archiveId: string): ArchivedChat['messages'] | null {
    const archives = this.getAllArchives()
    const archive = archives.find(a => a.id === archiveId)
    if (!archive) {
      console.warn('Archive not found:', archiveId)
      return null
    }

    console.log('Restoring archive:', archiveId, 'with', archive.messages.length, 'messages')
    console.log('Archive messages:', JSON.stringify(archive.messages, null, 2))
    
    // Return messages in the format expected by the conversation
    // Include all fields from archived messages (role, content, audio if available)
    const restoredMessages = archive.messages.map((msg, idx) => {
      const restored = {
        role: msg.role || 'assistant',
        content: msg.content || '',
      }
      console.log(`Message ${idx}:`, restored)
      return restored
    })
    
    // Filter out messages with empty content (they're invalid)
    const validMessages = restoredMessages.filter(msg => msg.content && msg.content.trim().length > 0)
    
    if (validMessages.length === 0) {
      console.error('No valid messages found in archive (all have empty content)')
      console.error('Original messages:', archive.messages)
      return null
    }
    
    if (validMessages.length < restoredMessages.length) {
      console.warn(`Filtered out ${restoredMessages.length - validMessages.length} messages with empty content`)
    }
    
    return validMessages
  },

  /**
   * Save archives to localStorage
   */
  saveArchives(archives: ArchivedChat[]): void {
    try {
      const serialized = JSON.stringify(archives)
      localStorage.setItem(ARCHIVE_STORAGE_KEY, serialized)
      
      // Verify the save worked
      const verifyStored = localStorage.getItem(ARCHIVE_STORAGE_KEY)
      if (verifyStored !== serialized) {
        console.error('Archive save verification failed - data mismatch')
        throw new Error('Archive save verification failed')
      }
      
      console.log(`Saved ${archives.length} archived chats to localStorage`)
    } catch (error) {
      console.error('Failed to save chat archives:', error)
      
      // Check if it's a quota exceeded error
      if (error instanceof Error && error.name === 'QuotaExceededError') {
        console.error('localStorage quota exceeded - cannot save more archives')
        // Try to remove oldest archives to make room
        if (archives.length > 1) {
          const sorted = [...archives].sort((a, b) => 
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          )
          const reduced = sorted.slice(-50) // Keep only the 50 most recent
          try {
            localStorage.setItem(ARCHIVE_STORAGE_KEY, JSON.stringify(reduced))
            console.log(`Reduced archives to ${reduced.length} most recent to save space`)
          } catch (retryError) {
            console.error('Failed to save reduced archives:', retryError)
          }
        }
      }
      throw error
    }
  },

  /**
   * Clear all archives
   */
  clearAllArchives(): void {
    localStorage.removeItem(ARCHIVE_STORAGE_KEY)
  },
}
