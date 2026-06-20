import { useEffect, useRef, useCallback, useState } from 'react'
import { Spin, Alert, Empty, Typography, Tag } from 'antd'
import cytoscape, { Core, EventObject, StylesheetStyle } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import type { ImpactGraph as ImpactGraphData } from '../types'
import { getImpactGraph } from '../api/impact'

// Register dagre layout
cytoscape.use(dagre)

const { Text } = Typography

const EDGE_COLORS: Record<string, string> = {
  amends: '#1890ff',
  references: '#52c41a',
  supersedes: '#fa8c16',
  related: '#8c8c8c',
  cancels: '#ff4d4f',
  default: '#8c8c8c',
}

const EDGE_LABELS: Record<string, string> = {
  amends: 'Изменяет',
  references: 'Ссылается',
  supersedes: 'Заменяет',
  related: 'Связан',
  cancels: 'Отменяет',
}

interface ImpactGraphProps {
  documentId: number
}

type CyNode = cytoscape.NodeSingular
type CyEdge = cytoscape.EdgeSingular

export default function ImpactGraph({ documentId }: ImpactGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [graphData, setGraphData] = useState<ImpactGraphData | null>(null)
  const [selectedNode, setSelectedNode] = useState<{
    id: string
    label: string
    type: string
  } | null>(null)

  const loadGraph = useCallback(async () => {
    if (!documentId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getImpactGraph(documentId)
      setGraphData(data)
    } catch (err: any) {
      setError(
        err?.response?.data?.detail?.message || err.message || 'Ошибка загрузки графа влияний'
      )
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadGraph()
  }, [loadGraph])

  // Initialize cytoscape when graph data changes
  useEffect(() => {
    if (!graphData || !containerRef.current) return

    // Destroy previous instance
    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: CyNode) => {
              const nodeType = ele.data('type')
              return nodeType === 'order' ? '#722ed1' : '#1890ff'
            },
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'font-size': '11px',
            'text-wrap': 'ellipsis',
            'text-max-width': '120px',
            color: '#333',
            width: 40,
            height: 40,
            'border-color': '#fff',
            'border-width': 2,
            'overlay-padding': '6px',
          } as any,
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#faad14',
            'border-width': 3,
            'shadow-blur': 10,
            'shadow-color': '#faad14',
            'shadow-opacity': 0.5,
          } as any,
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': (ele: CyEdge) => EDGE_COLORS[ele.data('type')] || EDGE_COLORS.default,
            'target-arrow-color': (ele: CyEdge) =>
              EDGE_COLORS[ele.data('type')] || EDGE_COLORS.default,
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.2,
            'curve-style': 'bezier',
            label: (ele: CyEdge) => EDGE_LABELS[ele.data('type')] || ele.data('type'),
            'font-size': '9px',
            color: '#666',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
            'control-point-step-size': 40,
          } as any,
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#faad14',
            'target-arrow-color': '#faad14',
            width: 3,
          } as any,
        },
      ],
      layout: {
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 60,
        rankSep: 120,
        animate: true,
        animationDuration: 300,
        padding: 30,
      } as any,
      elements: [
        // Nodes
        ...graphData.nodes.map((n) => ({
          data: { id: n.id, label: n.label, type: n.type },
        })),
        // Edges
        ...graphData.edges.map((e, i) => ({
          data: {
            id: `edge-${i}`,
            source: e.source,
            target: e.target,
            label: e.label,
            type: e.type,
          },
        })),
      ] as any,
    })

    // Handle node selection
    cy.on('tap', 'node', (evt: EventObject) => {
      const node = evt.target
      const data = node.data()
      setSelectedNode({
        id: data.id,
        label: data.label,
        type: data.type,
      })
    })

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        setSelectedNode(null)
      }
    })

    // Add tooltips on hover
    cy.on('mouseover', 'node', (_evt: EventObject) => {
      document.getElementById('cy-container')?.style.setProperty('cursor', 'pointer')
    })

    cy.on('mouseout', 'node', (_evt: EventObject) => {
      document.getElementById('cy-container')?.style.setProperty('cursor', 'default')
    })

    cyRef.current = cy

    // Fit to container
    cy.fit(undefined, 30)

    // Cleanup on unmount
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [graphData])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0' }}>
        <Spin size="large" tip="Загрузка графа влияний..." />
      </div>
    )
  }

  if (error) {
    return <Alert message="Ошибка" description={error} type="error" showIcon />
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <Empty
        description="Нет данных для построения графа влияний"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    )
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">
          Интерактивный граф влияний. Перетаскивайте узлы, используйте колесо мыши для
          масштабирования.
        </Text>
      </div>

      <div
        id="cy-container"
        style={{
          position: 'relative',
          width: '100%',
          height: 480,
          border: '1px solid #f0f0f0',
          borderRadius: 4,
          background: '#fafafa',
          overflow: 'hidden',
        }}
      >
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

        {/* Legend */}
        <div
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            background: 'rgba(255,255,255,0.9)',
            padding: '8px 12px',
            borderRadius: 4,
            fontSize: 12,
            border: '1px solid #f0f0f0',
            zIndex: 10,
          }}
        >
          <div style={{ marginBottom: 4 }}>
            <Tag color="#1890ff">Документ</Tag>
            <Tag color="#722ed1">Приказ</Tag>
          </div>
          <div style={{ color: '#666' }}>
            {Object.entries(EDGE_LABELS).map(([key, label]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 16,
                    height: 2,
                    background: EDGE_COLORS[key],
                    verticalAlign: 'middle',
                  }}
                />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Selected node info */}
      {selectedNode && (
        <div style={{ marginTop: 12, padding: 12, background: '#fafafa', borderRadius: 4 }}>
          <Text strong>Выбранный элемент: </Text>
          <Tag color={selectedNode.type === 'order' ? 'purple' : 'blue'}>
            {selectedNode.type === 'order' ? 'Приказ' : 'Документ'}
          </Tag>
          <Text>{selectedNode.label}</Text>
        </div>
      )}
    </div>
  )
}
