import { useState, useCallback } from 'react'

// Image paths based on the actual filenames in the directory
// Using processed versions (will fallback to originals if processed don't exist)
const IMAGE_PATHS = [
  '/8bit-roleplaycards/1 - 55JZX.png', '/8bit-roleplaycards/2 - pxgJr.png', '/8bit-roleplaycards/3 - 9MEgE.png',
  '/8bit-roleplaycards/4 - 2rslo.png', '/8bit-roleplaycards/5 - ul4bE.png', '/8bit-roleplaycards/6 - VEmG7.png',
  '/8bit-roleplaycards/7 - sEUef.png', '/8bit-roleplaycards/8 - sHFit.png', '/8bit-roleplaycards/9 - 6EQw1.png',
  '/8bit-roleplaycards/10 - dKeo2.png', '/8bit-roleplaycards/11 - syhqc.png', '/8bit-roleplaycards/12 - rz1mw.png',
  '/8bit-roleplaycards/13 - uhzHA.png', '/8bit-roleplaycards/14 - AdWC5.png', '/8bit-roleplaycards/15 - 1bkFH.png',
  '/8bit-roleplaycards/16 - w92Em.png', '/8bit-roleplaycards/17 - jY9vI.png', '/8bit-roleplaycards/18 - kqjgI.png',
  '/8bit-roleplaycards/19 - wy4FB.png', '/8bit-roleplaycards/20 - EL273.png', '/8bit-roleplaycards/21 - LgO08.png',
  '/8bit-roleplaycards/22 - JQaJt.png', '/8bit-roleplaycards/23 - gZ8VF.png', '/8bit-roleplaycards/24 - 3YMfC.png',
  '/8bit-roleplaycards/25 - BkyXg.png', '/8bit-roleplaycards/26 - Sw8ju.png', '/8bit-roleplaycards/27 - iRu0N.png',
  '/8bit-roleplaycards/28 - w95Ez.png', '/8bit-roleplaycards/29 - p2TLi.png', '/8bit-roleplaycards/30 - 3vGLA.png',
  '/8bit-roleplaycards/31 - bo8Md.png', '/8bit-roleplaycards/32 - cq6l8.png', '/8bit-roleplaycards/33 - G9eyz.png',
  '/8bit-roleplaycards/34 - wbEvr.png', '/8bit-roleplaycards/35 - wRyzU.png', '/8bit-roleplaycards/36 - Xq43Y.png',
  '/8bit-roleplaycards/37 - OEod0.png', '/8bit-roleplaycards/38 - IJ3od.png', '/8bit-roleplaycards/39 - 5vy3B.png',
  '/8bit-roleplaycards/40 - scGH8.png', '/8bit-roleplaycards/41 - J6qka.png', '/8bit-roleplaycards/42 - gqJ7U.png',
  '/8bit-roleplaycards/43 - 94TsH.png', '/8bit-roleplaycards/44 - hCUoy.png', '/8bit-roleplaycards/45 - c7Wi7.png',
  '/8bit-roleplaycards/46 - EGqvQ.png', '/8bit-roleplaycards/47 - K6nfa.png', '/8bit-roleplaycards/48 - y9koT.png',
  '/8bit-roleplaycards/49 - 542dN.png', '/8bit-roleplaycards/50 - OhYb8.png', '/8bit-roleplaycards/51 - UiXm0.png',
  '/8bit-roleplaycards/52 - r6w7h.png', '/8bit-roleplaycards/53 - ixxtY.png', '/8bit-roleplaycards/54 - kXelA.png',
  '/8bit-roleplaycards/55 - Tq2BI.png', '/8bit-roleplaycards/56 - 0xrgr.png', '/8bit-roleplaycards/57 - Pirqh.png',
  '/8bit-roleplaycards/58 - zfiSP.png', '/8bit-roleplaycards/59 - 8w17A.png', '/8bit-roleplaycards/60 - ChvnU.png',
  '/8bit-roleplaycards/61 - b9rTQ.png', '/8bit-roleplaycards/62 - nTahQ.png', '/8bit-roleplaycards/63 - 0sbVx.png',
  '/8bit-roleplaycards/64 - 1UmxO.png', '/8bit-roleplaycards/65 - KSnD8.png', '/8bit-roleplaycards/66 - 2i68U.png',
  '/8bit-roleplaycards/67 - h0PZk.png', '/8bit-roleplaycards/68 - LtjjL.png', '/8bit-roleplaycards/69 - xOOht.png',
  '/8bit-roleplaycards/70 - ofxWS.png', '/8bit-roleplaycards/71 - ueigD.png', '/8bit-roleplaycards/72 - BZlOQ.png',
  '/8bit-roleplaycards/73 - bDjXr.png', '/8bit-roleplaycards/74 - IbSsz.png', '/8bit-roleplaycards/75 - hSQLd.png',
  '/8bit-roleplaycards/76 - mcIZp.png', '/8bit-roleplaycards/77 - lgYRE.png', '/8bit-roleplaycards/78 - AZuRm.png',
  '/8bit-roleplaycards/79 - tWiJe.png', '/8bit-roleplaycards/80 - t5RUa.png',
  // Excluded 81 - RFKVq.png (summary/sprite sheet image)
]

export function useHeaderImages() {
  const [images, setImages] = useState<[string, string]>(() => getRandomPair())

  const refreshImages = useCallback(() => {
    setImages(prevImages => {
      let newImages: [string, string]
      do {
        newImages = getRandomPair()
      } while (
        // Never same as previous pair
        (newImages[0] === prevImages[0] && newImages[1] === prevImages[1]) ||
        (newImages[0] === prevImages[1] && newImages[1] === prevImages[0]) ||
        // Never same image twice at the same time
        newImages[0] === newImages[1]
      )
      return newImages
    })
  }, [])

  return { images, refreshImages }
}

function getRandomPair(): [string, string] {
  const indices = Array.from({ length: IMAGE_PATHS.length }, (_, i) => i)
  const shuffled = indices.sort(() => Math.random() - 0.5)
  const first = IMAGE_PATHS[shuffled[0]]
  let second = IMAGE_PATHS[shuffled[1]]
  
  // Ensure they're different
  if (first === second && shuffled.length > 2) {
    second = IMAGE_PATHS[shuffled[2]]
  }
  
  return [first, second]
}
