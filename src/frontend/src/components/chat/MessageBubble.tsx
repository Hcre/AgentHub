import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Avatar, Button, Icon } from '../ui'
import type { Agent, ChatMessage, UserInfo } from '../../types'

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
        <div className="prose text-[14px] leading-[1.6] text-foreground">
          {isAgent ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                pre: ({ children }: any) => (
                  <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border bg-muted/50 p-3 text-[13px] font-mono text-foreground/80">
                    {children}
                  </pre>
                ),
                code: ({ className, children, ...props }: any) => {
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
                a: ({ href, children }: any) => (
                  <a href={href} target="_blank" rel="noopener" className="text-brand underline">
                    {children}
                  </a>
                ),
                table: ({ children }: any) => (
                  <div className="overflow-x-auto my-2">
                    <table className="min-w-full border-separate border-spacing-0 rounded-lg border text-[13px]">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }: any) => (
                  <th className="border-b bg-muted/50 px-3 py-1.5 text-left font-medium text-muted-foreground">
                    {children}
                  </th>
                ),
                td: ({ children }: any) => (
                  <td className="border-b px-3 py-1.5">{children}</td>
                ),
                blockquote: ({ children }: any) => (
                  <blockquote className="my-2 border-l-2 border-brand/40 pl-3 italic text-muted-foreground">
                    {children}
                  </blockquote>
                ),
              }}
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
        {msg.attachment && (
          <div className="mt-2 inline-flex items-center gap-2.5 rounded-md border bg-muted/40 px-3 py-2">
            <div className="grid h-7 w-7 place-items-center rounded border bg-background text-muted-foreground">
              <Icon name="doc" className="h-3.5 w-3.5" />
            </div>
            <div className="text-left">
              <div className="font-mono text-[12px]">{msg.attachment.name}</div>
              <div className="font-mono text-[10.5px] text-muted-foreground">
                {msg.attachment.size}
              </div>
            </div>
          </div>
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
