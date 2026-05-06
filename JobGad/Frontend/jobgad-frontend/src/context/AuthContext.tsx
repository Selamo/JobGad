'use client'
import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { auth, saveTokens, clearTokens, type User } from '@/lib/api'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType>({
  user: null, loading: true,
  login: async () => {}, logout: () => {}, refresh: async () => {},
  isAuthenticated: false,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) { setLoading(false); return }
      const me = await auth.me()
      setUser(me)
    } catch {
      clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchMe() }, [fetchMe])

  const login = async (email: string, password: string) => {
    const data = await auth.login(email, password)
    saveTokens(data.access_token, data.refresh_token)
    const me = await auth.me()
    setUser(me)
  }

  const logout = () => {
    clearTokens()
    setUser(null)
    window.location.href = '/login'
  }

  const refresh = async () => {
    setLoading(true)
    await fetchMe()
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)