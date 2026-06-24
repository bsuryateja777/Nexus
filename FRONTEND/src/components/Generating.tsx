import { useState, useEffect, useMemo } from 'react'
import './Generating.css'

const generatingTexts = [
  'Thinking...',
  'Processing...',
  'Analyzing...',
  'Generating...',
  'Working on it...',
  'Drafting...',
  'Composing...',
  'Reasoning...',
]

const icons = ['꩜', '▚', ' 𖦹', '☁︎', ' 𒀭', 'ᨒ', '╰➤', '𖤣𖤥𖠿𖤣𖤣', '✿', '⌇!!', '✎༄', '֍', ' 𔐬', '𓈈', '⊹', '〨', '𓂃𓊝', '*', '≛', '𖧧', '₆⁶₆', 'ஃ', '⿻', '❈', 'ʚïɞ']
const randomChars = ['▮', '▯', '_', '█', '░', '▓', '◆', '○', '◊', '▲']

const getRandomChar = () => randomChars[Math.floor(Math.random() * randomChars.length)]

export default function Generating() {
  const [textIndex, setTextIndex] = useState(0)
  const [displayedText, setDisplayedText] = useState('')
  const [progress, setProgress] = useState(0)

  const { currentText, currentIcon } = useMemo(() => {
    const getRandomIndex = (length: number) => Math.floor(Math.random() * length)
    return {
      currentText: generatingTexts[getRandomIndex(generatingTexts.length)],
      currentIcon: icons[getRandomIndex(icons.length)],
    }
  }, [textIndex])

  useEffect(() => {
    setDisplayedText('')
    setProgress(0)
    let charIndex = 0
    let randomCharsMap: Record<number, string> = {}

    const typeInterval = setInterval(() => {
      if (charIndex < currentText.length) {
        // Main text with scrambling effect
        let newText = ''
        const charProbability = 0.4
        for (let i = 0; i < currentText.length; i++) {
          if (i < charIndex + 1) {
            newText += currentText[i]
          } else {
            if (Math.random() < charProbability) {
              if (!randomCharsMap[i]) {
                randomCharsMap[i] = getRandomChar()
              }
              newText += randomCharsMap[i]
            } else {
              newText += ' '
            }
          }
        }
        setDisplayedText(newText)
        setProgress((charIndex / currentText.length) * 100)
        charIndex++
      } else {
        clearInterval(typeInterval)
        setTimeout(() => {
          setTextIndex((prev) => (prev + 1) % generatingTexts.length)
        }, 1200)
      }
    }, 45)

    return () => clearInterval(typeInterval)
  }, [textIndex, currentText])

  return (
    <div className="generating-container">
      <div className="generating-message group flex items-start justify-start gap-2 px-3 py-2 text-sm">
        <span className="generating-icon mt-1">{currentIcon}</span>
        <div className="generating-content">
          <div className="generating-text">
            {displayedText}
            <span className="generating-cursor" />
          </div>
          <div className="generating-progress">
            <div
              className="progress-bar"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
