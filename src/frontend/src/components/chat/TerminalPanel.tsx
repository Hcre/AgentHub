import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { WS_BASE } from '../../api/client'
import { Icon } from '../ui'

interface TerminalPanelProps {
  sessionId: string
  onClose?: () => void
}

/**
 * 嵌入式终端面板 —— 通过 WebSocket 流式接收 session 的 CLI 输出并渲染到 xterm.js 终端。
 *
 * - 以固定高度 280px 的底部面板呈现，可折叠/展开。
 * - 折叠后仅保留标题栏，终端实例与 WebSocket 保持连接，展开时恢复显示。
 * - onClose 回调由父组件决定是否销毁整个面板。
 */
export function TerminalPanel({ sessionId, onClose }: TerminalPanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!sessionId || !containerRef.current) return

    let closed = false

    const term = new Terminal({
      theme: {
        background: '#1e1e1e',
        foreground: '#cccccc',
        cursor: '#cccccc',
        cursorAccent: '#1e1e1e',
        selectionBackground: '#264f78',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#ffffff',
      },
      fontSize: 13,
      fontFamily:
        "'Cascadia Code', 'Fira Code', 'JetBrains Mono', Consolas, monospace",
      cursorBlink: true,
      scrollback: 5000,
    })

    term.open(containerRef.current)
    termRef.current = term

    const wsUrl = `${WS_BASE}/ws/sessions/${sessionId}/terminal`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (closed) return
      term.writeln('\x1b[32m● Terminal connected\x1b[0m')
    }

    ws.onmessage = (e) => {
      if (closed) return
      if (typeof e.data === 'string') {
        term.write(e.data)
      } else if (e.data instanceof Blob) {
        const reader = new FileReader()
        reader.onload = () => {
          if (!closed && typeof reader.result === 'string') {
            term.write(reader.result)
          }
        }
        reader.readAsText(e.data)
      }
    }

    ws.onerror = () => {
      if (closed) return
      term.writeln('\r\n\x1b[31m● Connection error\x1b[0m')
    }

    ws.onclose = () => {
      if (closed) return
      term.writeln('\r\n\x1b[33m● Disconnected\x1b[0m')
    }

    return () => {
      closed = true
      ws.close()
      wsRef.current = null
      term.dispose()
      termRef.current = null
    }
  }, [sessionId])

  return (
    <div className="border-t border-border/70">
      {/* Header bar */}
      <div className="flex items-center justify-between bg-[#252526] px-4 py-1.5">
        <div className="flex items-center gap-2">
          <Icon
            name="terminal"
            className="h-3.5 w-3.5 text-muted-foreground"
          />
          <span className="font-mono text-[12px] font-medium text-foreground">
            终端
          </span>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? '展开终端' : '收起终端'}
            className="grid h-6 w-6 place-items-center rounded text-muted-foreground/60 transition-colors hover:bg-accent hover:text-muted-foreground"
          >
            <Icon
              name="chevronDown"
              className={`h-3.5 w-3.5 transition-transform ${collapsed ? 'rotate-180' : ''}`}
            />
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              title="关闭终端"
              className="grid h-6 w-6 place-items-center rounded text-muted-foreground/60 transition-colors hover:bg-accent hover:text-muted-foreground"
            >
              <Icon name="x" className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Terminal container — hidden when collapsed, instance stays alive */}
      {!collapsed && (
        <div
          ref={containerRef}
          className="w-full overflow-hidden"
          style={{ height: 280, background: '#1e1e1e' }}
        />
      )}
    </div>
  )
}
