import { create } from 'zustand'
import type { DocumentListItem, DocumentDetail, DocumentStatus, PaginatedResponse } from '../types'
import * as documentsApi from '../api/documents'

interface DocumentStore {
  // List
  documents: DocumentListItem[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  error: string | null

  // Detail
  currentDocument: DocumentDetail | null
  detailLoading: boolean
  detailError: string | null

  // Actions
  fetchDocuments: (params?: { status?: string; search?: string; page?: number }) => Promise<void>
  fetchDocument: (id: number) => Promise<void>
  updateDocument: (id: number, data: { title?: string; description?: string; status?: string }) => Promise<void>
  archiveDocument: (id: number) => Promise<void>
  clearCurrent: () => void
  clearError: () => void
}

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  // List state
  documents: [],
  total: 0,
  page: 1,
  pageSize: 10,
  loading: false,
  error: null,

  // Detail state
  currentDocument: null,
  detailLoading: false,
  detailError: null,

  // Fetch document list
  fetchDocuments: async (params) => {
    set({ loading: true, error: null })
    try {
      const searchParams: Record<string, any> = {
        page: params?.page || get().page,
        page_size: get().pageSize,
      }
      if (params?.status && params.status !== 'all') {
        searchParams.status = params.status
      }
      if (params?.search) {
        searchParams.search = params.search
      }

      const response: PaginatedResponse<DocumentListItem> =
        await documentsApi.getDocuments(searchParams)

      set({
        documents: response.items,
        total: response.total,
        page: response.page,
        pageSize: response.page_size,
        loading: false,
      })
    } catch (err: any) {
      const message =
        err?.response?.data?.detail?.message ||
        err?.message ||
        'Ошибка загрузки списка документов'
      set({ loading: false, error: message })
    }
  },

  // Fetch single document
  fetchDocument: async (id: number) => {
    set({ detailLoading: true, detailError: null, currentDocument: null })
    try {
      const doc = await documentsApi.getDocument(id)
      set({ currentDocument: doc, detailLoading: false })
    } catch (err: any) {
      const message =
        err?.response?.data?.detail?.message ||
        err?.message ||
        'Ошибка загрузки документа'
      set({ detailLoading: false, detailError: message })
    }
  },

  // Update document
  updateDocument: async (id: number, data: { title?: string; description?: string; status?: string }) => {
    try {
      const apiData: { title?: string; description?: string; status?: DocumentStatus } = {}
      if (data.title !== undefined) apiData.title = data.title
      if (data.description !== undefined) apiData.description = data.description
      if (data.status !== undefined) apiData.status = data.status as DocumentStatus
      const updated = await documentsApi.updateDocument(id, apiData)
      set({ currentDocument: updated })
      // Also update in list if present
      const docs = get().documents.map((d) =>
        d.id === id ? { ...d, ...updated, status: updated.status } : d
      )
      set({ documents: docs })
    } catch (err: any) {
      const message =
        err?.response?.data?.detail?.message ||
        err?.message ||
        'Ошибка обновления документа'
      throw new Error(message)
    }
  },

  // Archive (delete) document
  archiveDocument: async (id: number) => {
    try {
      await documentsApi.archiveDocument(id)
      const docs = get().documents.filter((d) => d.id !== id)
      set({ documents: docs, total: get().total - 1, currentDocument: null })
    } catch (err: any) {
      const message =
        err?.response?.data?.detail?.message ||
        err?.message ||
        'Ошибка архивирования документа'
      throw new Error(message)
    }
  },

  // Clear current document
  clearCurrent: () => {
    set({ currentDocument: null, detailLoading: false, detailError: null })
  },

  // Clear error
  clearError: () => {
    set({ error: null, detailError: null })
  },
}))
