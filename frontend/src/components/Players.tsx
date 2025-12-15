import { useState, useRef, useEffect } from 'react'
import { Users, Upload, Download, Plus, Trash2, Edit2, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import { Input } from '@base-ui/react/input'
import { Tabs } from '@base-ui/react/tabs'
import type { Character } from '../services/api'
import { partyStorage } from '../services/partyStorage'

interface PlayersProps {
  characters: Record<string, Character>
  onCharactersChange: (characters: Record<string, Character>) => void
}

export function Players({ characters, onCharactersChange }: PlayersProps) {
  const [selectedCharacter, setSelectedCharacter] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [showAddSpellInput, setShowAddSpellInput] = useState(false)
  const [newSpellName, setNewSpellName] = useState('')
  const [expandedSpells, setExpandedSpells] = useState<Set<string>>(new Set())
  const [spellSuggestions, setSpellSuggestions] = useState<string[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const spellInputRef = useRef<HTMLInputElement>(null)
  
  // Common spells and effects database
  const allSpellsAndEffects = [
    // Spells
    'Mage Armor', 'Magic Missile', 'Shield', 'Detect Magic', 'Identify',
    'Cure Wounds', 'Healing Word', 'Bless', 'Bane', 'Faerie Fire',
    'Thunderwave', 'Burning Hands', 'Chromatic Orb', 'Sleep', 'Tasha\'s Hideous Laughter',
    'Fog Cloud', 'Grease', 'Expeditious Retreat', 'Feather Fall', 'Jump',
    'Longstrider', 'Disguise Self', 'Silent Image', 'Unseen Servant', 'Find Familiar',
    'Comprehend Languages', 'Detect Evil and Good', 'Protection from Evil and Good',
    'Alarm', 'Floating Disk', 'Goodberry', 'Entangle', 'Animal Friendship',
    // Conditions/Effects
    'Blinded', 'Charmed', 'Deafened', 'Exhaustion', 'Frightened',
    'Grappled', 'Incapacitated', 'Invisible', 'Paralyzed', 'Petrified',
    'Poisoned', 'Prone', 'Restrained', 'Stunned', 'Unconscious',
    // Other Effects
    'Rage', 'Second Wind', 'Action Surge', 'Lay on Hands', 'Divine Smite',
    'Sneak Attack', 'Cunning Action', 'Wild Shape', 'Rage', 'Reckless Attack',
    'Danger Sense', 'Frenzy', 'Brutal Critical', 'Extra Attack', 'Indomitable',
  ]
  
  const toggleSpell = (spellName: string) => {
    setExpandedSpells(prev => {
      const next = new Set(prev)
      if (next.has(spellName)) {
        next.delete(spellName)
      } else {
        next.add(spellName)
      }
      return next
    })
  }

  // Helper to get spell details (can be extended with a spell database)
  const getSpellDetails = (spellName: string): any => {
    // Check if spell details exist in character data
    const char = selectedCharacter ? characters[selectedCharacter] : null
    if (char && (char as any).spell_details && (char as any).spell_details[spellName]) {
      return (char as any).spell_details[spellName]
    }
    
    // Basic spell database for common spells
    const spellDatabase: Record<string, any> = {
      'Fire Bolt': {
        level: 'Cantrip',
        school: 'Evocation',
        casting_time: '1 action',
        range: '120 feet',
        components: 'V, S',
        duration: 'Instantaneous',
        description: 'You hurl a mote of fire at a creature or object within range. Make a ranged spell attack against the target. On a hit, the target takes 1d10 fire damage. A flammable object hit by this spell ignites if it isn\'t being worn or carried.',
      },
      'Ray of Frost': {
        level: 'Cantrip',
        school: 'Evocation',
        casting_time: '1 action',
        range: '60 feet',
        components: 'V, S',
        duration: 'Instantaneous',
        description: 'A frigid beam of blue-white light streaks toward a creature within range. Make a ranged spell attack against the target. On a hit, it takes 1d8 cold damage, and its speed is reduced by 10 feet until the start of your next turn.',
      },
      'Mage Hand': {
        level: 'Cantrip',
        school: 'Conjuration',
        casting_time: '1 action',
        range: '30 feet',
        components: 'V, S',
        duration: '1 minute',
        description: 'A spectral, floating hand appears at a point you choose within range. The hand lasts for the duration or until you dismiss it as an action. The hand can manipulate an object, open an unlocked door or container, stow or retrieve an item from an open container, or pour the contents out of a vial.',
      },
      'Mage Armor': {
        level: '1st',
        school: 'Abjuration',
        casting_time: '1 action',
        range: 'Touch',
        components: 'V, S, M (a piece of leather)',
        duration: '8 hours',
        description: 'You touch a willing creature who isn\'t wearing armor, and a protective magical force surrounds it until the spell ends. The target\'s base AC becomes 13 + its Dexterity modifier. The spell ends if the target dons armor or if you dismiss the spell as an action.',
      },
      'Magic Missile': {
        level: '1st',
        school: 'Evocation',
        casting_time: '1 action',
        range: '120 feet',
        components: 'V, S',
        duration: 'Instantaneous',
        description: 'You create three glowing darts of magical force. Each dart hits a creature of your choice that you can see within range. A dart deals 1d4+1 force damage to its target. The darts all strike simultaneously, and you can direct them to hit one creature or several.',
      },
      'Shield': {
        level: '1st',
        school: 'Abjuration',
        casting_time: '1 reaction',
        range: 'Self',
        components: 'V, S',
        duration: '1 round',
        description: 'An invisible barrier of magical force appears and protects you. Until the start of your next turn, you have a +5 bonus to AC, including against the triggering attack, and you take no damage from magic missile.',
      },
      'Detect Magic': {
        level: '1st',
        school: 'Divination',
        casting_time: '1 action',
        range: 'Self',
        components: 'V, S',
        duration: 'Concentration, up to 10 minutes',
        description: 'For the duration, you sense the presence of magic within 30 feet of you. If you sense magic in this way, you can use your action to see a faint aura around any visible creature or object in the area that bears magic, and you learn its school of magic, if any.',
      },
      'Identify': {
        level: '1st',
        school: 'Divination',
        casting_time: '1 minute',
        range: 'Touch',
        components: 'V, S, M (a pearl worth at least 100 gp and an owl feather)',
        duration: 'Instantaneous',
        description: 'You choose one object that you must touch throughout the casting of the spell. If it is a magic item or some other magic-imbued object, you learn its properties and how to use them, whether it requires attunement to use, and how many charges it has, if any.',
      },
    }
    
    // Return from database or default
    if (spellDatabase[spellName]) {
      return spellDatabase[spellName]
    }
    
    // Return basic structure for unknown spells
    const isCantrip = char && (char as any).spellcasting?.cantrips?.includes(spellName)
    return {
      level: isCantrip ? 'Cantrip' : '1st',
      school: 'Unknown',
      casting_time: '1 action',
      range: 'Unknown',
      components: 'V, S',
      duration: 'Instantaneous',
      description: 'Spell description not available. Add spell details in character data or extend the spell database.',
    }
  }

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
    } else if (selectedCharacter && !characters[selectedCharacter]) {
      // If selected character no longer exists, select first available
      if (characterEntries.length > 0) {
        setSelectedCharacter(characterEntries[0][0])
      } else {
        setSelectedCharacter(null)
      }
    }
  }, [characterEntries.length, selectedCharacter, characters])

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
    const currentChar = characters[name]
    if (!currentChar) {
      console.error('Character not found:', name)
      return
    }
    
    const updated = {
      ...characters,
      [name]: { 
        ...currentChar,
        ...updates,
        // Preserve active_spells if it exists
        ...(updates.active_spells ? { active_spells: updates.active_spells } : {}),
      },
    }
    
    console.log('Updating character:', name, 'with:', updates)
    console.log('Updated character:', updated[name])
    
    partyStorage.saveParty(updated)
    onCharactersChange(updated)
  }

  if (characterEntries.length === 0) {
    return (
      <div className="w-full">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Users className="w-5 h-5" />
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
              <Upload className="w-5 h-5" />
            </Button>
          </div>
        </div>

        <div className="bg-card border border-border p-6 flex flex-col items-center justify-center gap-3">
          <p className="text-xs text-muted-foreground text-center">
            No party loaded
          </p>
          <Button
            onClick={handleLoadClick}
            className="px-3 py-1.5 text-xs bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors flex items-center gap-1.5"
          >
            <Upload className="w-5 h-5" />
            Load Party File
          </Button>
        </div>
      </div>
    )
  }

  const selectedChar = selectedCharacter ? characters[selectedCharacter] : null

  return (
    <div className="w-full">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Left side - Character Stats (takes 2 columns) */}
        <div className="lg:col-span-2">
          <div className="bg-card border border-border">
            <Tabs.Root
              value={selectedCharacter}
              onValueChange={(value) => {
                setSelectedCharacter(value)
                setIsEditing(false)
              }}
            >
              <div className="flex items-center justify-between border-b border-border">
                <Tabs.List className="flex overflow-x-auto flex-1">
                {characterEntries.map(([name]) => (
                  <Tabs.Tab
                    key={name}
                    value={name}
                    className={`px-3 py-2 text-xs font-medium border-b-2 border-transparent hover:text-foreground transition-colors whitespace-nowrap ${
                      selectedCharacter === name
                        ? 'text-foreground'
                        : 'text-muted-foreground'
                    }`}
                    style={{
                      borderBottomColor: selectedCharacter === name ? 'hsl(var(--primary))' : 'transparent',
                    }}
                  >
                    {name}
                  </Tabs.Tab>
                ))}
                </Tabs.List>
                <div className="flex gap-1.5 px-3 py-2 border-l border-border">
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
                    <Upload className="w-5 h-5" />
                  </Button>
                  <Button
                    onClick={handleExport}
                    className="px-2 py-1 text-xs bg-secondary border border-border text-secondary-foreground hover:bg-accent hover:text-accent-foreground transition-colors flex items-center gap-1"
                    title="Export party file"
                  >
                    <Download className="w-5 h-5" />
                  </Button>
                </div>
              </div>

              {characterEntries.map(([name, char]) => (
                <Tabs.Panel key={name} value={name} className="p-3">
                  <div className="bg-background border border-border p-2 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold text-foreground">
                        {char.name}
                      </h3>
                      <div className="flex gap-1.5">
                        {isEditing && selectedCharacter === name && (
                          <Button
                            onClick={() => handleDeleteCharacter(name)}
                            className="px-1.5 py-0.5 text-[10px] bg-destructive border border-destructive text-destructive-foreground hover:bg-destructive/80 transition-colors flex items-center gap-1"
                            title="Delete character"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                        <Button
                          onClick={() => {
                            setIsEditing(!isEditing)
                            if (!isEditing) {
                              setSelectedCharacter(name)
                            }
                          }}
                          className="px-1.5 py-0.5 text-[10px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors flex items-center gap-1"
                        >
                          <Edit2 className="w-5 h-5" />
                          {isEditing && selectedCharacter === name ? 'Done' : 'Edit'}
                        </Button>
                      </div>
                    </div>

                {isEditing && selectedCharacter === name ? (
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                <div>
                  <label className="text-[10px] text-muted-foreground">Name</label>
                  <Input
                    value={char.name}
                    onChange={(e) => handleUpdateCharacter(name, { name: e.target.value })}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">Race</label>
                    <Input
                      value={char.race}
                      onChange={(e) => handleUpdateCharacter(name, { race: e.target.value })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Class</label>
                    <Input
                      value={char.char_class}
                      onChange={(e) => handleUpdateCharacter(name, { char_class: e.target.value })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">Level</label>
                    <Input
                      type="number"
                      value={char.level}
                      onChange={(e) => handleUpdateCharacter(name, { level: parseInt(e.target.value) || 1 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Max HP</label>
                    <Input
                      type="number"
                      value={char.max_hp}
                      onChange={(e) => handleUpdateCharacter(name, { max_hp: parseInt(e.target.value) || 1 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Current HP</label>
                    <Input
                      type="number"
                      value={char.current_hp}
                      onChange={(e) => handleUpdateCharacter(name, { current_hp: parseInt(e.target.value) || 0 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">AC</label>
                    <Input
                      type="number"
                      value={char.armor_class}
                      onChange={(e) => handleUpdateCharacter(name, { armor_class: parseInt(e.target.value) || 10 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Proficiency Bonus</label>
                    <Input
                      type="number"
                      value={char.proficiency_bonus}
                      onChange={(e) => handleUpdateCharacter(name, { proficiency_bonus: parseInt(e.target.value) || 2 })}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground">Speed</label>
                    <Input
                      type="number"
                      value={(char as any).speed || ''}
                      onChange={(e) => handleUpdateCharacter(name, { speed: parseInt(e.target.value) || 0 } as any)}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground">Temp HP</label>
                    <Input
                      type="number"
                      value={(char as any).temp_hp || 0}
                      onChange={(e) => handleUpdateCharacter(name, { temp_hp: parseInt(e.target.value) || 0 } as any)}
                      className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground">Background</label>
                  <Input
                    value={(char as any).background || ''}
                    onChange={(e) => handleUpdateCharacter(name, { background: e.target.value } as any)}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground">Gold</label>
                  <Input
                    type="number"
                    value={(char as any).gold || 0}
                    onChange={(e) => handleUpdateCharacter(name, { gold: parseInt(e.target.value) || 0 } as any)}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                  />
                </div>
                
                {/* Armor */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Armor</label>
                  <div className="space-y-2">
                    <div>
                      <label className="text-[9px] text-muted-foreground">Armor Name</label>
                      <Input
                        value={(char as any).armor?.name || ''}
                        onChange={(e) => handleUpdateCharacter(name, { 
                          armor: { 
                            ...(char as any).armor, 
                            name: e.target.value,
                            ac_base: (char as any).armor?.ac_base || 10,
                            type: (char as any).armor?.type || 'light'
                          } 
                        } as any)}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                        placeholder="e.g., Chain Mail"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-muted-foreground">AC Base</label>
                        <Input
                          type="number"
                          value={(char as any).armor?.ac_base || (char as any).armor?.ac || ''}
                          onChange={(e) => handleUpdateCharacter(name, { 
                            armor: { 
                              ...(char as any).armor, 
                              ac_base: parseInt(e.target.value) || 10,
                              name: (char as any).armor?.name || 'Armor',
                              type: (char as any).armor?.type || 'light'
                            } 
                          } as any)}
                          className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                        />
                      </div>
                      <div>
                        <label className="text-[9px] text-muted-foreground">Type</label>
                        <Input
                          value={(char as any).armor?.type || ''}
                          onChange={(e) => handleUpdateCharacter(name, { 
                            armor: { 
                              ...(char as any).armor, 
                              type: e.target.value,
                              name: (char as any).armor?.name || 'Armor',
                              ac_base: (char as any).armor?.ac_base || 10
                            } 
                          } as any)}
                          className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                          placeholder="light/medium/heavy"
                        />
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Shield */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Shield</label>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[9px] text-muted-foreground">Shield Name</label>
                      <Input
                        value={(char as any).shield?.name || ''}
                        onChange={(e) => handleUpdateCharacter(name, { 
                          shield: { 
                            ...(char as any).shield, 
                            name: e.target.value,
                            ac_bonus: (char as any).shield?.ac_bonus || 2
                          } 
                        } as any)}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                        placeholder="e.g., Shield"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] text-muted-foreground">AC Bonus</label>
                      <Input
                        type="number"
                        value={(char as any).shield?.ac_bonus || ''}
                        onChange={(e) => handleUpdateCharacter(name, { 
                          shield: { 
                            ...(char as any).shield, 
                            ac_bonus: parseInt(e.target.value) || 2,
                            name: (char as any).shield?.name || 'Shield'
                          } 
                        } as any)}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                      />
                    </div>
                  </div>
                </div>
                
                {/* Ability Scores */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Ability Scores</label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'].map((ability) => {
                      const score = char.abilities[ability] || char.abilities[ability.toLowerCase()] || 10
                      return (
                        <div key={ability}>
                          <label className="text-[9px] text-muted-foreground uppercase">{ability}</label>
                          <Input
                            type="number"
                            value={score}
                            onChange={(e) => {
                              const newAbilities = {
                                ...char.abilities,
                                [ability]: parseInt(e.target.value) || 8,
                                [ability.toLowerCase()]: parseInt(e.target.value) || 8
                              }
                              handleUpdateCharacter(name, { abilities: newAbilities })
                            }}
                            className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                          />
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Spellcasting */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Spellcasting</label>
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-muted-foreground">Spellcasting Ability</label>
                        <Input
                          value={(char as any).spellcasting?.ability || ''}
                          onChange={(e) => handleUpdateCharacter(name, {
                            spellcasting: {
                              ...(char as any).spellcasting,
                              ability: e.target.value,
                              spell_save_dc: (char as any).spellcasting?.spell_save_dc || 8,
                              spell_attack_bonus: (char as any).spellcasting?.spell_attack_bonus || 0,
                              spell_slots: (char as any).spellcasting?.spell_slots || {},
                              spells_prepared: (char as any).spellcasting?.spells_prepared || [],
                              cantrips: (char as any).spellcasting?.cantrips || []
                            }
                          } as any)}
                          className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                          placeholder="e.g., INT, WIS, CHA"
                        />
                      </div>
                      <div>
                        <label className="text-[9px] text-muted-foreground">Spell Save DC</label>
                        <Input
                          type="number"
                          value={(char as any).spellcasting?.spell_save_dc || ''}
                          onChange={(e) => handleUpdateCharacter(name, {
                            spellcasting: {
                              ...(char as any).spellcasting,
                              ability: (char as any).spellcasting?.ability || 'INT',
                              spell_save_dc: parseInt(e.target.value) || 8,
                              spell_attack_bonus: (char as any).spellcasting?.spell_attack_bonus || 0,
                              spell_slots: (char as any).spellcasting?.spell_slots || {},
                              spells_prepared: (char as any).spellcasting?.spells_prepared || [],
                              cantrips: (char as any).spellcasting?.cantrips || []
                            }
                          } as any)}
                          className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="text-[9px] text-muted-foreground">Spell Attack Bonus</label>
                      <Input
                        type="number"
                        value={(char as any).spellcasting?.spell_attack_bonus || ''}
                        onChange={(e) => handleUpdateCharacter(name, {
                          spellcasting: {
                            ...(char as any).spellcasting,
                            ability: (char as any).spellcasting?.ability || 'INT',
                            spell_save_dc: (char as any).spellcasting?.spell_save_dc || 8,
                            spell_attack_bonus: parseInt(e.target.value) || 0,
                            spell_slots: (char as any).spellcasting?.spell_slots || {},
                            spells_prepared: (char as any).spellcasting?.spells_prepared || [],
                            cantrips: (char as any).spellcasting?.cantrips || []
                          }
                        } as any)}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] text-muted-foreground">Spell Slots (e.g., "1st": 3, "2nd": 2)</label>
                      <Input
                        value={JSON.stringify((char as any).spellcasting?.spell_slots || {})}
                        onChange={(e) => {
                          try {
                            const slots = JSON.parse(e.target.value || '{}')
                            handleUpdateCharacter(name, {
                              spellcasting: {
                                ...(char as any).spellcasting,
                                ability: (char as any).spellcasting?.ability || 'INT',
                                spell_save_dc: (char as any).spellcasting?.spell_save_dc || 8,
                                spell_attack_bonus: (char as any).spellcasting?.spell_attack_bonus || 0,
                                spell_slots: slots,
                                spells_prepared: (char as any).spellcasting?.spells_prepared || [],
                                cantrips: (char as any).spellcasting?.cantrips || []
                              }
                            } as any)
                          } catch (err) {
                            // Invalid JSON, ignore
                          }
                        }}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5 font-mono text-[10px]"
                        placeholder='{"1st": 3, "2nd": 2}'
                      />
                    </div>
                    <div>
                      <label className="text-[9px] text-muted-foreground">Cantrips (comma-separated)</label>
                      <Input
                        value={(char as any).spellcasting?.cantrips?.join(', ') || ''}
                        onChange={(e) => {
                          const cantrips = e.target.value.split(',').map(s => s.trim()).filter(s => s)
                          handleUpdateCharacter(name, {
                            spellcasting: {
                              ...(char as any).spellcasting,
                              ability: (char as any).spellcasting?.ability || 'INT',
                              spell_save_dc: (char as any).spellcasting?.spell_save_dc || 8,
                              spell_attack_bonus: (char as any).spellcasting?.spell_attack_bonus || 0,
                              spell_slots: (char as any).spellcasting?.spell_slots || {},
                              spells_prepared: (char as any).spellcasting?.spells_prepared || [],
                              cantrips: cantrips
                            }
                          } as any)
                        }}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                        placeholder="Fire Bolt, Ray of Frost, Mage Hand"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] text-muted-foreground">Spells Prepared (comma-separated)</label>
                      <Input
                        value={(char as any).spellcasting?.spells_prepared?.join(', ') || ''}
                        onChange={(e) => {
                          const spells = e.target.value.split(',').map(s => s.trim()).filter(s => s)
                          handleUpdateCharacter(name, {
                            spellcasting: {
                              ...(char as any).spellcasting,
                              ability: (char as any).spellcasting?.ability || 'INT',
                              spell_save_dc: (char as any).spellcasting?.spell_save_dc || 8,
                              spell_attack_bonus: (char as any).spellcasting?.spell_attack_bonus || 0,
                              spell_slots: (char as any).spellcasting?.spell_slots || {},
                              spells_prepared: spells,
                              cantrips: (char as any).spellcasting?.cantrips || []
                            }
                          } as any)
                        }}
                        className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                        placeholder="Mage Armor, Magic Missile, Shield"
                      />
                    </div>
                  </div>
                </div>

                {/* Features */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Features (comma-separated)</label>
                  <Input
                    value={(char as any).features?.join(', ') || ''}
                    onChange={(e) => {
                      const features = e.target.value.split(',').map(s => s.trim()).filter(s => s)
                      handleUpdateCharacter(name, { features: features } as any)
                    }}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    placeholder="Fighting Style: Defense, Second Wind"
                  />
                </div>

                {/* Class Features */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Class Features (comma-separated)</label>
                  <Input
                    value={(char as any).class_features?.join(', ') || ''}
                    onChange={(e) => {
                      const classFeatures = e.target.value.split(',').map(s => s.trim()).filter(s => s)
                      handleUpdateCharacter(name, { class_features: classFeatures } as any)
                    }}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    placeholder="Action Surge, Second Wind"
                  />
                </div>

                {/* Racial Traits */}
                <div className="border-t border-border pt-2">
                  <label className="text-[10px] font-semibold text-foreground mb-1.5 block">Racial Traits (comma-separated)</label>
                  <Input
                    value={(char as any).racial_traits?.join(', ') || ''}
                    onChange={(e) => {
                      const racialTraits = e.target.value.split(',').map(s => s.trim()).filter(s => s)
                      handleUpdateCharacter(name, { racial_traits: racialTraits } as any)
                    }}
                    className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mt-0.5"
                    placeholder="Darkvision, Fey Ancestry"
                  />
                </div>
              </div>
                ) : (
                  <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {/* Basic Info */}
                  <div>
                    <p className="text-[10px] text-muted-foreground mb-1">
                      {char.race} {char.char_class} Level {char.level}
                    </p>
                    {(char as any).background && (
                      <p className="text-[10px] text-muted-foreground">
                        Background: {(char as any).background}
                      </p>
                    )}
                  </div>

                  {/* HP Bar */}
                  <div>
                    <div className="flex justify-between text-[10px] mb-0.5">
                      <span className="text-muted-foreground">HP</span>
                      <span className="text-muted-foreground">
                        {char.current_hp} / {char.max_hp}
                      </span>
                    </div>
                    <div className="h-1.5 bg-card overflow-hidden rounded">
                      <div
                        className="h-full bg-destructive transition-all"
                        style={{
                          width: `${Math.max(0, Math.min(100, (char.current_hp / char.max_hp) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* AC, Speed, and Proficiency Bonus */}
                  <div className="grid grid-cols-3 gap-2 border-t border-border pt-2">
                    <div className="text-[10px]">
                      <span className="text-muted-foreground">AC: </span>
                      <span 
                        className="text-foreground font-semibold"
                        title={(() => {
                          const armor = (char as any).armor
                          const shield = (char as any).shield
                          const activeSpells = (char as any).active_spells || []
                          const features = (char as any).features || []
                          
                          if (armor) {
                            let breakdown = `Armor: ${armor.ac_base || armor.ac || 0}`
                            if (shield) {
                              breakdown += ` + Shield: +${shield.ac_bonus || 0}`
                            }
                            if (features.some((f: string) => f.toLowerCase().includes('defense') && f.toLowerCase().includes('+1'))) {
                              breakdown += ` + Fighting Style: +1`
                            }
                            return breakdown
                          } else if (activeSpells.some((s: any) => 
                            (typeof s === 'string' && s.toLowerCase().includes('mage armor')) ||
                            (typeof s === 'object' && s.name?.toLowerCase().includes('mage armor'))
                          )) {
                            const dexMod = Math.floor(((char.abilities.DEX || char.abilities.dex || 10) - 10) / 2)
                            return `Mage Armor: 13 + Dex (${dexMod >= 0 ? '+' : ''}${dexMod}) = ${13 + dexMod}`
                          } else {
                            const dexMod = Math.floor(((char.abilities.DEX || char.abilities.dex || 10) - 10) / 2)
                            return `Base: 10 + Dex (${dexMod >= 0 ? '+' : ''}${dexMod}) = ${10 + dexMod}`
                          }
                        })()}
                      >
                        {(() => {
                          let calculatedAC = char.armor_class
                          const activeSpells = (char as any).active_spells || []
                          const armor = (char as any).armor
                          const shield = (char as any).shield
                          
                          // Calculate AC from armor if present
                          if (armor) {
                            calculatedAC = armor.ac_base || armor.ac || calculatedAC
                            // Add shield bonus if present
                            if (shield) {
                              calculatedAC += shield.ac_bonus || 0
                            }
                            // Add fighting style defense bonus if applicable
                            const features = (char as any).features || []
                            if (features.some((f: string) => f.toLowerCase().includes('defense') && f.toLowerCase().includes('+1'))) {
                              calculatedAC += 1
                            }
                          } else {
                            // No armor - check for Mage Armor or use base 10 + Dex
                            if (activeSpells.some((s: any) => 
                              (typeof s === 'string' && s.toLowerCase().includes('mage armor')) ||
                              (typeof s === 'object' && s.name?.toLowerCase().includes('mage armor'))
                            )) {
                              const dexMod = Math.floor(((char.abilities.DEX || char.abilities.dex || 10) - 10) / 2)
                              calculatedAC = 13 + dexMod
                            } else {
                              // Base AC 10 + Dex modifier
                              const dexMod = Math.floor(((char.abilities.DEX || char.abilities.dex || 10) - 10) / 2)
                              calculatedAC = 10 + dexMod
                            }
                          }
                          return calculatedAC
                        })()}
                      </span>
                      {((char as any).armor || (char as any).shield || ((char as any).active_spells && (char as any).active_spells.length > 0)) && (
                        <span className="text-[8px] text-muted-foreground ml-1" title="Hover over AC to see calculation">*</span>
                      )}
                    </div>
                    {(char as any).speed && (
                      <div className="text-[10px]">
                        <span className="text-muted-foreground">Speed: </span>
                        <span className="text-foreground font-semibold">
                          {(char as any).speed} ft
                        </span>
                      </div>
                    )}
                    <div className="text-[10px]">
                      <span className="text-muted-foreground">Proficiency: </span>
                      <span className="text-foreground font-semibold">
                        +{char.proficiency_bonus}
                      </span>
                    </div>
                  </div>
                  
                  {/* Armor and Shield */}
                  {((char as any).armor || (char as any).shield) && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Armor & Shield</h4>
                      <div className="space-y-1">
                        {(char as any).armor && (
                          <div className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{(char as any).armor.name}</div>
                            <div className="text-muted-foreground">
                              AC: {(char as any).armor.ac_base || (char as any).armor.ac} 
                              {(char as any).armor.type && ` (${(char as any).armor.type})`}
                            </div>
                          </div>
                        )}
                        {(char as any).shield && (
                          <div className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{(char as any).shield.name}</div>
                            <div className="text-muted-foreground">
                              AC Bonus: +{(char as any).shield.ac_bonus}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Ability Scores */}
                  <div className="border-t border-border pt-2">
                    <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Ability Scores</h4>
                    <div className="grid grid-cols-3 gap-1.5">
                      {['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'].map((ability) => {
                        const score = char.abilities[ability] || char.abilities[ability.toLowerCase()]
                        if (score === undefined) return null
                        const modifier = Math.floor((score - 10) / 2)
                        const modifierStr = modifier >= 0 ? `+${modifier}` : `${modifier}`
                        return (
                          <div key={ability} className="bg-card border border-border p-1.5 rounded">
                            <div className="text-[9px] text-muted-foreground uppercase">{ability}</div>
                            <div className="text-xs font-semibold text-foreground">{score}</div>
                            <div className="text-[9px] text-muted-foreground">{modifierStr}</div>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* Skills */}
                  {char.skills && Object.keys(char.skills).length > 0 && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Skills</h4>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(char.skills).map(([skill, proficient]) => (
                          <div
                            key={skill}
                            className={`text-[9px] px-1.5 py-0.5 rounded border ${
                              proficient
                                ? 'bg-primary border-primary text-primary-foreground font-semibold'
                                : 'bg-card border-border text-muted-foreground'
                            }`}
                          >
                            {skill}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Save Proficiencies */}
                  {(char as any).save_proficiencies && 
                   (char as any).save_proficiencies.length > 0 && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Saving Throw Proficiencies</h4>
                      <div className="flex flex-wrap gap-1">
                        {(char as any).save_proficiencies.map((save: string) => (
                          <div
                            key={save}
                            className="text-[9px] px-1.5 py-0.5 rounded border bg-primary border-primary text-primary-foreground font-semibold uppercase"
                          >
                            {save}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Armor and Shield */}
                  {((char as any).armor || (char as any).shield) && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Armor & Shield</h4>
                      <div className="space-y-1">
                        {(char as any).armor && (
                          <div className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{(char as any).armor.name}</div>
                            <div className="text-muted-foreground">
                              AC: {(char as any).armor.ac_base || (char as any).armor.ac} 
                              {(char as any).armor.type && ` (${(char as any).armor.type})`}
                            </div>
                          </div>
                        )}
                        {(char as any).shield && (
                          <div className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{(char as any).shield.name}</div>
                            <div className="text-muted-foreground">
                              AC Bonus: +{(char as any).shield.ac_bonus}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Weapons */}
                  {(char as any).weapons && (char as any).weapons.length > 0 && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Weapons</h4>
                      <div className="space-y-1">
                        {(char as any).weapons.map((weapon: any, idx: number) => (
                          <div key={idx} className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{weapon.name}</div>
                            <div className="text-muted-foreground">
                              {weapon.attack_bonus >= 0 ? '+' : ''}{weapon.attack_bonus} to hit, {weapon.damage_dice}
                              {weapon.damage_bonus >= 0 ? '+' : ''}{weapon.damage_bonus} {weapon.damage_type}
                              {weapon.ranged && ` (ranged ${weapon.range})`}
                              {weapon.thrown && ` (thrown ${weapon.range})`}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Inventory */}
                  {char.inventory && char.inventory.length > 0 && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Inventory</h4>
                      <div className="space-y-0.5 max-h-[100px] overflow-y-auto pb-2">
                        {char.inventory.map((item, idx) => (
                          <div key={idx} className="text-[9px] text-muted-foreground">
                            • {item}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Gold */}
                  {(char as any).gold !== undefined && (
                    <div className="flex justify-between text-[10px] border-t border-border pt-2">
                      <span className="text-muted-foreground">Gold</span>
                      <span className="text-foreground font-semibold">
                        {(char as any).gold} gp
                      </span>
                    </div>
                  )}

                  {/* Conditions */}
                  {char.conditions && char.conditions.length > 0 && (
                    <div className="border-t border-border pt-2">
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Conditions</h4>
                      <div className="flex flex-wrap gap-1">
                        {char.conditions.map((condition, idx) => (
                          <div
                            key={idx}
                            className="text-[9px] px-1.5 py-0.5 rounded border bg-destructive/20 border-destructive text-destructive-foreground"
                          >
                            {condition}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  </div>
                )}
                  </div>
                </Tabs.Panel>
              ))}
            </Tabs.Root>
          </div>
        </div>

        {/* Right side - Spells & Abilities Box (takes 1 column) */}
        {selectedCharacter && characters[selectedCharacter] && !isEditing && (
          <div className="bg-card border border-border p-3">
            <h3 className="text-xs font-semibold text-foreground mb-3">Spells & Abilities</h3>
            <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {/* Spellcasting Info */}
                  {(characters[selectedCharacter] as any).spellcasting ? (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Spellcasting</h4>
                      <div className="space-y-1.5 text-[9px] bg-card border border-border p-2 rounded">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Spell Save DC:</span>
                          <span className="text-foreground font-semibold">
                            {(characters[selectedCharacter] as any).spellcasting.spell_save_dc}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Spell Attack Bonus:</span>
                          <span className="text-foreground font-semibold">
                            {(characters[selectedCharacter] as any).spellcasting.spell_attack_bonus >= 0 ? '+' : ''}
                            {(characters[selectedCharacter] as any).spellcasting.spell_attack_bonus}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Spellcasting Ability:</span>
                          <span className="text-foreground font-semibold uppercase">
                            {(characters[selectedCharacter] as any).spellcasting.ability}
                          </span>
                        </div>
                        {(characters[selectedCharacter] as any).spellcasting.spell_slots && (
                          <div className="border-t border-border pt-1 mt-1">
                            <span className="text-muted-foreground block mb-1">Spell Slots:</span>
                            <div className="space-y-1">
                              {Object.entries((characters[selectedCharacter] as any).spellcasting.spell_slots).map(([level, maxSlots]: [string, any]) => {
                                const usedSlots = (characters[selectedCharacter] as any).spell_slots_used?.[level] || 0
                                const availableSlots = maxSlots - usedSlots
                                return (
                                  <div key={level} className="flex items-center gap-2">
                                    <span className="text-muted-foreground text-[8px] w-12">{level} level:</span>
                                    <div className="flex gap-1">
                                      {Array.from({ length: maxSlots }).map((_, idx) => {
                                        const isUsed = idx < usedSlots
                                        return (
                                          <button
                                            key={idx}
                                            onClick={() => {
                                              const currentUsed = (characters[selectedCharacter] as any).spell_slots_used || {}
                                              const newUsed = { ...currentUsed }
                                              if (isUsed) {
                                                newUsed[level] = Math.max(0, (newUsed[level] || 0) - 1)
                                              } else {
                                                newUsed[level] = Math.min(maxSlots, (newUsed[level] || 0) + 1)
                                              }
                                              handleUpdateCharacter(selectedCharacter!, {
                                                spell_slots_used: newUsed
                                              } as any)
                                            }}
                                            className={`w-4 h-4 border-2 rounded-sm transition-colors ${
                                              isUsed
                                                ? 'bg-primary border-primary'
                                                : 'bg-transparent border-border hover:border-primary'
                                            }`}
                                            title={`${isUsed ? 'Used' : 'Available'} ${level} level spell slot`}
                                          />
                                        )
                                      })}
                                    </div>
                                    <span className="text-[8px] text-muted-foreground ml-auto">
                                      {availableSlots}/{maxSlots}
                                    </span>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Spellcasting</h4>
                      <div className="text-[9px] text-muted-foreground bg-card border border-border p-2 rounded">
                        No spellcasting ability
                      </div>
                    </div>
                  )}

                  {/* Cantrips */}
                  {(characters[selectedCharacter] as any).spellcasting?.cantrips && 
                   (characters[selectedCharacter] as any).spellcasting.cantrips.length > 0 && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Cantrips</h4>
                      <div className="space-y-1">
                        {(characters[selectedCharacter] as any).spellcasting.cantrips.map((cantrip: string, idx: number) => {
                          const isExpanded = expandedSpells.has(cantrip)
                          const details = getSpellDetails(cantrip)
                          return (
                            <div key={idx} className="text-[9px] bg-card border border-border rounded">
                              <button
                                onClick={() => toggleSpell(cantrip)}
                                className="w-full flex items-center justify-between p-1.5 hover:bg-accent transition-colors text-left"
                              >
                                <div className="flex items-center gap-1.5 flex-1">
                                  {isExpanded ? (
                                    <ChevronDown className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                  ) : (
                                    <ChevronRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                  )}
                                  <div>
                                    <div className="font-semibold text-foreground">{cantrip}</div>
                                    <div className="text-muted-foreground text-[8px]">Cantrip - At will</div>
                                  </div>
                                </div>
                              </button>
                              {isExpanded && (
                                <div className="px-1.5 pb-1.5 pt-0 border-t border-border mt-1">
                                  <div className="space-y-1 text-[8px]">
                                    <div className="grid grid-cols-2 gap-1">
                                      <div>
                                        <span className="text-muted-foreground">Level: </span>
                                        <span className="text-foreground">{details.level}</span>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">School: </span>
                                        <span className="text-foreground">{details.school}</span>
                                      </div>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Casting Time: </span>
                                      <span className="text-foreground">{details.casting_time}</span>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Range: </span>
                                      <span className="text-foreground">{details.range}</span>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Components: </span>
                                      <span className="text-foreground">{details.components}</span>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Duration: </span>
                                      <span className="text-foreground">{details.duration}</span>
                                    </div>
                                    <div className="pt-1 border-t border-border">
                                      <div className="text-muted-foreground mb-0.5">Description:</div>
                                      <div className="text-foreground">{details.description}</div>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Active Spells/Effects */}
                  {selectedCharacter && characters[selectedCharacter] && !isEditing && (
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <h4 className="text-[10px] font-semibold text-foreground">Active Spells/Effects</h4>
                        {!showAddSpellInput && (
                          <Button
                            onClick={(e) => {
                              e.preventDefault()
                              e.stopPropagation()
                              setShowAddSpellInput(true)
                              setNewSpellName('')
                            }}
                            className="px-1.5 py-0.5 text-[8px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors"
                            title="Add active spell"
                          >
                            + Add
                          </Button>
                        )}
                      </div>
                      {showAddSpellInput && (
                        <div className="mb-2 p-2 bg-card border border-border rounded relative">
                          <input
                            ref={spellInputRef}
                            type="text"
                            value={newSpellName}
                            onChange={(e) => {
                              const value = e.target.value
                              setNewSpellName(value)
                              if (value.trim()) {
                                const filtered = allSpellsAndEffects.filter(spell =>
                                  spell.toLowerCase().includes(value.toLowerCase())
                                )
                                setSpellSuggestions(filtered.slice(0, 8))
                                setShowSuggestions(true)
                              } else {
                                setSpellSuggestions([])
                                setShowSuggestions(false)
                              }
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && newSpellName.trim()) {
                                const char = characters[selectedCharacter]
                                const currentSpells = (char as any).active_spells || []
                                handleUpdateCharacter(selectedCharacter, {
                                  active_spells: [...currentSpells, newSpellName.trim()]
                                } as any)
                                setShowAddSpellInput(false)
                                setNewSpellName('')
                                setShowSuggestions(false)
                              } else if (e.key === 'Escape') {
                                setShowAddSpellInput(false)
                                setNewSpellName('')
                                setShowSuggestions(false)
                              } else if (e.key === 'ArrowDown' && spellSuggestions.length > 0) {
                                e.preventDefault()
                                setNewSpellName(spellSuggestions[0])
                              }
                            }}
                            onFocus={() => {
                              if (newSpellName.trim()) {
                                const filtered = allSpellsAndEffects.filter(spell =>
                                  spell.toLowerCase().includes(newSpellName.toLowerCase())
                                )
                                setSpellSuggestions(filtered.slice(0, 8))
                                setShowSuggestions(true)
                              }
                            }}
                            onBlur={() => {
                              // Delay to allow click on suggestion
                              setTimeout(() => setShowSuggestions(false), 200)
                            }}
                            placeholder="Type to search spells/effects..."
                            className="w-full px-2 py-1 text-xs bg-background text-foreground border border-border focus:border-primary focus:outline-none mb-1.5"
                            autoFocus
                          />
                          {showSuggestions && spellSuggestions.length > 0 && (
                            <div className="absolute z-10 w-full mt-0.5 bg-card border border-border rounded max-h-[200px] overflow-y-auto shadow-lg">
                              {spellSuggestions.map((suggestion, idx) => (
                                <button
                                  key={idx}
                                  type="button"
                                  onMouseDown={(e) => {
                                    e.preventDefault()
                                    setNewSpellName(suggestion)
                                    setShowSuggestions(false)
                                    spellInputRef.current?.focus()
                                  }}
                                  className="w-full text-left px-2 py-1.5 text-[9px] hover:bg-accent transition-colors border-b border-border last:border-b-0"
                                >
                                  {suggestion}
                                </button>
                              ))}
                            </div>
                          )}
                          <div className="flex gap-1.5">
                            <Button
                              onClick={() => {
                                if (newSpellName.trim()) {
                                  const char = characters[selectedCharacter]
                                  const currentSpells = (char as any).active_spells || []
                                  handleUpdateCharacter(selectedCharacter, {
                                    active_spells: [...currentSpells, newSpellName.trim()]
                                  } as any)
                                }
                                setShowAddSpellInput(false)
                                setNewSpellName('')
                                setShowSuggestions(false)
                              }}
                              className="px-2 py-1 text-[8px] bg-primary border border-primary text-primary-foreground hover:bg-primary-hover transition-colors"
                            >
                              Add
                            </Button>
                            <Button
                              onClick={() => {
                                setShowAddSpellInput(false)
                                setNewSpellName('')
                                setShowSuggestions(false)
                              }}
                              className="px-2 py-1 text-[8px] bg-secondary border border-border text-secondary-foreground hover:bg-accent transition-colors"
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                      {(characters[selectedCharacter] as any).active_spells && 
                       (characters[selectedCharacter] as any).active_spells.length > 0 ? (
                        <div className="space-y-1 max-h-[150px] overflow-y-auto pb-2">
                          {(characters[selectedCharacter] as any).active_spells.map((spell: any, idx: number) => (
                            <div key={idx} className="flex items-start justify-between text-[9px] bg-primary/20 border border-primary p-1.5 rounded">
                              <div className="flex-1">
                                <div className="font-semibold text-foreground">{typeof spell === 'string' ? spell : spell.name}</div>
                                {typeof spell === 'object' && spell.duration && (
                                  <div className="text-muted-foreground text-[8px] mt-0.5">{spell.duration}</div>
                                )}
                              </div>
                              <Button
                                onClick={() => {
                                  const currentSpells = (characters[selectedCharacter] as any).active_spells || []
                                  handleUpdateCharacter(selectedCharacter, {
                                    active_spells: currentSpells.filter((_: any, i: number) => i !== idx)
                                  } as any)
                                }}
                                className="px-1 py-0.5 text-[8px] bg-destructive border border-destructive text-destructive-foreground hover:bg-destructive/80 transition-colors ml-1"
                                title="Remove spell"
                              >
                                ×
                              </Button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-[9px] text-muted-foreground bg-card border border-border p-2 rounded">
                          No active spells
                        </div>
                      )}
                    </div>
                  )}

                  {/* Spells Prepared */}
                  {(characters[selectedCharacter] as any).spellcasting?.spells_prepared && 
                   (characters[selectedCharacter] as any).spellcasting.spells_prepared.length > 0 && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Spells Prepared</h4>
                      <div className="space-y-1 max-h-[200px] overflow-y-auto pb-2">
                        {(characters[selectedCharacter] as any).spellcasting.spells_prepared.map((spell: string, idx: number) => {
                          const isExpanded = expandedSpells.has(spell)
                          const details = getSpellDetails(spell)
                          return (
                            <div key={idx} className="text-[9px] bg-card border border-border rounded">
                              <button
                                onClick={() => toggleSpell(spell)}
                                className="w-full flex items-center justify-between p-1.5 hover:bg-accent transition-colors text-left"
                              >
                                <div className="flex items-center gap-1.5 flex-1">
                                  {isExpanded ? (
                                    <ChevronDown className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                  ) : (
                                    <ChevronRight className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                  )}
                                  <div className="font-semibold text-foreground">{spell}</div>
                                </div>
                              </button>
                              {isExpanded && (
                                <div className="px-1.5 pb-1.5 pt-0 border-t border-border mt-1">
                                  <div className="space-y-1 text-[8px]">
                                    <div className="grid grid-cols-2 gap-1">
                                      <div>
                                        <span className="text-muted-foreground">Level: </span>
                                        <span className="text-foreground">{details.level}</span>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">School: </span>
                                        <span className="text-foreground">{details.school}</span>
                                      </div>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Casting Time: </span>
                                      <span className="text-foreground">{details.casting_time}</span>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Range: </span>
                                      <span className="text-foreground">{details.range}</span>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Components: </span>
                                      <span className="text-foreground">{details.components}</span>
                                    </div>
                                    <div>
                                      <span className="text-muted-foreground">Duration: </span>
                                      <span className="text-foreground">{details.duration}</span>
                                    </div>
                                    <div className="pt-1 border-t border-border">
                                      <div className="text-muted-foreground mb-0.5">Description:</div>
                                      <div className="text-foreground">{details.description}</div>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Features & Abilities */}
                  {(characters[selectedCharacter] as any).features && (characters[selectedCharacter] as any).features.length > 0 && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Features & Abilities</h4>
                      <div className="space-y-1.5 max-h-[300px] overflow-y-auto pb-2">
                        {(characters[selectedCharacter] as any).features.map((feature: string, idx: number) => {
                          // Try to parse feature name and description
                          const parts = feature.split(':')
                          const featureName = parts[0]?.trim() || feature
                          const featureDesc = parts.slice(1).join(':').trim()
                          
                          return (
                            <div key={idx} className="text-[9px] bg-card border border-border p-1.5 rounded">
                              <div className="font-semibold text-foreground">{featureName}</div>
                              {featureDesc && (
                                <div className="text-muted-foreground text-[8px] mt-0.5">{featureDesc}</div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Class Features */}
                  {(characters[selectedCharacter] as any).class_features && (characters[selectedCharacter] as any).class_features.length > 0 && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Class Features</h4>
                      <div className="space-y-1.5 max-h-[200px] overflow-y-auto pb-2">
                        {(characters[selectedCharacter] as any).class_features.map((feature: string, idx: number) => (
                          <div key={idx} className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{feature}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Racial Traits */}
                  {(characters[selectedCharacter] as any).racial_traits && (characters[selectedCharacter] as any).racial_traits.length > 0 && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Racial Traits</h4>
                      <div className="space-y-1.5 max-h-[200px] overflow-y-auto pb-2">
                        {(characters[selectedCharacter] as any).racial_traits.map((trait: string, idx: number) => (
                          <div key={idx} className="text-[9px] bg-card border border-border p-1.5 rounded">
                            <div className="font-semibold text-foreground">{trait}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Notes */}
                  {(characters[selectedCharacter] as any).notes && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Notes</h4>
                      <div className="text-[9px] text-muted-foreground bg-card border border-border p-2 rounded">
                        {(characters[selectedCharacter] as any).notes}
                      </div>
                    </div>
                  )}

                  {/* Personality Traits */}
                  {(characters[selectedCharacter] as any).personality && (
                    <div>
                      <h4 className="text-[10px] font-semibold text-foreground mb-1.5">Personality</h4>
                      <div className="space-y-1 text-[9px] bg-card border border-border p-2 rounded">
                        {(characters[selectedCharacter] as any).personality.trait && (
                          <div>
                            <span className="text-muted-foreground">Trait: </span>
                            <span className="text-foreground">{(characters[selectedCharacter] as any).personality.trait}</span>
                          </div>
                        )}
                        {(characters[selectedCharacter] as any).personality.ideal && (
                          <div>
                            <span className="text-muted-foreground">Ideal: </span>
                            <span className="text-foreground">{(characters[selectedCharacter] as any).personality.ideal}</span>
                          </div>
                        )}
                        {(characters[selectedCharacter] as any).personality.bond && (
                          <div>
                            <span className="text-muted-foreground">Bond: </span>
                            <span className="text-foreground">{(characters[selectedCharacter] as any).personality.bond}</span>
                          </div>
                        )}
                        {(characters[selectedCharacter] as any).personality.flaw && (
                          <div>
                            <span className="text-muted-foreground">Flaw: </span>
                            <span className="text-foreground">{(characters[selectedCharacter] as any).personality.flaw}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

