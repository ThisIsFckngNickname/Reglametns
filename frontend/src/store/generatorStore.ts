import { create } from 'zustand'
import type { GenerateResponse, GeneratorState } from '../types'
import { generateDocument } from '../api/generator'

interface GeneratorStore {
  state: GeneratorState

  generate: (
    context: string,
    draftFiles?: File[],
    influencingDocumentIds?: number[],
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

  reset: () => set({ state: { ...initialState } }),
}))
