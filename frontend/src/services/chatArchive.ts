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
    const archive: ArchivedChat = {
      id: `archive-${Date.now()}`,
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

    const archives = this.getAllArchives()
    archives.push(archive)
    this.saveArchives(archives)

    return archive
  },

  /**
   * Get all archived chats
   */
  getAllArchives(): ArchivedChat[] {
    try {
      const stored = localStorage.getItem(ARCHIVE_STORAGE_KEY)
      if (!stored) return []
      return JSON.parse(stored)
    } catch (error) {
      console.error('Failed to load chat archives:', error)
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
    if (!archive) return null

    // Return messages in the format expected by the conversation
    return archive.messages.map(msg => ({
      role: msg.role,
      content: msg.content,
    }))
  },

  /**
   * Save archives to localStorage
   */
  saveArchives(archives: ArchivedChat[]): void {
    try {
      localStorage.setItem(ARCHIVE_STORAGE_KEY, JSON.stringify(archives))
    } catch (error) {
      console.error('Failed to save chat archives:', error)
    }
  },

  /**
   * Clear all archives
   */
  clearAllArchives(): void {
    localStorage.removeItem(ARCHIVE_STORAGE_KEY)
  },
}
