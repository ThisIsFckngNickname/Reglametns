import { useEffect, useState, useCallback, useRef } from 'react'
import { Input, Select, Card, List, Tag, Typography, Space, Spin, Alert, Pagination, Empty, Breadcrumb, Button, Tooltip } from 'antd'
import { SearchOutlined, LinkOutlined, FileTextOutlined, ArrowLeftOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { LegislationItem, AvailableSource } from '../types'
import { searchLegislation, getAvailableSources } from '../api/legislation'

const { Text, Title, Paragraph } = Typography

type PageState = 'idle' | 'loading' | 'results' | 'empty' | 'error'

// Map source IDs to display labels
const SOURCE_LABELS: Record<string, string> = {
  pravo_gov_ru: 'Pravo.gov.ru',
  docs_cntd_ru: 'Техэксперт (docs.cntd.ru)',
  consultant_plus: 'Консультант+',
  garant: 'Гарант',
}

function getSourceLabel(sourceId: string): string {
  return SOURCE_LABELS[sourceId] || sourceId
}

// Map source IDs to human-readable result source names
function getResultSourceBadge(source: string): { label: string; color: string } {
  switch (source) {
    case 'pravo.gov.ru':
      return { label: 'Pravo.gov.ru', color: 'blue' }
    case 'docs.cntd.ru':
      return { label: 'Техэксперт', color: 'cyan' }
    default:
      return { label: source, color: 'default' }
  }
}

export default function LegislationSearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [source, setSource] = useState<string | undefined>(undefined)
  const [availableSources, setAvailableSources] = useState<AvailableSource[]>([])
  const [items, setItems] = useState<LegislationItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageState, setPageState] = useState<PageState>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [sourcesLoading, setSourcesLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load available sources on mount
  useEffect(() => {
    setSourcesLoading(true)
    getAvailableSources()
      .then((data) => setAvailableSources(data))
      .catch(() => {
        // Silently fail — sources are optional for the search
      })
      .finally(() => setSourcesLoading(false))
  }, [])

  // Debounce query input
  const handleQueryChange = useCallback((value: string) => {
    setQuery(value)
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(value)
      setPage(1)
    }, 300)
  }, [])

  // Trigger search immediately (on Enter / button click)
  const handleSearch = useCallback((value: string) => {
    setQuery(value)
    setDebouncedQuery(value)
    setPage(1)
  }, [])

  // Perform search when debounced query, source, or page changes
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 3) {
      setItems([])
      setTotal(0)
      setPageState(debouncedQuery.length > 0 ? 'idle' : 'idle')
      return
    }

    let cancelled = false
    setPageState('loading')

    searchLegislation(debouncedQuery, source, page)
      .then((data) => {
        if (cancelled) return
        setItems(data.items)
        setTotal(data.total)
        setPageState(data.items.length === 0 ? 'empty' : 'results')
      })
      .catch((err) => {
        if (cancelled) return
        setErrorMessage(err?.response?.data?.detail?.message || err.message || 'Ошибка при поиске')
        setPageState('error')
      })

    return () => {
      cancelled = true
    }
  }, [debouncedQuery, source, page])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  // Build source options from available sources
  const sourceOptions = availableSources
    .filter((s) => s.is_active || !s.is_paid) // Show active sources + non-paid that aren't active
    .map((s) => ({
      value: s.id,
      label: s.display_name,
      disabled: !s.is_active && s.is_paid,
    }))

  return (
    <div style={{ padding: 24 }}>
      {/* Breadcrumbs */}
      <Breadcrumb
        items={[
          {
            title: (
              <span onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                Главная
              </span>
            ),
          },
          {
            title: 'Поиск законодательства',
          },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        На главную
      </Button>

      <Title level={3} style={{ marginBottom: 8 }}>
        <SearchOutlined style={{ marginRight: 8 }} />
        Поиск законодательства
      </Title>
      <Paragraph type="secondary" style={{ marginBottom: 24 }}>
        Поиск нормативных правовых актов Российской Федерации
      </Paragraph>

      {/* Search bar */}
      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Input.Search
            size="large"
            placeholder="Введите поисковый запрос (минимум 3 символа)..."
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onSearch={handleSearch}
            enterButton={<><SearchOutlined /> Поиск</>}
            aria-label="Поиск законодательства"
          />

          <Space>
            <Text strong>Источник:</Text>
            <Select
              style={{ width: 260 }}
              value={source}
              onChange={(val) => {
                setSource(val)
                setPage(1)
              }}
              loading={sourcesLoading}
              allowClear
              placeholder="Все активные источники"
              aria-label="Выбор источника"
            >
              <Select.Option value="">Все активные источники</Select.Option>
              {sourceOptions.map((opt) => {
                const src = availableSources.find((s) => s.id === opt.value)
                return (
                  <Select.Option key={opt.value} value={opt.value} disabled={opt.disabled}>
                    <Space>
                      <span>{opt.label}</span>
                      {src?.is_paid && (
                        <Tooltip title="Платный источник">
                          <LockOutlined style={{ color: '#faad14' }} />
                        </Tooltip>
                      )}
                      {src?.is_paid && (
                        <Tag color="gold" style={{ fontSize: 10, lineHeight: '16px' }}>платно</Tag>
                      )}
                      {opt.disabled && (
                        <Text type="secondary" style={{ fontSize: 11 }}>(не активен)</Text>
                      )}
                    </Space>
                  </Select.Option>
                )
              })}
            </Select>
          </Space>
        </Space>
      </Card>

      {/* Content area */}
      {pageState === 'idle' && (
        <Card>
          <Empty
            description="Введите поисковый запрос для поиска законодательства"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      )}

      {pageState === 'loading' && (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" tip="Поиск..." />
        </div>
      )}

      {pageState === 'error' && (
        <Alert
          message="Ошибка поиска"
          description={errorMessage}
          type="error"
          showIcon
          closable
          onClose={() => setPageState('idle')}
        />
      )}

      {pageState === 'empty' && (
        <Card>
          <Empty
            description={
              <span>
                По запросу «<Text strong>{debouncedQuery}</Text>» ничего не найдено.
                Попробуйте изменить поисковый запрос.
              </span>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      )}

      {pageState === 'results' && (
        <>
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              Найдено: {total} документов по запросу «{debouncedQuery}»
              {source ? ` (источник: ${getSourceLabel(source)})` : ''}
            </Text>
          </div>

          <List
            dataSource={items}
            rowKey={(item: LegislationItem) => `${item.url}-${item.title}`}
            renderItem={(item: LegislationItem) => {
              const badge = getResultSourceBadge(item.source)
              return (
                <List.Item>
                  <Card
                    style={{ width: '100%' }}
                    hoverable
                    size="small"
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <Space align="center" style={{ marginBottom: 8 }}>
                          <FileTextOutlined style={{ color: '#1890ff' }} />
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontSize: 16, fontWeight: 500 }}
                          >
                            {item.title}
                          </a>
                        </Space>

                        <div style={{ marginBottom: 8 }}>
                          <Space size="middle">
                            {item.number && (
                              <Text>
                                <Text strong>№ </Text>
                                {item.number}
                              </Text>
                            )}
                            {item.date && (
                              <Text type="secondary">{item.date}</Text>
                            )}
                            <Tag color={badge.color}>{badge.label}</Tag>
                          </Space>
                        </div>

                        <Paragraph
                          type="secondary"
                          ellipsis={{ rows: 2 }}
                          style={{ marginBottom: 0 }}
                        >
                          {item.snippet}
                        </Paragraph>
                      </div>

                      <Button
                        type="link"
                        icon={<LinkOutlined />}
                        href={item.url}
                        target="_blank"
                        style={{ flexShrink: 0, marginLeft: 16 }}
                      >
                        Открыть
                      </Button>
                    </div>
                  </Card>
                </List.Item>
              )
            }}
          />

          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <Pagination
              current={page}
              total={total}
              pageSize={10}
              onChange={handlePageChange}
              showSizeChanger={false}
              showTotal={(total) => `Всего: ${total} документов`}
            />
          </div>
        </>
      )}
    </div>
  )
}
