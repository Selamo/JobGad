import { useRef, useState, useCallback, useEffect } from 'react'

interface WSMessage {
  type: string
  data: Record<string, unknown>
  timestamp: string
}

interface Props {
  sessionId: string
  token: string
  mode?: 'audio' | 'text'
  onMessage: (msg: WSMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: string) => void
}

export function useInterviewSocket({
  sessionId, token, mode = 'audio',
  onMessage, onConnect, onDisconnect, onError,
}: Props) {
  const wsRef   = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const send = useCallback((type: string, data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }))
    }
  }, [])

  const connect = useCallback(() => {
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
    const url = `${WS_URL}/api/v1/coaching/sessions/${sessionId}/ws?token=${token}&mode=${mode}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      onConnect?.()
      pingRef.current = setInterval(() => send('ping', {}), 25000)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        onMessage(msg)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onclose = (event) => {
      setIsConnected(false)
      if (pingRef.current) clearInterval(pingRef.current)
      if (event.code === 4001)      onError?.('Session expired. Please log in again.')
      else if (event.code === 4004) onError?.('Session not found.')
      else if (event.code === 4000) onError?.('Session already completed.')
      else onDisconnect?.()
    }

    ws.onerror = () => {
      onError?.('WebSocket connection failed. Check your network.')
    }
  }, [sessionId, token, mode, onMessage, onConnect, onDisconnect, onError, send])

  const sendAudioChunk = useCallback((audioBase64: string, questionNumber: number) => {
    send('audio_chunk', { audio: audioBase64, question_number: questionNumber })
  }, [send])

  const sendTextAnswer = useCallback((answer: string, questionNumber: number, timeTaken: number) => {
    send('text_answer', { answer, question_number: questionNumber, time_taken_seconds: timeTaken })
  }, [send])

  const endSession = useCallback(() => send('end_session', {}), [send])

  const disconnect = useCallback(() => {
    if (pingRef.current) clearInterval(pingRef.current)
    wsRef.current?.close()
  }, [])

  useEffect(() => {
    return () => {
      if (pingRef.current) clearInterval(pingRef.current)
      wsRef.current?.close()
    }
  }, [])

  return { connect, disconnect, sendAudioChunk, sendTextAnswer, endSession, isConnected }
}