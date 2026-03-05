/**
 * Hook for managing modular adventure system
 * 
 * Integrates with backend AdventureContext for optimized token usage.
 */

import { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'

export interface ModularAdventure {
  id: string
  name: string
  description: string
  level_range: [number, number]
  estimated_sessions?: number
}

export interface AdventureState {
  loaded: boolean
  adventure_info?: any
  metadata?: any
}

export interface useModularAdventureReturn {
  // Available adventures
  availableAdventures: ModularAdventure[]
  loadingAdventures: boolean
  
  // Current adventure
  currentAdventure: AdventureState | null
  loadingCurrent: boolean
  
  // Actions
  loadAdventure: (adventureId: string) => Promise<void>
  updateAdventureState: (updates: any) => Promise<void>
  refreshCurrent: () => Promise<void>
  
  // Context fetching
  getContext: (contextType: 'minimal' | 'standard' | 'detailed') => Promise<string>
  getLocationDetails: (locationId: string, areaId?: string) => Promise<string>
  getNPCInfo: (npcId: string) => Promise<string>
  
  // Lists
  listChapters: () => Promise<string[]>
  listLocations: () => Promise<string[]>
  listNPCs: () => Promise<string[]>
  
  // Error state
  error: string | null
}

export function useModularAdventure(): useModularAdventureReturn {
  const [availableAdventures, setAvailableAdventures] = useState<ModularAdventure[]>([])
  const [loadingAdventures, setLoadingAdventures] = useState(false)
  const [currentAdventure, setCurrentAdventure] = useState<AdventureState | null>(null)
  const [loadingCurrent, setLoadingCurrent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch available adventures on mount
  useEffect(() => {
    const fetchAvailableAdventures = async () => {
      setLoadingAdventures(true)
      setError(null)
      try {
        const response = await api.getAvailableAdventures()
        setAvailableAdventures(response.adventures || [])
      } catch (err) {
        console.error('Failed to fetch available adventures:', err)
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch adventures'
        setError(errorMessage)
        // Set empty array so UI shows error instead of "no adventures"
        setAvailableAdventures([])
      } finally {
        setLoadingAdventures(false)
      }
    }

    fetchAvailableAdventures()
  }, [])

  // Fetch current adventure on mount
  useEffect(() => {
    refreshCurrent()
  }, [])

  const refreshCurrent = useCallback(async () => {
    setLoadingCurrent(true)
    setError(null)
    try {
      const response = await api.getCurrentAdventure()
      setCurrentAdventure(response.loaded ? response : null)
    } catch (err) {
      console.error('Failed to fetch current adventure:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch current adventure')
      setCurrentAdventure(null)
    } finally {
      setLoadingCurrent(false)
    }
  }, [])

  const loadAdventure = useCallback(async (adventureId: string) => {
    setLoadingCurrent(true)
    setError(null)
    try {
      const response = await api.loadAdventure(adventureId)
      if (response.success) {
        await refreshCurrent()
      } else {
        throw new Error(response.message || 'Failed to load adventure')
      }
    } catch (err) {
      console.error('Failed to load adventure:', err)
      setError(err instanceof Error ? err.message : 'Failed to load adventure')
      throw err
    } finally {
      setLoadingCurrent(false)
    }
  }, [refreshCurrent])

  const updateAdventureState = useCallback(async (updates: any) => {
    setError(null)
    try {
      const response = await api.updateAdventureState(updates)
      if (response.success) {
        // Update local state with new metadata
        if (currentAdventure) {
          setCurrentAdventure({
            ...currentAdventure,
            metadata: response.metadata,
          })
        }
      }
    } catch (err) {
      console.error('Failed to update adventure state:', err)
      setError(err instanceof Error ? err.message : 'Failed to update adventure state')
      throw err
    }
  }, [currentAdventure])

  const getContext = useCallback(async (contextType: 'minimal' | 'standard' | 'detailed'): Promise<string> => {
    try {
      const response = await api.getAdventureContext(contextType)
      return response.context || ''
    } catch (err) {
      console.error('Failed to get adventure context:', err)
      throw err
    }
  }, [])

  const getLocationDetails = useCallback(async (locationId: string, areaId?: string): Promise<string> => {
    try {
      const response = await api.getLocationDetails(locationId, areaId)
      return response.details || ''
    } catch (err) {
      console.error('Failed to get location details:', err)
      throw err
    }
  }, [])

  const getNPCInfo = useCallback(async (npcId: string): Promise<string> => {
    try {
      const response = await api.getNPCInfo(npcId)
      return response.info || ''
    } catch (err) {
      console.error('Failed to get NPC info:', err)
      throw err
    }
  }, [])

  const listChapters = useCallback(async (): Promise<string[]> => {
    try {
      const response = await api.listChapters()
      return response.chapters || []
    } catch (err) {
      console.error('Failed to list chapters:', err)
      throw err
    }
  }, [])

  const listLocations = useCallback(async (): Promise<string[]> => {
    try {
      const response = await api.listLocations()
      return response.locations || []
    } catch (err) {
      console.error('Failed to list locations:', err)
      throw err
    }
  }, [])

  const listNPCs = useCallback(async (): Promise<string[]> => {
    try {
      const response = await api.listNPCs()
      return response.npcs || []
    } catch (err) {
      console.error('Failed to list NPCs:', err)
      throw err
    }
  }, [])

  return {
    availableAdventures,
    loadingAdventures,
    currentAdventure,
    loadingCurrent,
    loadAdventure,
    updateAdventureState,
    refreshCurrent,
    getContext,
    getLocationDetails,
    getNPCInfo,
    listChapters,
    listLocations,
    listNPCs,
    error,
  }
}

