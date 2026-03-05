import { useState, useEffect } from 'react'
import { Users } from 'lucide-react'
import { Tabs } from '@base-ui/react/tabs'
import type { Character } from '../services/api'

interface CharacterPanelProps {
  characters: Record<string, Character>
}

export function CharacterPanel({ characters }: CharacterPanelProps) {
  const [selectedTab, setSelectedTab] = useState<string | null>(null)

  const characterEntries = Object.entries(characters)
  
  // Helper to get first name from full name
  const getFirstName = (fullName: string): string => {
    return fullName.split(' ')[0] || fullName
  }

  // Set default tab when characters load
  useEffect(() => {
    if (characterEntries.length > 0 && !selectedTab) {
      setSelectedTab(characterEntries[0][0])
    } else if (characterEntries.length === 0) {
      setSelectedTab(null)
    }
  }, [characterEntries.length, selectedTab])

  if (characterEntries.length === 0) {
    return (
      <div className="bg-card border border-border">
        <div className="p-3 border-b border-border">
          <h2 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Users className="w-5 h-5" />
            Party
          </h2>
        </div>
        <div className="p-6 flex flex-col items-center justify-center gap-3">
          <p className="text-xs text-muted-foreground text-center">
            No characters loaded. Load a party in the Players tab.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border">
      <div className="p-3 border-b border-border">
        <h2 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <Users className="w-3 h-3" />
          Party
        </h2>
      </div>
      
      <Tabs.Root
        value={selectedTab}
        onValueChange={(value) => setSelectedTab(value)}
      >
        <Tabs.List className="flex overflow-x-auto border-b border-border">
          {characterEntries.map(([name]) => (
            <Tabs.Tab
              key={name}
              value={name}
              className={`px-3 py-2 text-xs font-medium border-b-2 border-transparent hover:text-foreground transition-colors whitespace-nowrap ${
                selectedTab === name
                  ? 'text-foreground'
                  : 'text-muted-foreground'
              }`}
              style={{
                borderBottomColor: selectedTab === name ? 'hsl(var(--primary))' : 'transparent',
              }}
              title={name} // Show full name on hover
            >
              {getFirstName(name)}
            </Tabs.Tab>
          ))}
        </Tabs.List>

        {characterEntries.map(([name, char]) => (
          <Tabs.Panel key={name} value={name} className="p-3">
            <div className="bg-background px-2 py-1.5 border border-border">
              <h3 className="font-semibold text-xs text-foreground">{char.name}</h3>
              <p className="text-[10px] text-muted-foreground">
                {char.race} {char.char_class} {char.level}
              </p>

              {/* HP Bar */}
              <div className="mt-2">
                <div className="flex justify-between text-[10px] mb-0.5">
                  <span className="text-muted-foreground">HP</span>
                  <span className="text-muted-foreground">
                    {char.current_hp} / {char.max_hp}
                  </span>
                </div>
                <div className="h-1 bg-card overflow-hidden">
                  <div
                    className="h-full bg-destructive"
                    style={{
                      width: `${(char.current_hp / char.max_hp) * 100}%`,
                    }}
                  />
                </div>
              </div>

              {/* AC */}
              <div className="mt-1.5 flex justify-between text-[10px]">
                <span className="text-muted-foreground">AC</span>
                <span className="text-foreground font-semibold">
                  {char.armor_class}
                </span>
              </div>
            </div>
          </Tabs.Panel>
        ))}
      </Tabs.Root>
    </div>
  )
}
