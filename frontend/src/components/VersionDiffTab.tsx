import { useEffect, useState, useCallback } from 'react'
import { Select, Spin, Alert, Empty, Typography, Space, Descriptions, Tag, Card } from 'antd'
import ReactDiffViewer from 'react-diff-viewer-continued'
import type { DocumentVersion, DocumentDiffChange } from '../types'
import { getDocumentDiff } from '../api/versions'
import { getDocumentVersions } from '../api/documents'

const { Title, Text } = Typography

interface VersionDiffTabProps {
  documentId: number
}

export default function VersionDiffTab({ documentId }: VersionDiffTabProps) {
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)

  const [fromVersion, setFromVersion] = useState<number | null>(null)
  const [toVersion, setToVersion] = useState<number | null>(null)
  const [diffData, setDiffData] = useState<DocumentDiffChange[] | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [diffError, setDiffError] = useState<string | null>(null)

  // Load versions for selectors
  const loadVersions = useCallback(async () => {
    if (!documentId) return
    setVersionsLoading(true)
    try {
      const data = await getDocumentVersions(documentId)
      const sorted = data.items.sort((a, b) => b.version_number - a.version_number)
      setVersions(sorted)
      // Default: compare latest two versions
      if (sorted.length >= 2) {
        setFromVersion(sorted[1].version_number)
        setToVersion(sorted[0].version_number)
      } else if (sorted.length === 1) {
        setFromVersion(null)
        setToVersion(sorted[0].version_number)
      }
    } catch {
      // Silently fail
    } finally {
      setVersionsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadVersions()
  }, [loadVersions])

  // Load diff when versions change
  const loadDiff = useCallback(async () => {
    if (!documentId || !fromVersion || !toVersion || fromVersion === toVersion) {
      setDiffData(null)
      return
    }

    setDiffLoading(true)
    setDiffError(null)
    try {
      const data = await getDocumentDiff(documentId, fromVersion, toVersion)
      setDiffData(data.changes)
    } catch (err: any) {
      setDiffError(
        err?.response?.data?.detail?.message || err.message || 'Ошибка загрузки сравнения версий'
      )
    } finally {
      setDiffLoading(false)
    }
  }, [documentId, fromVersion, toVersion])

  useEffect(() => {
    loadDiff()
  }, [loadDiff])

  const versionOptions = versions.map((v) => ({
    value: v.version_number,
    label: `v${v.version_number} — ${v.version_notes || 'Без комментария'}`,
  }))

  // Detect if a field is likely a full text field (multi-line content)
  const isLongField = (field: string): boolean => {
    return ['content', 'text', 'body', 'description'].includes(field)
  }

  return (
    <div>
      {/* Version selectors */}
      {versionsLoading ? (
        <Spin style={{ display: 'block', margin: '20px auto' }} />
      ) : versions.length < 2 ? (
        <Empty
          description="Для сравнения необходимо не менее двух версий документа"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Space wrap>
              <div>
                <Text strong style={{ display: 'block', marginBottom: 4 }}>
                  Исходная версия (старая)
                </Text>
                <Select
                  style={{ width: 300 }}
                  value={fromVersion}
                  onChange={setFromVersion}
                  options={versionOptions}
                  placeholder="Выберите версию"
                />
              </div>
              <div>
                <Text strong style={{ display: 'block', marginBottom: 4 }}>
                  Сравниваемая версия (новая)
                </Text>
                <Select
                  style={{ width: 300 }}
                  value={toVersion}
                  onChange={setToVersion}
                  options={versionOptions}
                  placeholder="Выберите версию"
                />
              </div>
            </Space>

            {diffError && (
              <Alert message="Ошибка" description={diffError} type="error" showIcon />
            )}

            {diffLoading ? (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <Spin size="large" tip="Загрузка сравнения..." />
              </div>
            ) : diffData && diffData.length > 0 ? (
              <div>
                <Title level={5} style={{ marginBottom: 16 }}>
                  Результат сравнения v{fromVersion} → v{toVersion}
                </Title>

                {diffData.map((change, index) => (
                  <Card
                    key={index}
                    size="small"
                    title={
                      <Space>
                        <Tag>{change.field}</Tag>
                        {change.old_value === null && <Tag color="green">Добавлено</Tag>}
                        {change.new_value === null && <Tag color="red">Удалено</Tag>}
                      </Space>
                    }
                    style={{ marginBottom: 16 }}
                  >
                    {isLongField(change.field) ? (
                      <ReactDiffViewer
                        oldValue={change.old_value || ''}
                        newValue={change.new_value || ''}
                        splitView={true}
                        leftTitle={`v${fromVersion}`}
                        rightTitle={`v${toVersion}`}
                        showDiffOnly={false}
                      />
                    ) : (
                      <Descriptions bordered size="small" column={1}>
                        <Descriptions.Item label={`v${fromVersion} (старое)`}>
                          {change.old_value || (
                            <Text type="secondary">—</Text>
                          )}
                        </Descriptions.Item>
                        <Descriptions.Item label={`v${toVersion} (новое)`}>
                          {change.new_value || (
                            <Text type="secondary">—</Text>
                          )}
                        </Descriptions.Item>
                      </Descriptions>
                    )}
                  </Card>
                ))}
              </div>
            ) : fromVersion && toVersion && fromVersion !== toVersion ? (
              <Empty
                description="Изменения между выбранными версиями не найдены"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : null}
          </Space>
        </>
      )}
    </div>
  )
}
