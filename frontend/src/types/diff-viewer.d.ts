declare module 'react-diff-viewer-continued' {
  import { CSSProperties, ReactNode } from 'react'

  export interface DiffMethod {
    diffWords: string
    diffWordsWithSpace: string
    diffLines: string
    diffTrimmedLines: string
    diffSentences: string
    diffChars: string
    diffCss: string
  }

  export interface ReactDiffViewerProps {
    oldValue: string
    newValue: string
    splitView?: boolean
    leftTitle?: string
    rightTitle?: string
    showDiffOnly?: boolean
    extraLinesSurroundingDiff?: number
    styles?: {
      diffContainer?: CSSProperties
      diffRemoved?: CSSProperties
      diffAdded?: CSSProperties
      line?: CSSProperties
      titleBlock?: CSSProperties
      contentText?: CSSProperties
      gutter?: CSSProperties
      highlightedGutter?: CSSProperties
      lineNumber?: CSSProperties
      emptyLine?: CSSProperties
      marker?: CSSProperties
      wordDiff?: CSSProperties
      wordAdded?: CSSProperties
      wordRemoved?: CSSProperties
      codeFoldGutter?: CSSProperties
      emptyGutter?: CSSProperties
      splitView?: CSSProperties
    }
    renderContent?: (source: string) => ReactNode
    codeFoldMessageRenderer?: (total: number) => ReactNode
    hideLineNumbers?: boolean
    disableWordDiff?: boolean
  }

  const ReactDiffViewer: React.FC<ReactDiffViewerProps>
  export default ReactDiffViewer
}
