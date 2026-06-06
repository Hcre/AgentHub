import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Avatar, Button, Icon } from '../ui'
import type { Agent, ChatMessage, UserInfo } from '../../types'
import { WebPreviewCard } from './WebPreviewCard'
import { collectUrls } from './webPreviewUrl'

export function MessageBubble({
  msg,
  agent,
  user,
}: {
  msg: ChatMessage
  agent: Agent
  user: UserInfo
}) {
  const isAgent = msg.from === 'agent'
  // 优先用 Agent 显式声明的 urls 字段；退化路径从 text 抓 http(s)://
  const previewUrls = isAgent ? collectUrls(msg.text, msg.urls) : []
  return (
    <div className="animate-[var(--animate-fade-in)] flex gap-3">
      <div className="pt-0.5">
        {isAgent ? (
          <Avatar initial={agent.name[0] ?? '?'} color={agent.color} size={32} />
        ) : (
          <Avatar initial={user.initial} color="neutral" size={32} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[13px] font-semibold">{isAgent ? agent.name : user.handle}</span>
          <span className="font-mono text-[11px] text-muted-foreground">{msg.time}</span>
        </div>
        <div className="prose min-w-0 max-w-full break-words text-[14px] leading-[1.6] text-foreground">
          {isAgent ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                pre: ({ children }) => (
                  <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border bg-muted/50 p-3 text-[13px] font-mono text-foreground/80">
                    {children}
                  </pre>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !className
                  return isInline ? (
                    <code className="text-[13px] font-mono text-foreground" {...props}>
                      {children}
                    </code>
                  ) : (
                    <code
                      className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[12px] text-foreground"
                      {...props}
                    >
                      {children}
                    </code>
                  )
                },
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener" className="text-brand underline">
                    {children}
                  </a>
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="min-w-full border-separate border-spacing-0 rounded-lg border text-[13px]">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border-b bg-muted/50 px-3 py-1.5 text-left font-medium text-muted-foreground">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border-b px-3 py-1.5">{children}</td>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="my-2 border-l-2 border-brand/40 pl-3 italic text-muted-foreground">
                    {children}
                  </blockquote>
                ),
              } satisfies Components}
            >
              {msg.text}
            </ReactMarkdown>
          ) : (
            msg.text.split('\n\n').map((p, i) => (
              <p key={i} className={i > 0 ? 'mt-2' : undefined}>
                {p}
              </p>
            ))
          )}
        </div>
        {previewUrls.map((u) => (
          <WebPreviewCard key={u} url={u} />
        ))}
        {msg.attachment && (
          <a
            href={msg.attachment.url ?? '#'}
            download={msg.attachment.url ? undefined : undefined}
            target="_blank"
            rel="noopener"
            className="mt-2 inline-flex items-center gap-2.5 rounded-md border bg-muted/40 px-3 py-2 transition-colors hover:bg-muted/60"
          >
            <div className="grid h-7 w-7 place-items-center rounded border bg-background text-muted-foreground">
              <Icon name="doc" className="h-3.5 w-3.5" />
            </div>
            <div className="text-left">
              <div className="font-mono text-[12px] underline-offset-2 group-hover:underline">
                {msg.attachment.name}
              </div>
              <div className="font-mono text-[10.5px] text-muted-foreground">
                {msg.attachment.size}
              </div>
            </div>
          </a>
        )}
        {msg.actions && (
          <div className="mt-2 flex gap-2">
            {msg.actions.map((a) => (
              <Button key={a} variant="outline" size="sm">
                {a}
              </Button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
