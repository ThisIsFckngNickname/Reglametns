import { create } from 'zustand'
import type { UserProfile } from '../types'
import { refreshAccessToken, logoutUser, getCurrentUser } from '../api/auth'

interface AuthStore {
  accessToken: string | null
  user: UserProfile | null
  isAuthenticated: boolean
  isLoading: boolean

  setTokens: (access: string) => void
  setUser: (user: UserProfile) => void
  updateUser: (updates: Partial<UserProfile>) => void
  logout: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthStore>((set) => ({
  accessToken: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,

  setTokens: (access: string) => {
    localStorage.setItem('access_token', access)
    set({
      accessToken: access,
      isAuthenticated: true,
      isLoading: false,
    })
  },

  setUser: (user: UserProfile) => {
    set({ user, isAuthenticated: true, isLoading: false })
  },

  updateUser: (updates: Partial<UserProfile>) => {
    set((state) => ({
      user: state.user ? { ...state.user, ...updates } : null,
    }))
  },

  logout: async () => {
    try {
      await logoutUser()
    } catch {
      // Ignore logout API errors — we clear local state anyway
    }
    localStorage.removeItem('access_token')
    set({
      accessToken: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
    })
  },

  initialize: async () => {
    set({ isLoading: true })
    try {
      // Try to refresh the access token using the httpOnly refresh cookie.
      // If the user has a valid session, the cookie is sent automatically.
      const { access_token } = await refreshAccessToken()
      localStorage.setItem('access_token', access_token)
      set({ accessToken: access_token, isAuthenticated: true })

      // Fetch user profile
      const user = await getCurrentUser()
      set({ user, isLoading: false })
    } catch {
      // No valid session — clear everything
      localStorage.removeItem('access_token')
      set({
        accessToken: null,
        user: null,
        isAuthenticated: false,
        isLoading: false,
      })
    }
  },
}))
