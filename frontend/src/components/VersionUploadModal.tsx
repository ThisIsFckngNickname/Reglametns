import { useState } from 'react'
import { Modal, Upload, Input, Button, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { createVersion } from '../api/documents'

const { Dragger } = Upload

interface VersionUploadModalProps {
  visible: boolean
  onClose: () => void
  documentId: number
  onSuccess: () => void
}

export default function VersionUploadModal({
  visible,
  onClose,
  documentId,
  onSuccess,
}: VersionUploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [comment, setComment] = useState('')
  const [uploading, setUploading] = useState(false)

  const handleUpload = async () => {
    if (!file) {
      message.warning('Выберите файл')
      return
    }

    setUploading(true)
    try {
      await createVersion(documentId, file, comment || undefined)
      message.success('Новая версия загружена')
      setFile(null)
      setComment('')
      onClose()
      onSuccess()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Ошибка загрузки версии')
    } finally {
      setUploading(false)
    }
  }

  return (
    <Modal
      title="Загрузить новую версию"
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>Отмена</Button>,
        <Button
          key="upload"
          type="primary"
          loading={uploading}
          onClick={handleUpload}
          disabled={!file}
        >
          Загрузить
        </Button>,
      ]}
      destroyOnClose
    >
      <Dragger
        beforeUpload={(f) => {
          setFile(f)
          return false
        }}
        onRemove={() => setFile(null)}
        fileList={file ? [file as any] : []}
        accept=".docx,.pdf,.doc"
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">Нажмите или перетащите файл сюда</p>
        <p className="ant-upload-hint">.docx, .pdf</p>
      </Dragger>

      <Input.TextArea
        style={{ marginTop: 16 }}
        placeholder="Комментарий к версии (опционально)"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
      />
    </Modal>
  )
}
