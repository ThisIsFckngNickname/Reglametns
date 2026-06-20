import apiClient from './client'
import type { Order, OrderDocumentLink, PaginatedResponse } from '../types'

export async function uploadOrder(
  file: File,
  title: string,
  orderNumber?: string,
  orderDate?: string,
  description?: string,
  onProgress?: (percent: number) => void
): Promise<Order> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', title)
  if (orderNumber) formData.append('order_number', orderNumber)
  if (orderDate) formData.append('order_date', orderDate)
  if (description) formData.append('description', description)

  const response = await apiClient.post('/orders/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total))
      }
    },
  })
  return response.data
}

export async function getOrders(params?: {
  status?: string
  page?: number
  page_size?: number
}): Promise<PaginatedResponse<Order>> {
  const response = await apiClient.get('/orders', { params })
  return response.data
}

export async function getOrder(id: number): Promise<Order> {
  const response = await apiClient.get(`/orders/${id}`)
  return response.data
}

export async function updateOrder(
  id: number,
  data: { title?: string; order_number?: string; order_date?: string; description?: string }
): Promise<Order> {
  const response = await apiClient.put(`/orders/${id}`, data)
  return response.data
}

export async function cancelOrder(id: number): Promise<void> {
  await apiClient.delete(`/orders/${id}`)
}

export async function getOrderDocuments(orderId: number): Promise<{ items: OrderDocumentLink[] }> {
  const response = await apiClient.get(`/orders/${orderId}/documents`)
  return response.data
}

export async function linkOrderToDocument(
  orderId: number,
  documentId: number,
  linkType: string,
  description?: string
): Promise<OrderDocumentLink> {
  const response = await apiClient.post(`/orders/${orderId}/documents`, {
    document_id: documentId,
    link_type: linkType,
    description,
  })
  return response.data
}

export async function unlinkOrderFromDocument(orderId: number, linkId: number): Promise<void> {
  await apiClient.delete(`/orders/${orderId}/documents/${linkId}`)
}
