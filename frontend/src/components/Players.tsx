import { useState, useRef, useEffect } from 'react'
import { Users, Upload, Download, Plus, Trash2, Edit2 } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import { Input } from '@base-ui/react/input'
import type { Character } from '../services/api'
import { partyStorage } from '../services/partyStorage'

interface PlayersProps {
  characters: Record<string, Character>
  onCharactersChange: (characters: Record<string, Character>) => void
}

export function Players({ characters, onCharactersChange }: PlayersProps) {
  const [selectedCharacter, setSelectedCharacter] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const characterEntries = Object.entries(characters)

  // Load from localStorage on mount, or load default party
  useEffect(() => {
    const savedParty = partyStorage.loadParty()
    if (savedParty && Object.keys(savedParty).length > 0) {
      onCharactersChange(savedParty)
      if (Object.keys(savedParty).length > 0) {
        setSelectedCharacter(Object.keys(savedParty)[0])
      }
    } else {
      // Load default party file if no saved party
      fetch('/data/party_elara_thorin.json')
        .then(res => res.json())
        .then(data => {
          if (data.characters) {
            partyStorage.saveParty(data.characters)
            onCharactersChange(data.characters)
            const names = Object.keys(data.characters)
            if (names.length > 0) {
              setSelectedCharacter(names[0])
            }
          }
        })
        .catch(err => {
          console.log('Default party file not found, starting empty')
        })
    }
  }, [onCharactersChange])

  // Set default selected character
  useEffect(() => {
    if (characterEntries.length > 0 && !selectedCharacter) {
      setSelectedCharacter(characterEntries[0][0])
    } else if (characterEntries.length === 0) {
      setSelectedCharacter(null)
    }
  }, [characterEntries.length, selectedCharacter])

  const handleLoadParty = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      const importedCharacters = await partyStorage.importFromFile(file)
      partyStorage.saveParty(importedCharacters)
      onCharactersChange(importedCharacters)
      if (Object.keys(importedCharacters).length > 0) {
        setSelectedCharacter(Object.keys(importedCharacters)[0])
      }
    } catch (error) {
      console.error('Failed to load party file:', error)
      alert('Failed to load party file. Please check the file format.')
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleLoadClick = () => {
    fileInputRef.current?.click()
  }

  const handleExport = () => {
    partyStorage.exportToFile(characters)
  }

  const handleDeleteCharacter = (name: string) => {
    if (confirm(`Are you sure you want to delete ${name}?`)) {
      const updated = { ...characters }
      delete updated[name]
      partyStorage.saveParty(updated)
      onCharactersChange(updated)
      if (selectedCharacter === name) {
        const remaining = Object.keys(updated)
        setSelectedCharacter(remaining.length > 0 ? remaining[0] : null)
      }
    }
  }

  const handleUpdateCharacter = (name: string, updates: Partial<Character>) => {
    const updated = {
      ...characters,
      [name]: { ...characters[name], ...updates },
    }
    partyStorage.saveParty(updated)
    onCharactersChange(updated)
  }

  if (characterEntries.length === 0) {
    return (
      <div className="bg-card border border-border p-3">
        <h2 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
          <Users className="w-3 h-3" />
          Players
        </h2>

        <div className="p-6 flex flex-col items-center justify-center gap-3">
          <p className="text-xs text-muted-foreground text-center">
            No party loaded
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json,text/json"
            onChange={handleLoadParty}
            className="hidden"
          />
          <Button
            onClick={handleLoadClick}
            className="px-3 py-1.5 text-xs bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1.5"
          >
            <Upload className="w-3.5 h-3.5" />
            Load Party File
          </Button>
        </div>
      </div>
    )
  }

  const selectedChar = selectedCharacter ? characters[selectedCharacter] : null

  return (
    <div className="bg-card border border-border p-3">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <Users className="w-3 h-3" />
          Players
        </h2>
        <div className="flex gap-1.5">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json,text/json"
            onChange={handleLoadParty}
            className="hidden"
          />
          <Button
            onClick={handleLoadClick}
            className="px-2 py-1 text-xs bg-secondary border border-border text-secondary-foreground hover:bg-accent hover:text-accent-foreground transition-colors flex items-center gap-1"
            title="Load party file"
          >
            <Upload className="w-3 h-3" />
          </Button>
          <Button
            onClick={handleExport}
            className="px-2 py-1 text-xs bg-secondary border border-border text-secondary-foreground hover:bg-accent hover:text-accent-foreground transition-colors flex items-center gap-1"
            title="Export party file"
          >
            <Download className="w-3 h-3" />
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        <div className="space-y-1 max-h-[200px] overflow-y-auto">
          {characterEntries.map(([name, char]) => (
            <div
              key={name}
              className={`bg-background border border-border p-2 cursor-pointer transition-colors ${
                selectedCharacter === name
                  ? 'border-primary'
                  : 'hover:bg-card'
              }`}
              onClick={() => {
                setSelectedCharacter(name)
                setIsEditing(false)
              }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <h3 className="text-xs font-semibold text-foreground truncate">
                    {char.name}
                  </h3>
                  <p className="text-[10px] text-muted-foreground">
                    {char.race} {char.char_class} {char.level}
                  </p>
                </div>
                <Button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDeleteCharacter(name)
                  }}
                  className="px-1.5 py-0.5 text-[10px] bg-destructive border border-destructive text-destructive-foreground hover:bg-destructive/80 transition-colors"
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>

        {selectedChar && (
          <div className="bg-background border border-border p-2 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-foreground">
                {selectedChar.name}
              </h3>
              <Button
                onClick={() => setIsEditing(!isEditing)}
                className="px-1.5 py-0.5 text-[10px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors flex items-center gap-1"
              >
                <Edit2 className="w-3 h-3" />
                {isEditing ? 'Done' : 'Edit'}
              </Button>
            </div>

            {isEditing ? (
              <div className="space-y-2">
                <div>
                  <label className="text-[10px] text-muted-foreground">Name</label>
                  <Input
                    value={selectedChar.name}
                    onChange={(e) => handleUpdateCharacter(selectedCharacter!, { name: e.target.value })}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">Race</label>
                    <Input
                      value={selectedChar.race}
                      onChange={(e) => handleUpdateCharacter(selectedCharacter!, { race: e.target.value })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Class</label>
                    <Input
                      value={selectedChar.char_class}
                      onChange={(e) => handleUpdateCharacter(selectedCharacter!, { char_class: e.target.value })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">Level</label>
                    <Input
                      type="number"
                      value={selectedChar.level}
                      onChange={(e) => handleUpdateCharacter(selectedCharacter!, { level: parseInt(e.target.value) || 1 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Max HP</label>
                    <Input
                      type="number"
                      value={selectedChar.max_hp}
                      onChange={(e) => handleUpdateCharacter(selectedCharacter!, { max_hp: parseInt(e.target.value) || 1 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Current HP</label>
                    <Input
                      type="number"
                      value={selectedChar.current_hp}
                      onChange={(e) => handleUpdateCharacter(selectedCharacter!, { current_hp: parseInt(e.target.value) || 0 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground">AC</label>
                  <Input
                    type="number"
                    value={selectedChar.armor_class}
                    onChange={(e) => handleUpdateCharacter(selectedCharacter!, { armor_class: parseInt(e.target.value) || 10 })}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-[10px] text-muted-foreground">
                  {selectedChar.race} {selectedChar.char_class} {selectedChar.level}
                </p>

                {/* HP Bar */}
                <div>
                  <div className="flex justify-between text-[10px] mb-0.5">
                    <span className="text-muted-foreground">HP</span>
                    <span className="text-muted-foreground">
                      {selectedChar.current_hp} / {selectedChar.max_hp}
                    </span>
                  </div>
                  <div className="h-1 bg-card overflow-hidden">
                    <div
                      className="h-full bg-destructive"
                      style={{
                        width: `${(selectedChar.current_hp / selectedChar.max_hp) * 100}%`,
                      }}
                    />
                  </div>
                </div>

                {/* AC */}
                <div className="flex justify-between text-[10px]">
                  <span className="text-muted-foreground">AC</span>
                  <span className="text-foreground font-semibold">
                    {selectedChar.armor_class}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

