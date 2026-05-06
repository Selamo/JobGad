import { useRef, useState, useCallback } from 'react'

export function useMicrophone() {
  const streamRef    = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const contextRef   = useRef<AudioContext | null>(null)
  const [isRecording, setIsRecording]     = useState(false)
  const [hasPermission, setHasPermission] = useState(false)

  const requestPermission = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach(t => t.stop())
      setHasPermission(true)
    } catch {
      setHasPermission(false)
      throw new Error('Microphone permission denied')
    }
  }, [])

  const startRecording = useCallback(async (onChunk: (base64: string) => void) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
    })
    streamRef.current = stream

    const context = new AudioContext({ sampleRate: 16000 })
    contextRef.current = context

    const source    = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    processorRef.current = processor

    processor.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0)
      const pcm = new Int16Array(inputData.length)
      for (let i = 0; i < inputData.length; i++) {
        pcm[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768))
      }
      const bytes  = new Uint8Array(pcm.buffer)
      let binary   = ''
      bytes.forEach(b => (binary += String.fromCharCode(b)))
      onChunk(btoa(binary))
    }

    source.connect(processor)
    processor.connect(context.destination)
    setIsRecording(true)
  }, [])

  const stopRecording = useCallback(() => {
    processorRef.current?.disconnect()
    contextRef.current?.close()
    streamRef.current?.getTracks().forEach(t => t.stop())
    processorRef.current = null
    contextRef.current   = null
    streamRef.current    = null
    setIsRecording(false)
  }, [])

  return { startRecording, stopRecording, requestPermission, isRecording, hasPermission }
}