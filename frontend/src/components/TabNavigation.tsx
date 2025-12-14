import { Tabs } from '@base-ui/react/tabs'

interface TabNavigationProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <div className="border-b border-border mb-3">
      <Tabs.List className="flex overflow-x-auto">
        <Tabs.Tab
          value="game"
          className={`px-3 py-2 text-xs font-medium border-b-2 border-transparent hover:text-foreground transition-colors whitespace-nowrap ${
            activeTab === 'game'
              ? 'text-foreground'
              : 'text-muted-foreground'
          }`}
          style={{
            borderBottomColor: activeTab === 'game' ? 'hsl(var(--primary))' : 'transparent',
          }}
        >
          Game
        </Tabs.Tab>
        <Tabs.Tab
          value="players"
          className={`px-3 py-2 text-xs font-medium border-b-2 border-transparent hover:text-foreground transition-colors whitespace-nowrap ${
            activeTab === 'players'
              ? 'text-foreground'
              : 'text-muted-foreground'
          }`}
          style={{
            borderBottomColor: activeTab === 'players' ? 'hsl(var(--primary))' : 'transparent',
          }}
        >
          Players
        </Tabs.Tab>
        <Tabs.Tab
          value="adventure"
          className={`px-3 py-2 text-xs font-medium border-b-2 border-transparent hover:text-foreground transition-colors whitespace-nowrap ${
            activeTab === 'adventure'
              ? 'text-foreground'
              : 'text-muted-foreground'
          }`}
          style={{
            borderBottomColor: activeTab === 'adventure' ? 'hsl(var(--primary))' : 'transparent',
          }}
        >
          Adventure
        </Tabs.Tab>
        <Tabs.Tab
          value="dm-settings"
          className={`px-3 py-2 text-xs font-medium border-b-2 border-transparent hover:text-foreground transition-colors whitespace-nowrap ${
            activeTab === 'dm-settings'
              ? 'text-foreground'
              : 'text-muted-foreground'
          }`}
          style={{
            borderBottomColor: activeTab === 'dm-settings' ? 'hsl(var(--primary))' : 'transparent',
          }}
        >
          DM Settings
        </Tabs.Tab>
      </Tabs.List>
    </div>
  )
}
