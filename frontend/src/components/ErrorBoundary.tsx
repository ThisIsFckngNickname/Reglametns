import { Component, ErrorInfo, ReactNode } from 'react'
import { Button, Result, Typography, Space } from 'antd'

const { Paragraph, Text } = Typography

interface ErrorBoundaryProps {
  children: ReactNode
  /** Optional custom fallback UI */
  fallback?: ReactNode
  title?: string
  description?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

/**
 * React Error Boundary — catches render errors and shows a fallback UI
 * instead of crashing the entire app.
 *
 * Use:
 *   <ErrorBoundary>
 *     <YourComponent />
 *   </ErrorBoundary>
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo })
    // Log error to console for debugging
    console.error('[ErrorBoundary] Caught error:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      // If a custom fallback was provided, use it
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div style={{ padding: 48, maxWidth: 600, margin: '0 auto' }}>
          <Result
            status="error"
            title={this.props.title || 'Что-то пошло не так'}
            subTitle={
              this.props.description ||
              'При загрузке страницы произошла ошибка. Пожалуйста, попробуйте перезагрузить.'
            }
            extra={
              <Space>
                <Button type="primary" onClick={this.handleReload}>
                  Перезагрузить страницу
                </Button>
                <Button onClick={this.handleReset}>
                  Попробовать снова
                </Button>
              </Space>
            }
          >
            {this.state.error && (
              <div style={{ marginTop: 16 }}>
                <Text type="danger" strong>
                  Детали ошибки (для разработчика):
                </Text>
                <Paragraph
                  code
                  style={{
                    padding: 12,
                    background: '#f5f5f5',
                    borderRadius: 4,
                    marginTop: 8,
                    maxHeight: 200,
                    overflow: 'auto',
                    fontSize: 12,
                  }}
                >
                  {this.state.error.name}: {this.state.error.message}
                  {'stack' in this.state.error && (
                    <>
                      <br />
                      {this.state.error.stack}
                    </>
                  )}
                </Paragraph>
              </div>
            )}
          </Result>
        </div>
      )
    }

    return this.props.children
  }
}
