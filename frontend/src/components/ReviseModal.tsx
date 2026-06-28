import { useState } from 'react'
import { Modal, Form, Input, notification } from 'antd'
import { reviseDocument } from '../api/documents'
import type { ReviseResponse } from '../types'

const { TextArea } = Input

interface ReviseModalProps {
  visible: boolean
  onClose: () => void
  documentId: number
  onSuccess: (response: ReviseResponse) => void
}

export default function ReviseModal({ visible, onClose, documentId, onSuccess }: ReviseModalProps) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      const response = await reviseDocument(documentId, {
        comment: values.comment.trim(),
        target_section: values.target_section?.trim() || undefined,
      })

      notification.success({
        message: 'Правки внесены',
        description: 'Ревизия успешно создана. Вы можете просмотреть изменения.',
      })

      form.resetFields()
      onSuccess(response)
    } catch (err: any) {
      // Validation error — ignore, Ant Design form shows inline errors
      if (err?.errorFields) return

      // Extract error message
      const httpStatus = err?.response?.status
      const detail = err?.response?.data?.detail

      if (httpStatus === 422) {
        // Validation error from backend
        const msg =
          typeof detail === 'string'
            ? detail
            : detail?.message || 'Ошибка валидации. Проверьте введённые данные.'
        notification.error({ message: 'Ошибка валидации', description: msg })
      } else {
        const msg = detail?.message || err?.message || 'Не удалось отправить правки'
        notification.error({ message: 'Ошибка', description: msg })
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = () => {
    form.resetFields()
    onClose()
  }

  return (
    <Modal
      title="Внести правки"
      open={visible}
      onOk={handleSubmit}
      onCancel={handleCancel}
      confirmLoading={submitting}
      okText="Отправить"
      cancelText="Отмена"
      destroyOnClose
      width={560}
    >
      <Form
        form={form}
        layout="vertical"
        autoComplete="off"
        style={{ marginTop: 16 }}
      >
        <Form.Item
          name="comment"
          label="Описание изменений"
          rules={[
            { required: true, message: 'Опишите, что нужно изменить' },
            { min: 10, message: 'Минимум 10 символов' },
          ]}
        >
          <TextArea
            rows={4}
            placeholder="Опишите, что нужно изменить..."
            showCount
            maxLength={2000}
          />
        </Form.Item>

        <Form.Item
          name="target_section"
          label="Целевой раздел (опционально)"
        >
          <Input
            placeholder="Например: Раздел 3 или пункт 4.2"
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
