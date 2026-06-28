import type { DocumentStatus } from '../types'

export const STATUS_LABELS: Record<DocumentStatus, string> = {
  draft: 'Черновик',
  review: 'На согласовании',
  approved: 'Утверждён',
  cancelled: 'Отменён',
  archived: 'Архивирован',
}

export const STATUS_COLORS: Record<DocumentStatus, string> = {
  draft: 'default',     // серый (Ant Design 'default')
  review: 'orange',     // оранжевый
  approved: 'green',    // зелёный
  cancelled: 'red',     // красный
  archived: 'default',  // серебро/серый
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
