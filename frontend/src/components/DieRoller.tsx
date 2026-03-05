import { useState } from 'react'
import { Dice6, X } from 'lucide-react'
import { Button } from '@base-ui/react/button'
import { Input } from '@base-ui/react/input'

const DICE_TYPES = [4, 6, 8, 10, 12, 20, 100] as const

interface RollResult {
  die: number
  roll: number
  modifier: number
  total: number
  count?: number
  rolls?: number[]
}

export function DieRoller() {
  const [results, setResults] = useState<RollResult[]>([])
  const [modifier, setModifier] = useState('')
  const [count, setCount] = useState('1')

  const rollDie = (sides: number) => {
    const modifierValue = parseInt(modifier) || 0
    const diceCount = parseInt(count) || 1
    
    if (diceCount === 1) {
      const roll = Math.floor(Math.random() * sides) + 1
      const total = roll + modifierValue
      setResults((prev) => [{ die: sides, roll, modifier: modifierValue, total }, ...prev].slice(0, 20))
    } else {
      const rolls: number[] = []
      for (let i = 0; i < diceCount; i++) {
        rolls.push(Math.floor(Math.random() * sides) + 1)
      }
      const rollSum = rolls.reduce((sum, r) => sum + r, 0)
      const total = rollSum + modifierValue
      setResults((prev) => [{ die: sides, roll: rollSum, modifier: modifierValue, total, count: diceCount, rolls }, ...prev].slice(0, 20))
    }
  }

  const clearResults = () => {
    setResults([])
  }

  const formatResult = (item: RollResult) => {
    if (item.count && item.count > 1 && item.rolls) {
      const rollsStr = item.rolls.join(' + ')
      const modifierStr = item.modifier !== 0 ? (item.modifier > 0 ? ` + ${item.modifier}` : ` ${item.modifier}`) : ''
      return `${rollsStr}${modifierStr} = ${item.total}`
    } else {
      const modifierStr = item.modifier !== 0 ? (item.modifier > 0 ? ` + ${item.modifier}` : ` ${item.modifier}`) : ''
      return `${item.roll}${modifierStr}${modifierStr ? ` = ${item.total}` : ''}`
    }
  }

  return (
    <div className="bg-card border border-border p-3">
      <div className="mb-2">
        <h2 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <Dice6 className="w-5 h-5" />
          Die Roller
        </h2>
      </div>
      
      <div className="space-y-2">
        <div className="flex gap-1.5">
          <Input
            type="number"
            value={count}
            onChange={(e) => setCount(e.target.value)}
            placeholder="Count"
            className="w-12 px-1.5 py-1 text-[10px] bg-background text-foreground border border-border focus:border-primary focus:outline-none"
          />
          <Input
            type="number"
            value={modifier}
            onChange={(e) => setModifier(e.target.value)}
            placeholder="Modifier"
            className="flex-1 px-1.5 py-1 text-[10px] bg-background text-foreground border border-border focus:border-primary focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-4 gap-1">
          {DICE_TYPES.map((sides) => (
            <Button
              key={sides}
              onClick={() => rollDie(sides)}
              className="px-2 py-1 text-[10px] bg-card border border-border text-foreground hover:bg-accent transition-colors"
            >
              d{sides}
            </Button>
          ))}
          {results.length > 0 && (
            <Button
              onClick={clearResults}
              className="px-2.5 py-1.5 text-xs bg-card border border-border text-foreground hover:bg-accent transition-colors flex items-center justify-center gap-1"
              title="Clear results"
            >
              <X className="w-5 h-5" />
              Clear
            </Button>
          )}
        </div>

        {results.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-[10px] text-muted-foreground mb-1">Recent rolls:</p>
            <div className="space-y-0.5 max-h-[120px] overflow-y-auto">
              {results.map((item, idx) => (
                <div
                  key={idx}
                  className="text-[10px] text-foreground flex justify-between items-center"
                >
                  <span>
                    {item.count && item.count > 1 ? `${item.count}d${item.die}:` : `d${item.die}:`}
                  </span>
                  <span className="font-semibold text-primary">
                    {formatResult(item)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

