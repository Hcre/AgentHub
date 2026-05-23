// Chrome — Sidebar, RightPanel
// Center frame lives in app.jsx so it can compose with the tab views.

/* ─────────────────────────── Sidebar ─────────────────────────── */
const SidebarRow = ({ icon, label, count, active, badge, onClick, dotted }) =>
<button onClick={onClick}
data-active={active ? "true" : undefined}
className={cn(
  "group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm",
  "text-muted-foreground hover:bg-accent hover:text-foreground transition-colors",
  "data-[active=true]:bg-accent data-[active=true]:text-foreground data-[active=true]:font-medium"
)}>
    {icon && <Icon name={icon} className="h-4 w-4" strokeWidth={1.75} />}
    {dotted && <span className="text-muted-foreground/70 font-mono text-[13px] w-4 text-center">#</span>}
    <span className="flex-1 truncate text-left">{label}</span>
    {count > 0 &&
  <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">{count}</span>
  }
    {badge}
  </button>;


const SectionHeader = ({ label, collapsed, onToggle, onAdd, addTitle }) =>
<div className="flex items-center justify-between px-2 mt-3 mb-1 group">
    <button onClick={onToggle}
  className="flex items-center gap-1 text-[10.5px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors">
      <Icon name="chevronDown" className={cn("h-2.5 w-2.5 transition-transform", collapsed && "-rotate-90")} />
      <span>{label}</span>
    </button>
    {onAdd &&
  <button onClick={onAdd} title={addTitle}
  className="opacity-0 group-hover:opacity-100 transition-opacity h-4 w-4 rounded grid place-items-center hover:bg-accent">
        <Icon name="plus" className="h-3 w-3" />
      </button>
  }
  </div>;


const Sidebar = ({ data, state, setState, onCollapse, onCreateAgent }) => {
  const [openAI, setOpenAI] = React.useState(true);
  const [openCh, setOpenCh] = React.useState(true);
  const [expandedAgents, setExpandedAgents] = React.useState({ editor: true });
  const channels = (data.channels || []).concat(
    (window.DATA_EXTRA?.groups || []).filter((g) => !(data.channels || []).find((c) => c.id === g.id))
  );
  const toggleAgent = (id) => setExpandedAgents((m) => ({ ...m, [id]: !m[id] }));

  return (
    <aside className="flex h-full w-full flex-col glass-panel border rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-2 px-3 pt-3 pb-2">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-brand to-brand-deep text-brand-foreground heading-serif font-semibold text-sm shadow-sm">
          {data.org.initial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="heading-serif text-[14px] font-medium truncate">{data.org.name}</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">workspace</div>
        </div>
        <Button variant="ghost" size="iconSm" onClick={onCollapse} title="Collapse sidebar">
          <Icon name="panelLeft" className="h-3.5 w-3.5" />
        </Button>
      </header>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="flex h-8 items-center gap-2 rounded-md border glass-soft px-2.5 text-muted-foreground transition-colors focus-within:border-brand/40" style={{ height: "30px" }}>
          <Icon name="search" className="h-3.5 w-3.5" />
          <input placeholder="Jump to…" className="flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/70" style={{ width: "20px" }} />
          <Kbd>⌘K</Kbd>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        <div className="space-y-px">
          {data.nav.map((n) =>
          <SidebarRow key={n.id} icon={n.icon} label={n.label} count={n.count}
          active={state.section === n.id}
          onClick={() => setState((s) => ({ ...s, section: n.id, agentId: null, groupId: null }))} />
          )}
        </div>

        <SectionHeader label="频道" collapsed={!openCh} onToggle={() => setOpenCh((v) => !v)} onAdd={() => {}} />
        {openCh &&
        <div className="space-y-px">
            {channels.map((c) =>
          <SidebarRow key={c.id} label={c.name} dotted
          active={state.section === "group" && state.groupId === c.id}
          onClick={() => setState((s) => ({ ...s, section: "group", groupId: c.id, agentId: null }))}
          badge={c.unread && <span className="h-1.5 w-1.5 rounded-full bg-brand" />} />
          )}
          </div>
        }

        <SectionHeader label="AI 队友" collapsed={!openAI} onToggle={() => setOpenAI((v) => !v)}
        onAdd={onCreateAgent} addTitle="创建新助手" />
        {openAI &&
        <div className="space-y-px">
            {data.agents.map((a) => {
            const expanded = !!expandedAgents[a.id];
            const convs = (data.conversations[a.id] || []);
            const isActive = state.agentId === a.id && state.section === "chat";
            return (
              <div key={a.id}>
                <div
                  role="button"
                  tabIndex={0}
                  data-active={isActive ? "true" : undefined}
                  onClick={() => setState((s) => ({ ...s, agentId: a.id, section: "chat", groupId: null }))}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setState((s) => ({ ...s, agentId: a.id, section: "chat", groupId: null })); } }}
                  className={cn(
                    "group/agent relative flex w-full items-center gap-2 rounded-md pl-2 pr-1 py-1.5 text-sm cursor-pointer",
                    "text-muted-foreground hover:bg-accent hover:text-foreground transition-colors",
                    "data-[active=true]:bg-accent data-[active=true]:text-foreground data-[active=true]:font-medium",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  )}>
                  <Avatar initial={a.name[0]} color={a.color} size={20} online={a.online} />
                  <span className="flex-1 truncate text-left">{a.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); setState((s) => ({ ...s, agentId: a.id, section: "agent-detail" })); }}
                    title="查看助手详情"
                    className="opacity-0 group-hover/agent:opacity-100 transition-opacity h-5 w-5 rounded grid place-items-center hover:bg-background text-muted-foreground hover:text-foreground">
                    <Icon name="info" className="h-3 w-3" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleAgent(a.id); }}
                    title={expanded ? "收起历史会话" : "展开历史会话"}
                    className={cn(
                      "inline-flex items-center gap-1 rounded border px-1.5 py-0 text-[9px] font-mono uppercase tracking-wider transition-colors",
                      "hover:bg-brand/10 hover:border-brand/30 hover:text-brand",
                      "border-transparent bg-brand/10 text-brand"
                    )}>
                    <span>AI</span>
                    <Icon name="chevronDown" className={cn("h-2 w-2 transition-transform", !expanded && "-rotate-90")} />
                  </button>
                </div>
                {expanded && (
                  <div className="ml-5 mt-0.5 mb-1 border-l border-border/60 pl-1 space-y-px">
                    {convs.length === 0 ? (
                      <div className="px-2 py-1 text-[11px] text-muted-foreground/70">还没有会话</div>
                    ) : convs.map((c) => {
                      const on = isActive && state.conversationId === c.id;
                      return (
                        <button key={c.id}
                          onClick={() => setState((s) => ({ ...s, agentId: a.id, section: "chat", groupId: null, conversationId: c.id }))}
                          data-active={on ? "true" : undefined}
                          className={cn(
                            "flex w-full items-start gap-2 rounded-md px-2 py-1 text-left",
                            "text-muted-foreground hover:bg-accent hover:text-foreground transition-colors",
                            "data-[active=true]:bg-brand/10 data-[active=true]:text-foreground"
                          )}>
                          <span className={cn("mt-1 h-1.5 w-1.5 rounded-full flex-shrink-0",
                            on ? "bg-brand" : "bg-muted-foreground/40")} />
                          <div className="min-w-0 flex-1">
                            <div className="text-[12.5px] truncate">{c.name}</div>
                            <div className="font-mono text-[10px] text-muted-foreground/80 truncate">{c.subtitle}</div>
                          </div>
                        </button>
                      );
                    })}
                    <button className="flex items-center gap-1.5 w-full rounded-md px-2 py-1 text-[11.5px] text-muted-foreground hover:text-brand transition-colors">
                      <Icon name="plus" className="h-2.5 w-2.5" /> 新建会话
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          </div>
        }
      </nav>

      {/* User card */}
      <footer className="border-t border-border/70 p-2">
        <div className="flex items-center gap-2 rounded-md p-2 glass-soft border border-border/50 hover:glass-strong transition-all">
          <Avatar initial={data.user.initial} color="neutral" size={28} online />
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-medium truncate">{data.user.handle}</div>
            <div className="flex items-center gap-1 text-[10.5px] font-mono text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse-dot" />
              <span>在线</span>
            </div>
          </div>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground">
            <Icon name="moreHorizontal" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </footer>
    </aside>);

};

/* ─────────────────────────── Right panel ─────────────────────────── */
const StateDot = ({ state }) => {
  if (state === "done") return <Icon name="check" className="h-3 w-3" />;
  if (state === "doing") return <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse" />;
  return null;
};
const TaskCheck = ({ state, onClick, size = "default" }) =>
<button onClick={onClick}
className={cn(
  "grid place-items-center rounded-full border-[1.5px] transition-all hover:scale-110 flex-shrink-0",
  size === "lg" ? "h-[18px] w-[18px]" : "h-4 w-4",
  state === "done" && "bg-brand border-brand text-brand-foreground",
  state === "doing" && "border-brand bg-background",
  !state && "border-border bg-background"
)}>
    <StateDot state={state} />
  </button>;


const RightPanel = ({ state, onToggleTask, onClose }) => {
  return (
    <aside className="flex h-full w-full flex-col gap-3">
      {/* Stage */}
      <section className="glass-panel border rounded-2xl shadow-sm flex flex-col min-h-0 max-h-[50%]">
        <header className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="listCheck" className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="heading-serif text-[15px] font-medium tracking-tight">阶段</h3>
          </div>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground">
            <Icon name="plus" className="h-3.5 w-3.5" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {state.stage.length === 0 ?
          <div className="px-3 py-6 text-center text-xs text-muted-foreground">暂无任务</div> :
          state.stage.map((t) =>
          <div key={t.id} className="group flex items-start gap-2.5 rounded-md px-2 py-2 hover:bg-accent/60 transition-colors">
              <div className="pt-0.5">
                <TaskCheck state={t.state} size="lg" onClick={() => onToggleTask(t.id)} />
              </div>
              <div className="flex-1 min-w-0">
                <div className={cn("text-[13px] font-medium leading-tight",
              t.state === "done" && "text-muted-foreground line-through")}>
                  {t.label}
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <Badge variant={t.state === "doing" ? "brand" : t.state === "done" ? "success" : "outline"}>
                    {t.state === "done" ? "完成" : t.state === "doing" ? "进行中" : "待办"}
                  </Badge>
                  <span className="font-mono text-[10.5px] text-muted-foreground">~{t.eta} min</span>
                </div>
              </div>
            </div>
          )}
        </div>
        <footer className="border-t border-border/70 p-2">
          <Button variant="secondary" size="sm" className="w-full bg-brand-soft text-brand-deep hover:bg-brand-soft/80">
            <Icon name="sparkle" className="h-3 w-3" />
            建议下一步
          </Button>
        </footer>
      </section>

      {/* Outputs */}
      <section className="glass-panel border rounded-2xl shadow-sm flex flex-col flex-1 min-h-0">
        <header className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="files" className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="heading-serif text-[15px] font-medium tracking-tight">任务产出</h3>
          </div>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground">
            <Icon name="moreHorizontal" className="h-3.5 w-3.5" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto p-2">
          {state.outputs.length === 0 ?
          <div className="px-3 py-6 text-center text-xs text-muted-foreground">尚无产出文件</div> :
          state.outputs.map((f) =>
          <div key={f.id} className="my-0.5 flex items-center gap-2.5 rounded-md border border-border/60 glass-soft p-2.5 transition-all hover:-translate-y-px hover:glass-strong">
              <div className="grid h-8 w-8 place-items-center rounded-md border glass-strong text-muted-foreground">
                <Icon name={f.kind === "diff" ? "diff" : "doc"} className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="truncate font-mono text-[12.5px]">{f.name}</div>
                <div className="mt-0.5 font-mono text-[10.5px] text-muted-foreground">
                  {f.kind === "diff" ? "Diff" : "Document"} · {f.size}
                </div>
              </div>
              <Badge variant={f.status === "pending" ? "brand" : "outline"} className="text-[9.5px]">
                {f.status === "input" ? "输入" : f.status === "pending" ? "生成中" : "完成"}
              </Badge>
            </div>
          )}
        </div>
      </section>
    </aside>);

};

window.Sidebar = Sidebar;
window.RightPanel = RightPanel;
window.TaskCheck = TaskCheck;