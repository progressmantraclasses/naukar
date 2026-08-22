import React, { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, ChevronDown, ChevronUp, Clipboard, Download, Search } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'

function nodeText(node: React.ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(nodeText).join(' ')
  if (React.isValidElement(node)) return nodeText(node.props.children)
  return ''
}

function normalizeReportMarkdown(markdown: string): string {
  return markdown
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/\s*\|\|\s*/g, '\n')
    .replace(/^(\s*\|[^\n]+\|)\s*$/gm, '$1\n')
}

const InteractiveTable: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [query, setQuery] = useState('')
  const [sortColumn, setSortColumn] = useState<number | null>(null)
  const [descending, setDescending] = useState(false)
  const [selectedRow, setSelectedRow] = useState<number | null>(null)
  const sections = React.Children.toArray(children).filter(React.isValidElement)
  const headerSection = sections.find((section) => section.type === 'thead') as React.ReactElement | undefined
  const bodySection = sections.find((section) => section.type === 'tbody') as React.ReactElement | undefined
  const headerRow = headerSection ? React.Children.toArray(headerSection.props.children)[0] as React.ReactElement : null
  const bodyRows = bodySection ? React.Children.toArray(bodySection.props.children).filter(React.isValidElement) as React.ReactElement[] : []
  const headers = headerRow ? React.Children.toArray(headerRow.props.children) : []

  const visibleRows = useMemo(() => {
    const filtered = bodyRows.filter((row) => !query || nodeText(row).toLowerCase().includes(query.toLowerCase()))
    if (sortColumn === null) return filtered
    return [...filtered].sort((left, right) => {
      const leftCell = React.Children.toArray(left.props.children)[sortColumn]
      const rightCell = React.Children.toArray(right.props.children)[sortColumn]
      return nodeText(leftCell).localeCompare(nodeText(rightCell), undefined, { numeric: true }) * (descending ? -1 : 1)
    })
  }, [bodyRows, descending, query, sortColumn])

  const sortBy = (column: number) => {
    if (sortColumn === column) setDescending((value) => !value)
    else { setSortColumn(column); setDescending(false) }
  }

  return (
    <div className="interactive-table">
      <div className="table-toolbar">
        <label className="table-search">
          <Search size={14} aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter rows" aria-label="Filter table rows" />
        </label>
        <span className="table-count">{visibleRows.length} of {bodyRows.length} rows</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            {headerRow && React.cloneElement(headerRow, {
              children: headers.map((header, index) => (
                <th key={index} className="sortable-header" onClick={() => sortBy(index)} scope="col">
                  <span>{header}</span>
                  {sortColumn === index && (descending ? <ChevronDown size={14} /> : <ChevronUp size={14} />)}
                </th>
              )),
            })}
          </thead>
          <tbody>
            {visibleRows.map((row, index) => React.cloneElement(row, {
              key: index,
              className: `${row.props.className || ''} ${selectedRow === index ? 'selected-row' : ''}`,
              onClick: () => setSelectedRow(index),
            }))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

export const ResultDisplay: React.FC = () => {
  const {
    phase, finalResult, qualityScore, elapsedMs,
    employees, steps, title, reset,
  } = useTaskStore()
  const [copied, setCopied] = useState(false)

  if (phase !== 'completed' && phase !== 'failed') return null
  if (phase === 'failed') {
    return (
      <div className="result-panel">
        <div className="result-header">
          <div className="result-header-top">
            <div className="result-title">❌ Task Failed</div>
            <button className="btn-new-task" onClick={reset}>
              ↩ New Task
            </button>
          </div>
        </div>
        <div className="result-content">
          <div style={{ color: 'var(--accent-rose)', padding: 16 }}>
            The task encountered an error. Please check the backend logs and try again.
          </div>
        </div>
      </div>
    )
  }

  const completedSteps = steps.filter((s) => s.status === 'completed').length

  const copyResult = async () => {
    await navigator.clipboard.writeText(finalResult || '')
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  const downloadResult = () => {
    const blob = new Blob([finalResult || ''], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${(title || 'naukar-result').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="result-panel">
      <div className="result-header">
        <div className="result-header-top">
          <div className="result-title">
            ✅ {title || 'Task Complete'}
          </div>
          <div className="result-quality">
            {qualityScore !== null && (
              <div className="quality-badge">
                ⭐ {Math.round(qualityScore * 100)}% Quality
              </div>
            )}
            <button className="btn-new-task" onClick={reset}>
              ↩ New Task
            </button>
          </div>
        </div>
        <div className="result-stats">
          <div className="result-stat">
            <strong>{employees.length}</strong> employees
          </div>
          <div className="result-stat">
            <strong>{completedSteps}</strong> steps
          </div>
          <div className="result-stat">
            Completed in <strong>{formatElapsed(elapsedMs)}</strong>
          </div>
        </div>
      </div>

      <div className="result-content">
        <div className="result-actions" role="toolbar" aria-label="Result actions">
          <span className="result-actions-label">DELIVERABLE</span>
          <button type="button" onClick={copyResult} title="Copy result">
            {copied ? <Check size={15} /> : <Clipboard size={15} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" onClick={downloadResult} title="Download Markdown">
            <Download size={15} />
            Markdown
          </button>
        </div>
        <div className="result-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ table: InteractiveTable }}>
            {normalizeReportMarkdown(finalResult || '_No result generated._')}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
