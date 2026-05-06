import { useRef, useCallback } from 'react'

export function useAudioPlayer() {
  const contextRef   = useRef<AudioContext | null>(null)
  const queueRef     = useRef<AudioBuffer[]>([])
  const isPlayingRef = useRef(false)

  function getContext(): AudioContext {
    if (!contextRef.current || contextRef.current.state === 'closed') {
      contextRef.current = new AudioContext({ sampleRate: 24000 })
    }
    return contextRef.current
  }

  function base64ToPCM(base64: string): number[] {
    const binary = atob(base64)
    const bytes  = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    const result: number[] = []
    for (let i = 0; i < bytes.length - 1; i += 2) {
      const val    = (bytes[i + 1] << 8) | bytes[i]
      const signed = val >= 0x8000 ? val - 0x10000 : val
      result.push(signed / 32768)
    }
    return result
  }

  const playNext = useCallback(() => {
    if (queueRef.current.length === 0) {
      isPlayingRef.current = false
      return
    }
    isPlayingRef.current = true
    const context = getContext()
    const buffer  = queueRef.current.shift()!
    const source  = context.createBufferSource()
    source.buffer = buffer
    source.connect(context.destination)
    source.onended = playNext
    source.start()
  }, [])

  const enqueueAudio = useCallback((base64: string) => {
    try {
      const context = getContext()
      const samples = base64ToPCM(base64)
      const buffer  = context.createBuffer(1, samples.length, 24000)
      const channel = buffer.getChannelData(0)
      for (let i = 0; i < samples.length; i++) channel[i] = samples[i]
      queueRef.current.push(buffer)
      if (!isPlayingRef.current) playNext()
    } catch (e) {
      console.error('Audio enqueue error:', e)
    }
  }, [playNext])

  const stopAudio = useCallback(() => {
    queueRef.current     = []
    isPlayingRef.current = false
    try { contextRef.current?.close() } catch { }
    contextRef.current = null
  }, [])

  return { enqueueAudio, stopAudio }
}