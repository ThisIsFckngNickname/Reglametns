import { create } from 'zustand'
import type { GenerateResponse, GeneratorState } from '../types'
import { generateDocument, generateDocumentV2 } from '../api/generator'
import type { GenerateV2Request } from '../api/generator'

interface GeneratorStore {
  state: GeneratorState

  generate: (
    context: string,
    draftFiles?: File[],
    influencingDocumentIds?: number[],
  ) => Promise<void>

  generateV2: (
    data: GenerateV2Request,
  ) => Promise<void>

  reset: () => void
}

const initialState: GeneratorState = {
  step: 'form',
  progress: 0,
  message: '',
  result: null,
  error: null,
}

export const useGeneratorStore = create<GeneratorStore>((set) => ({
  state: { ...initialState },

  generate: async (context, draftFiles, influencingDocumentIds) => {
    set({ state: { step: 'preparing', progress: 5, message: 'Подготовка данных...', result: null, error: null } })

    try {
      const result = await generateDocument(
        context,
        draftFiles,
        influencingDocumentIds,
        (step, percent) => {
          const messages: Record<string, string> = {
            preparing: 'Анализ контекста и профиля холдинга...',
            generating: 'Генерация текста через нейросеть...',
            formatting: 'Оформление документа в Word...',
          }
          set({ state: { step: step as GeneratorState['step'], progress: percent, message: messages[step] || '...', result: null, error: null } })
        },
      )

      set({ state: { step: 'done', progress: 100, message: 'Документ готов!', result, error: null } })
    } catch (err: any) {
      set({ state: { step: 'error', progress: 0, message: '', result: null, error: err.message || 'Ошибка генерации' } })
    }
  },

  generateV2: async (data) => {
    set({ state: { step: 'preparing', progress: 2, message: 'Подготовка данных...', result: null, error: null } })

    try {
      // Simulate V2 extended steps progress
      const stepMessages: Record<string, string> = {
        preparing: 'Подготовка контекста и профиля холдинга...',
        searching: 'Поиск информации в интернете...',
        analyzing: 'Анализ документов компании...',
        generating: 'Генерация текста через нейросеть...',
        formatting: 'Оформление документа в Word...',
      }

      // We simulate the flow since the backend doesn't send SSE events
      set({ state: { step: 'preparing', progress: 10, message: stepMessages.preparing, result: null, error: null } })

      let progressTimer: ReturnType<typeof setInterval> | null = null

      if (data.search_enabled !== false) {
        set({ state: { step: 'searching', progress: 20, message: stepMessages.searching, result: null, error: null } })
      }

      set({ state: { step: 'analyzing', progress: 35, message: stepMessages.analyzing, result: null, error: null } })

      // Start progress animation
      if (!progressTimer) {
        progressTimer = setInterval(() => {
          set((s) => {
            if (s.state.step === 'generating' && s.state.progress < 80) {
              return { state: { ...s.state, progress: Math.min(s.state.progress + 2, 80) } }
            }
            return s
          })
        }, 1000)
      }

      set({ state: { step: 'generating', progress: 50, message: stepMessages.generating, result: null, error: null } })

      // Small delay to show generating state
      await new Promise((r) => setTimeout(r, 500))

      const result = await generateDocumentV2(data, (step, percent) => {
        const msg = stepMessages[step] || '...'
        set({ state: { step: step as GeneratorState['step'], progress: percent, message: msg, result: null, error: null } })
      })

      if (progressTimer) clearInterval(progressTimer)

      set({ state: { step: 'done', progress: 100, message: 'Документ готов!', result, error: null } })
    } catch (err: any) {
      set({ state: { step: 'error', progress: 0, message: '', result: null, error: err?.response?.data?.detail?.message || err.message || 'Ошибка генерации' } })
    }
  },

  reset: () => set({ state: { ...initialState } }),
}))
