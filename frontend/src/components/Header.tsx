interface HeaderProps {
  leftImage?: string
  rightImage?: string
}

export function Header({ leftImage, rightImage }: HeaderProps) {
  return (
    <header className="text-center py-3 border-b border-border mb-3">
      <div className="flex items-center justify-center gap-4">
        {leftImage && (
          <div className="w-24 h-24 relative flex items-center justify-center" style={{ imageRendering: 'pixelated' }}>
            <img 
              src={leftImage.replace('8bit-roleplaycards', '8bit-roleplaycards-processed')} 
              alt="Character"
              className="max-w-full max-h-full"
              style={{
                imageRendering: 'pixelated',
                objectFit: 'contain',
              }}
              onError={(e) => {
                // Fallback to original if processed version doesn't exist
                const target = e.target as HTMLImageElement
                target.src = leftImage
              }}
            />
          </div>
        )}
        <h1 className="text-sm font-medium text-foreground">
          AI Dungeon Master
        </h1>
        {rightImage && (
          <div className="w-24 h-24 relative flex items-center justify-center" style={{ imageRendering: 'pixelated' }}>
            <img 
              src={rightImage.replace('8bit-roleplaycards', '8bit-roleplaycards-processed')} 
              alt="Character"
              className="max-w-full max-h-full"
              style={{
                imageRendering: 'pixelated',
                objectFit: 'contain',
              }}
              onError={(e) => {
                // Fallback to original if processed version doesn't exist
                const target = e.target as HTMLImageElement
                target.src = rightImage
              }}
            />
          </div>
        )}
      </div>
    </header>
  )
}

