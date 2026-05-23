// All secondary tab views + Create Task modal — v0/shadcn aesthetic.

/* ═════════════════════ 聊天 — Chat ═════════════════════ */

const Message = ({ msg, agent, user }) => {
  const { toast } = useApp();
  const isAgent = msg.from === "agent";
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="pt-0.5">
        {isAgent ?
        <Avatar initial={agent.name[0]} color={agent.color} size={32} /> :
        <Avatar initial={user.initial} color="neutral" size={32} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[13px] font-semibold">{isAgent ? agent.name : user.handle}</span>
          {isAgent && <Badge variant="brand">AI</Badge>}
          <span className="font-mono text-[11px] text-muted-foreground">{msg.time}</span>
        </div>
        <div className="ai-prose text-[14px] leading-[1.6] text-foreground" style={{ textWrap: "pretty" }}>
          {msg.text.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}
        </div>
        {msg.attachment &&
        <button onClick={() => toast(`打开「${msg.attachment.name}」`, { kind: "info" })}
          className="mt-2 inline-flex items-center gap-2.5 rounded-md border bg-muted/40 px-3 py-2 hover:bg-muted transition-colors">
            <div className="grid h-7 w-7 place-items-center rounded border bg-background text-muted-foreground">
              <Icon name="doc" className="h-3.5 w-3.5" />
            </div>
            <div className="text-left">
              <div className="font-mono text-[12px]">{msg.attachment.name}</div>
              <div className="font-mono text-[10.5px] text-muted-foreground">{msg.attachment.size}</div>
            </div>
          </button>
        }
        {msg.actions &&
        <div className="mt-2 flex gap-2">
            {msg.actions.map((a, i) =>
              <Button key={i} variant="outline" size="sm" onClick={() => toast(`${a}`, { kind: "info" })}>{a}</Button>
            )}
          </div>
        }
      </div>
    </div>);
};

const TypingMessage = ({ agent }) =>
  <div className="flex gap-3 animate-fade-in">
    <Avatar initial={agent.name[0]} color={agent.color} size={32} />
    <div className="flex-1">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[13px] font-semibold">{agent.name}</span>
        <Badge variant="brand">AI</Badge>
        <span className="font-mono text-[11px] text-muted-foreground">正在输入…</span>
      </div>
      <div className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1.5">
        <span className="typing-dot h-1 w-1 rounded-full bg-brand" />
        <span className="typing-dot h-1 w-1 rounded-full bg-brand" />
        <span className="typing-dot h-1 w-1 rounded-full bg-brand" />
      </div>
    </div>
  </div>;


const Composer = ({ agent, onSend }) => {
  const { toast } = useApp();
  const [val, setVal] = React.useState("");
  const fileRef = React.useRef(null);
  const taRef = React.useRef(null);
  const send = () => { if (!val.trim()) return; onSend(val.trim()); setVal(""); };
  const onAttach = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    toast(`已附上 ${f.name} (${Math.ceil(f.size / 1024)} KB)`, { kind: "success" });
    setVal(v => v + (v ? "\n" : "") + `📎 ${f.name}`);
    e.target.value = "";
  };
  const insertMarkdown = (open, close) => {
    const ta = taRef.current; if (!ta) return;
    const start = ta.selectionStart, end = ta.selectionEnd;
    const sel = val.slice(start, end) || "文本";
    const next = val.slice(0, start) + open + sel + (close || "") + val.slice(end);
    setVal(next);
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(start + open.length, start + open.length + sel.length);
    }, 0);
  };
  const insertAtMention = () => {
    insertMarkdown(`@${agent.name} `, "");
  };
  const tools = [
    { i: "paperclip", label: "附件", onClick: () => fileRef.current?.click() },
    { i: "type", label: "粗体", onClick: () => insertMarkdown("**", "**") },
    { i: "smile", label: "表情", onClick: () => insertMarkdown("🙂 ", "") },
    { i: "atSign", label: "提及", onClick: insertAtMention },
  ];
  return (
    <div className="mx-4 mb-4 rounded-xl border bg-background shadow-sm transition-all focus-within:ring-2 focus-within:ring-ring">
      <input ref={fileRef} type="file" className="hidden" onChange={onAttach}/>
      <textarea
        ref={taRef}
        rows={1}
        placeholder={`Ask ${agent.role.toLowerCase()}…`}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        className="w-full resize-none rounded-t-xl border-0 bg-transparent px-3 py-3 text-[14px] outline-none placeholder:text-muted-foreground"
        style={{ maxHeight: 200 }} />
      <div className="flex items-center justify-between px-2 py-2">
        <div className="flex gap-0.5">
          {tools.map(t =>
            <Button key={t.i} variant="ghost" size="iconSm" title={t.label}
              onClick={t.onClick}
              className="text-muted-foreground h-7 w-7">
              <Icon name={t.i} className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-muted-foreground">↵ Send</span>
          <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
            <Icon name="send" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>);

};

const ConvTabs = ({ convs, activeId, onPick, open, onToggle, agent }) => {
  const { state, dispatch, toast } = useApp();
  const active = convs.find((c) => c.id === activeId);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const onNewConv = () => {
    const n = (convs.length || 0) + 1;
    const conv = { id: uid("c"), name: `对话 ${n}`, subtitle: "刚刚开始" };
    dispatch({ type: "addConversation", agentId: agent.id, conv });
    toast(`已新建会话「${conv.name}」`, { kind: "success" });
  };
  return (
    <div className="flex items-center gap-2 border-b px-3 py-2.5 relative">
      <div className="relative">
        <Button variant="ghost" size="iconSm" onClick={() => setMenuOpen(v => !v)}>
          <Icon name="moreHorizontal" className="h-3.5 w-3.5" />
        </Button>
        {menuOpen && (
          <div className="absolute left-0 top-9 w-44 rounded-lg border bg-popover p-1 shadow-lg z-20"
            onMouseLeave={() => setMenuOpen(false)}>
            <button onClick={() => { onNewConv(); setMenuOpen(false); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              <Icon name="plus" className="h-3 w-3"/> 新建会话
            </button>
            <button onClick={() => { toast("已固定到顶部", { kind: "success" }); setMenuOpen(false); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              <Icon name="pin" className="h-3 w-3"/> 固定此会话
            </button>
            <button onClick={() => { toast("已复制对话链接", { kind: "success" }); setMenuOpen(false); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              <Icon name="link" className="h-3 w-3"/> 复制链接
            </button>
          </div>
        )}
      </div>
      <div className={cn("flex-1 min-w-0 overflow-hidden transition-all duration-300",
        open ? "max-h-12 opacity-100" : "max-h-0 opacity-0 pointer-events-none")}>
        <div className="flex gap-1.5 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
          {convs.map((c) =>
            <button key={c.id} onClick={() => onPick(c.id)}
              data-active={activeId === c.id ? "true" : undefined}
              className={cn(
                "flex flex-col items-start gap-0.5 rounded-md border px-3 py-1.5 min-w-[140px] transition-colors text-left",
                "hover:bg-accent",
                "data-[active=true]:bg-brand/10 data-[active=true]:border-brand/30"
              )}>
              <span className="text-[12px] font-semibold">{c.name}</span>
              <span className="font-mono text-[10.5px] text-muted-foreground truncate max-w-[160px]">{c.subtitle}</span>
            </button>
          )}
          <button onClick={onNewConv} title="新建会话"
            className="flex items-center justify-center rounded-md border border-dashed w-9 text-muted-foreground hover:bg-accent hover:text-brand">
            <Icon name="plus" className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {!open &&
        <div className="flex-1 flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
          <span>历史会话</span>
          {active && <span className="font-sans normal-case tracking-normal text-[12.5px] text-foreground font-medium">· {active.name}</span>}
        </div>
      }
      <Button variant="ghost" size="iconSm" onClick={onToggle} title={open ? "收起" : "展开"}>
        <Icon name="chevronUp" className={cn("h-3.5 w-3.5 transition-transform", !open && "rotate-180")} />
      </Button>
    </div>);
};

const ChatView = ({ agent, user, conversations, messages, activeConvId, setActiveConvId, historyOpen, setHistoryOpen, pendingReply, onSend }) => {
  const convs = conversations[agent.id] || [];
  const activeConv = convs.find((c) => c.id === activeConvId);
  const msgs = messages[agent.id] && messages[agent.id][activeConvId] || [];
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [msgs.length, pendingReply]);
  return (
    <>
      <ConvTabs convs={convs} activeId={activeConvId} onPick={setActiveConvId}
        open={historyOpen} onToggle={() => setHistoryOpen(!historyOpen)} agent={agent}/>
      {activeConv && (
        <div className="flex items-center gap-2 border-b border-border/60 bg-muted/20 px-5 py-2">
          <Icon name="chat" className="h-3 w-3 text-muted-foreground"/>
          <span className="text-[12.5px] font-medium">{activeConv.name}</span>
          <span className="font-mono text-[10.5px] text-muted-foreground">· {activeConv.subtitle}</span>
          <div className="flex-1"/>
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">在侧边栏切换历史会话</span>
        </div>
      )}
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-5 space-y-5">
        {msgs.length === 0 && (
          <div className="flex flex-col items-center justify-center text-center py-20 text-muted-foreground">
            <Icon name="chat" className="h-8 w-8 mb-3 opacity-40"/>
            <div className="text-[13px]">还没有消息 — 给 {agent.name} 留个开头。</div>
          </div>
        )}
        {msgs.map((m) => <Message key={m.id} msg={m} agent={agent} user={user} />)}
        {pendingReply && <TypingMessage agent={agent} />}
      </div>
      <Composer agent={agent} onSend={onSend} />
    </>);
};

/* ═════════════════════ 任务 — Tasks ═════════════════════ */

const PRIORITY_LABEL = { low: "低", normal: "普通", high: "高" };
const COLUMNS = [
  { id: "todo",    label: "待处理", dotClass: "border-2 border-muted-foreground/40" },
  { id: "doing",   label: "进行中", dotClass: "bg-brand/60 border-2 border-brand" },
  { id: "blocked", label: "阻塞",   dotClass: "bg-amber-400 border-2 border-amber-500" },
  { id: "done",    label: "完成",   dotClass: "bg-emerald-500 border-2 border-emerald-600" }
];

const KanbanCard = ({ task, agentsById, onClick }) => {
  const { dispatch, toast } = useApp();
  const a = agentsById[task.assignee];
  const onDragStart = (e) => {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", task.id);
  };
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      title="点击循环状态 · 拖到其他列改状态"
      className="rounded-md border bg-background p-3 transition-all hover:-translate-y-px hover:shadow-sm cursor-grab active:cursor-grabbing space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">{task.id}</span>
        {task.priority === "high" && <Badge variant="brand">高</Badge>}
        {task.priority === "low" && <Badge variant="outline" className="text-muted-foreground">低</Badge>}
      </div>
      <div className="text-[13px] font-medium leading-snug">{task.title}</div>
      <div className="flex items-center justify-between pt-1">
        <span className="font-mono text-[11px] text-muted-foreground">{task.due}</span>
        {a && <Avatar initial={a.name[0]} color={a.color} size={20} />}
      </div>
    </div>);
};

// Filter panel — single source for the kanban + list views.
const TaskFilterBar = ({ filter, setFilter, agents, total }) => {
  const [openMenu, setOpenMenu] = React.useState(null);
  const close = () => setOpenMenu(null);
  React.useEffect(() => {
    if (!openMenu) return;
    const h = () => close();
    window.addEventListener("click", h);
    return () => window.removeEventListener("click", h);
  }, [openMenu]);
  const Pill = ({ id, label, active }) => (
    <div className="relative" onClick={e => e.stopPropagation()}>
      <Button variant={active ? "secondary" : "outline"} size="sm"
        onClick={() => setOpenMenu(openMenu === id ? null : id)}>
        {label}
        {active && <Icon name="x" className="h-3 w-3 ml-1"
          onClick={e => { e.stopPropagation(); setFilter({ [id]: undefined }); }} />}
        {!active && <Icon name="chevronDown" className="h-3 w-3" />}
      </Button>
      {openMenu === id && (
        <div className="absolute left-0 top-9 w-48 rounded-lg border bg-popover p-1 shadow-lg z-20">
          {id === "state" && COLUMNS.map(c => (
            <button key={c.id} onClick={() => { setFilter({ state: c.id }); close(); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              <span className={cn("h-2 w-2 rounded-full", c.dotClass)}/> {c.label}
            </button>
          ))}
          {id === "priority" && ["high", "normal", "low"].map(p => (
            <button key={p} onClick={() => { setFilter({ priority: p }); close(); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              {PRIORITY_LABEL[p]}
            </button>
          ))}
          {id === "assignee" && agents.map(a => (
            <button key={a.id} onClick={() => { setFilter({ assignee: a.id }); close(); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              <Avatar initial={a.name[0]} color={a.color} size={18}/> {a.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-muted-foreground">
        <Icon name="search" className="h-3.5 w-3.5" />
        <input placeholder="搜索任务…" value={filter.q || ""}
          onChange={e => setFilter({ q: e.target.value })}
          className="w-40 bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground" />
      </div>
      <Pill id="state"    label={filter.state    ? COLUMNS.find(c => c.id === filter.state)?.label || "状态" : "状态"}    active={!!filter.state}/>
      <Pill id="priority" label={filter.priority ? PRIORITY_LABEL[filter.priority] : "优先级"}                              active={!!filter.priority}/>
      <Pill id="assignee" label={filter.assignee ? agents.find(a => a.id === filter.assignee)?.name || "负责人" : "负责人"} active={!!filter.assignee}/>
      <span className="font-mono text-[11px] text-muted-foreground ml-1">{total} 个结果</span>
    </div>
  );
};

const TasksTabView = ({ openCreate, filterAgentId }) => {
  const { state, dispatch, toast } = useApp();
  const [view, setView] = React.useState("kanban");
  const [showClosed, setShowClosed] = React.useState(true);
  const [filter, setFilterRaw] = React.useState({});
  const setFilter = (patch) => setFilterRaw(f => ({ ...f, ...patch }));
  const [dragOver, setDragOver] = React.useState(null);

  const agentsById = Object.fromEntries(state.agents.map((a) => [a.id, a]));
  const base = state.tasks.filter(t => !filterAgentId || t.assignee === filterAgentId);
  const filtered = base.filter(t => {
    if (!showClosed && t.state === "done") return false;
    if (filter.state && t.state !== filter.state) return false;
    if (filter.priority && t.priority !== filter.priority) return false;
    if (filter.assignee && t.assignee !== filter.assignee) return false;
    if (filter.q) {
      const q = filter.q.toLowerCase();
      const hay = (t.title + " " + t.id + " " + (agentsById[t.assignee]?.name || "")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const cols = COLUMNS.map((c) => ({ ...c, tasks: filtered.filter((t) => t.state === c.id) }));

  const cycleState = (t) => {
    const order = ["todo", "doing", "blocked", "done"];
    const next = order[(order.indexOf(t.state) + 1) % order.length];
    dispatch({ type: "moveTask", id: t.id, toState: next });
    toast(`「${t.title}」→ ${COLUMNS.find(c => c.id === next).label}`, { kind: "success" });
  };
  const onDrop = (colId) => (e) => {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/plain");
    setDragOver(null);
    if (!id) return;
    const t = state.tasks.find(x => x.id === id); if (!t || t.state === colId) return;
    dispatch({ type: "moveTask", id, toState: colId });
    toast(`「${t.title}」→ ${COLUMNS.find(c => c.id === colId).label}`, { kind: "success" });
  };
  const addToCol = (colId) => {
    const n = (base.length + 1);
    dispatch({ type: "addTask", task: {
      id: "T-" + n, title: "未命名任务", state: colId, priority: "normal",
      assignee: filterAgentId || state.agentId, due: "—"
    }});
    toast("已新增任务", { kind: "success" });
  };

  return (
    <div className="flex flex-col h-full px-6 py-5 gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Tabs value={view} onValueChange={setView}>
            <TabsList className="h-8">
              <TabsTrigger value="list" className="h-6 px-2"><Icon name="list" className="h-3 w-3" /></TabsTrigger>
              <TabsTrigger value="kanban" className="h-6 px-2"><Icon name="grid" className="h-3 w-3" /></TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant={showClosed ? "secondary" : "outline"} size="sm"
            onClick={() => setShowClosed(v => !v)}>{showClosed ? "显示已关闭" : "隐藏已关闭"}</Button>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11.5px] text-muted-foreground">{state.tasks.length} 个任务</span>
          <Button variant="brand" size="sm" onClick={openCreate}>
            <Icon name="plus" className="h-3.5 w-3.5" />
            创建任务
          </Button>
        </div>
      </div>

      <TaskFilterBar filter={filter} setFilter={setFilter} agents={state.agents} total={filtered.length}/>

      {/* Body */}
      {view === "kanban" ?
        <div className="flex-1 grid grid-cols-4 gap-3 min-h-0">
          {cols.map((c) =>
            <div key={c.id}
              onDragOver={e => { e.preventDefault(); setDragOver(c.id); }}
              onDragLeave={() => setDragOver(d => d === c.id ? null : d)}
              onDrop={onDrop(c.id)}
              className={cn("flex flex-col rounded-xl border bg-muted/30 transition-all",
                dragOver === c.id && "ring-2 ring-brand bg-brand/5")}>
              <header className="flex items-center justify-between border-b px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className={cn("h-2 w-2 rounded-full", c.dotClass)} />
                  <span className="text-[13px] font-medium tracking-tight">{c.label}</span>
                </div>
                <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">{c.tasks.length}</span>
              </header>
              <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-1.5">
                {c.tasks.length === 0 ?
                  <div className="px-3 py-8 text-center font-mono text-[11px] text-muted-foreground/70">空</div> :
                  c.tasks.map((t) => <KanbanCard key={t.id} task={t} agentsById={agentsById} onClick={() => cycleState(t)} />)}
              </div>
              <button onClick={() => addToCol(c.id)}
                className="m-2 flex items-center gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-accent hover:border-brand/30 transition-colors">
                <Icon name="plus" className="h-3 w-3" /> 添加
              </button>
            </div>
          )}
        </div>
      :
        <div className="flex-1 min-h-0 overflow-y-auto rounded-xl border bg-card">
          <table className="w-full text-[13px]">
            <thead className="bg-muted/50">
              <tr className="text-left font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 w-8"></th>
                <th className="px-3 py-2">任务</th>
                <th className="px-3 py-2 w-24">状态</th>
                <th className="px-3 py-2 w-20">优先级</th>
                <th className="px-3 py-2 w-40">负责人</th>
                <th className="px-3 py-2 w-20">截止</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const a = agentsById[t.assignee];
                return (
                  <tr key={t.id} className="border-t hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => cycleState(t)}>
                    <td className="px-3 py-2.5">
                      <TaskCheck state={t.state === "done" ? "done" : t.state === "doing" ? "doing" : null} />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="font-mono text-[10.5px] text-muted-foreground">{t.id}</span>
                        <span className="truncate">{t.title}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant={t.state === "done" ? "success" : t.state === "doing" ? "brand" : t.state === "blocked" ? "warning" : "outline"}>
                        {t.state === "done" ? "完成" : t.state === "doing" ? "进行中" : t.state === "blocked" ? "阻塞" : "待办"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant={t.priority === "high" ? "brand" : "outline"}>
                        {PRIORITY_LABEL[t.priority]}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      {a &&
                        <div className="flex items-center gap-2 min-w-0">
                          <Avatar initial={a.name[0]} color={a.color} size={20} />
                          <span className="truncate">{a.name}</span>
                        </div>
                      }
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[11.5px] text-muted-foreground">{t.due}</td>
                  </tr>);
              })}
            </tbody>
          </table>
        </div>
      }
    </div>);
};

/* ═════════════════════ 活动 — Activity ═════════════════════ */

const ActivityView = ({ events, user }) => {
  const [q, setQ] = React.useState("");
  const filtered = events.filter(e =>
    !q || (e.text + " " + e.tools.join(" ")).toLowerCase().includes(q.toLowerCase())
  );
  return (
    <div className="flex flex-col h-full px-6 py-5 gap-4 overflow-hidden">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-muted-foreground">
            <Icon name="search" className="h-3.5 w-3.5" />
            <input placeholder="搜索活动…" value={q} onChange={e => setQ(e.target.value)}
              className="w-56 bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground" />
          </div>
        </div>
        <span className="font-mono text-[11.5px] text-muted-foreground">{filtered.length} / {events.length} 个回合</span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto space-y-3 pr-1">
        {filtered.length === 0 && (
          <div className="text-center py-16 font-mono text-[11.5px] text-muted-foreground">没有匹配的活动</div>
        )}
        {filtered.map((e) =>
          <article key={e.id} className="rounded-xl border bg-card overflow-hidden transition-colors hover:bg-muted/20">
            <header className="flex items-center gap-2.5 border-b bg-muted/30 px-4 py-2.5">
              <Badge variant="brand">消息</Badge>
              <Avatar initial={user.handle[0].toUpperCase()} color="neutral" size={20} />
              <span className="text-[13px] font-medium">{user.handle}</span>
              <div className="flex-1" />
              {e.latest && <Badge variant="brand">最新</Badge>}
              <span className="font-mono text-[11px] text-muted-foreground">{e.when}</span>
              <span className="font-mono text-[11px] text-muted-foreground">{e.count} 个事件</span>
            </header>
            <div className="p-4 space-y-3">
              <button className="inline-flex items-center gap-2 rounded-md border border-dashed bg-background px-2 py-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                <Icon name="chevronRight" className="h-3 w-3" />
                <Icon name="settings" className="h-3 w-3" />
                <span className="font-mono text-[11.5px]">使用了 {e.tools.length} 个工具</span>
              </button>
              <p className="text-[13.5px] leading-relaxed" style={{ textWrap: "pretty" }}>{e.text}</p>
              {e.tail && <div><Badge variant="brand">运行中</Badge></div>}
            </div>
          </article>
        )}
      </div>
    </div>);
};

/* ═════════════════════ 日历 — Calendar ═════════════════════ */

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DOW_ABBR = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
const TODAY_STR = "2026-05-22"; // prototype "today"

const parseDate = (s) => { const [y,m,d] = s.split("-").map(Number); return new Date(y, m-1, d); };
const fmtDate = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const addDays = (s, n) => { const d = parseDate(s); d.setDate(d.getDate()+n); return fmtDate(d); };
const addMonths = (s, n) => { const d = parseDate(s); d.setMonth(d.getMonth()+n); return fmtDate(d); };
const startOfWeek = (s) => { const d = parseDate(s); d.setDate(d.getDate() - d.getDay()); return fmtDate(d); };
const startOfMonth = (s) => { const d = parseDate(s); d.setDate(1); return fmtDate(d); };

const CalendarView = ({ agent }) => {
  const { state, dispatch, toast, confirm } = useApp();
  const { cursor, view } = state.calendar;
  const setView = (v) => dispatch({ type: "setCalendar", patch: { view: v } });
  const setCursor = (c) => dispatch({ type: "setCalendar", patch: { cursor: c } });
  const events = state.calendarEvents;
  const hours = Array.from({ length: 12 }, (_, i) => `${i + 1} ${i + 1 < 12 ? "AM" : "PM"}`);

  const navPrev = () => setCursor(view === "month" ? addMonths(cursor, -1) : view === "week" ? addDays(cursor, -7) : addDays(cursor, -1));
  const navNext = () => setCursor(view === "month" ? addMonths(cursor, +1) : view === "week" ? addDays(cursor, +7) : addDays(cursor, +1));
  const goToday = () => setCursor(TODAY_STR);

  // Range label
  let rangeLabel = "";
  if (view === "month") {
    const d = parseDate(cursor);
    rangeLabel = `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`;
  } else if (view === "week") {
    const s = parseDate(startOfWeek(cursor));
    const e = new Date(s); e.setDate(s.getDate()+6);
    rangeLabel = `${MONTH_NAMES[s.getMonth()]} ${s.getDate()} – ${MONTH_NAMES[e.getMonth()]} ${e.getDate()}, ${e.getFullYear()}`;
  } else {
    const d = parseDate(cursor);
    rangeLabel = `${MONTH_NAMES[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  }

  const addEvent = () => {
    const day = view === "day" ? cursor : TODAY_STR;
    dispatch({ type: "addEvent", event: {
      id: uid("ev"), date: day, startHour: 10, endHour: 11, title: "新事件", tone: "brand"
    }});
    toast(`已添加事件到 ${day}`, { kind: "success" });
  };

  return (
    <div className="flex flex-col h-full px-6 py-5 gap-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant={cursor === TODAY_STR ? "brand" : "outline"} size="sm" onClick={goToday}>今天</Button>
          <Button variant="ghost" size="iconSm" onClick={navPrev}><Icon name="chevronLeft" className="h-3.5 w-3.5" /></Button>
          <Button variant="ghost" size="iconSm" onClick={navNext}><Icon name="chevronRight" className="h-3.5 w-3.5" /></Button>
          <div className="flex items-baseline gap-2">
            <strong className="text-base font-semibold tracking-tight">{rangeLabel}</strong>
            <span className="font-mono text-[11px] text-muted-foreground">· {agent.role}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Tabs value={view} onValueChange={setView}>
            <TabsList className="h-8">
              <TabsTrigger value="month" className="h-6 px-3">月</TabsTrigger>
              <TabsTrigger value="week"  className="h-6 px-3">周</TabsTrigger>
              <TabsTrigger value="day"   className="h-6 px-3">日</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="brand" size="sm" onClick={addEvent}>
            <Icon name="plus" className="h-3.5 w-3.5" /> 事件
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden rounded-xl border bg-card">
        {view === "week" && <CalendarWeek cursor={cursor} events={events} hours={hours}/>}
        {view === "month" && <CalendarMonth cursor={cursor} events={events} onPickDay={(d) => { setCursor(d); setView("day"); }}/>}
        {view === "day" && <CalendarDay cursor={cursor} events={events} hours={hours}/>}
      </div>
    </div>);
};

const CalendarWeek = ({ cursor, events, hours }) => {
  const start = parseDate(startOfWeek(cursor));
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start); d.setDate(start.getDate() + i);
    return { date: fmtDate(d), abbr: DOW_ABBR[i], n: d.getDate(), today: fmtDate(d) === TODAY_STR };
  });
  return (
    <div className="grid h-full" style={{ gridTemplateColumns: "60px repeat(7, 1fr)", gridTemplateRows: "56px 1fr" }}>
      <div className="border-b border-r flex items-center justify-center">
        <span className="font-mono text-[10.5px] text-muted-foreground">GMT+8</span>
      </div>
      {days.map((d) =>
        <div key={d.date} className={cn("border-b border-r last:border-r-0 flex flex-col items-center justify-center gap-0.5",
          d.today && "bg-muted/30")}>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{d.abbr}</div>
          {d.today ?
            <div className="grid h-8 w-8 place-items-center rounded-full bg-brand text-brand-foreground text-[15px] font-semibold tracking-tight">{d.n}</div> :
            <div className="text-[18px] font-semibold tracking-tight">{d.n}</div>
          }
        </div>
      )}

      <div className="border-r overflow-y-auto">
        {hours.map((h) =>
          <div key={h} className="h-[56px] border-b flex items-start justify-center pt-1 font-mono text-[10.5px] text-muted-foreground">
            {h}
          </div>
        )}
      </div>

      {days.map((d) =>
        <div key={d.date} className="relative border-r last:border-r-0 overflow-hidden">
          {hours.map((_, hi) => <div key={hi} className="h-[56px] border-b hover:bg-accent/30 transition-colors" />)}
          {events.filter(e => e.date === d.date).map((e) =>
            <div key={e.id}
              className={cn(
                "absolute left-1 right-1 rounded-md border-l-2 px-2 py-1 transition-transform hover:translate-x-0.5",
                e.tone === "brand" ? "bg-brand/10 border-brand text-brand" :
                "bg-emerald-500/10 border-emerald-500 text-emerald-700 dark:text-emerald-300"
              )}
              style={{ top: (e.startHour - 1) * 56, height: (e.endHour - e.startHour) * 56 - 4 }}>
              <div className="text-[11px] font-medium">{e.title}</div>
              <div className="font-mono text-[10px] opacity-75">{e.startHour}:00 — {e.endHour}:00</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const CalendarMonth = ({ cursor, events, onPickDay }) => {
  const monthStart = parseDate(startOfMonth(cursor));
  const gridStart = parseDate(startOfWeek(fmtDate(monthStart)));
  const cells = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart); d.setDate(gridStart.getDate() + i);
    return d;
  });
  const monthIdx = monthStart.getMonth();
  return (
    <div className="flex flex-col h-full">
      <div className="grid grid-cols-7 border-b">
        {DOW_ABBR.map(d => (
          <div key={d} className="border-r last:border-r-0 px-2 py-2 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground text-center">
            {d}
          </div>
        ))}
      </div>
      <div className="flex-1 grid grid-cols-7 grid-rows-6">
        {cells.map((d, i) => {
          const ds = fmtDate(d);
          const isMonth = d.getMonth() === monthIdx;
          const isToday = ds === TODAY_STR;
          const dayEvents = events.filter(e => e.date === ds);
          return (
            <button key={i} onClick={() => onPickDay(ds)}
              className={cn("flex flex-col items-start gap-1 border-r border-b last:border-r-0 px-2 py-1.5 text-left transition-colors hover:bg-accent/40",
                !isMonth && "bg-muted/20 text-muted-foreground/60")}>
              <div className={cn("font-mono text-[11px]", isToday && "grid h-5 w-5 place-items-center rounded-full bg-brand text-brand-foreground font-semibold")}>
                {d.getDate()}
              </div>
              <div className="space-y-0.5 w-full">
                {dayEvents.slice(0, 3).map(e => (
                  <div key={e.id} className={cn("rounded text-[10px] px-1.5 py-0.5 truncate",
                    e.tone === "brand" ? "bg-brand/10 text-brand" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300")}>
                    {e.title}
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className="font-mono text-[10px] text-muted-foreground px-1">+{dayEvents.length - 3} more</div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

const CalendarDay = ({ cursor, events, hours }) => {
  const d = parseDate(cursor);
  const today = fmtDate(d) === TODAY_STR;
  const dayEvents = events.filter(e => e.date === cursor);
  return (
    <div className="grid h-full" style={{ gridTemplateColumns: "60px 1fr", gridTemplateRows: "56px 1fr" }}>
      <div className="border-b border-r flex items-center justify-center">
        <span className="font-mono text-[10.5px] text-muted-foreground">GMT+8</span>
      </div>
      <div className={cn("border-b flex flex-col items-center justify-center gap-0.5", today && "bg-muted/30")}>
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{DOW_ABBR[d.getDay()]}</div>
        {today ?
          <div className="grid h-8 w-8 place-items-center rounded-full bg-brand text-brand-foreground text-[15px] font-semibold">{d.getDate()}</div> :
          <div className="text-[18px] font-semibold tracking-tight">{d.getDate()}</div>
        }
      </div>
      <div className="border-r overflow-y-auto">
        {hours.map((h) =>
          <div key={h} className="h-[56px] border-b flex items-start justify-center pt-1 font-mono text-[10.5px] text-muted-foreground">{h}</div>
        )}
      </div>
      <div className="relative overflow-y-auto">
        {hours.map((_, hi) => <div key={hi} className="h-[56px] border-b hover:bg-accent/30 transition-colors" />)}
        {dayEvents.map(e =>
          <div key={e.id}
            className={cn(
              "absolute left-2 right-2 rounded-md border-l-2 px-2 py-1",
              e.tone === "brand" ? "bg-brand/10 border-brand text-brand" :
              "bg-emerald-500/10 border-emerald-500 text-emerald-700 dark:text-emerald-300"
            )}
            style={{ top: (e.startHour - 1) * 56, height: (e.endHour - e.startHour) * 56 - 4 }}>
            <div className="text-[13px] font-medium">{e.title}</div>
            <div className="font-mono text-[11px] opacity-75">{e.startHour}:00 — {e.endHour}:00</div>
          </div>
        )}
      </div>
    </div>
  );
};

/* ═════════════════════ 频道 — Channels ═════════════════════ */

const ChannelsView = ({ agent }) => {
  const { state, toast } = useApp();
  const [sel, setSel] = React.useState(null);
  const [filter, setFilter] = React.useState("all");
  const [q, setQ] = React.useState("");
  // Combine plain channels + groups (channel-like)
  const channels = state.channels.concat(
    (DATA_EXTRA.groups || []).filter(g => !state.channels.find(c => c.id === g.id))
  );
  const filtered = channels.filter(c => {
    if (filter === "dm") return false;     // no DMs in mock
    if (q && !c.name.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });
  return (
    <div className="grid h-full" style={{ gridTemplateColumns: "260px 1fr" }}>
      <aside className="flex flex-col border-r bg-muted/20 p-3 gap-3 min-h-0">
        <div className="flex h-8 items-center gap-2 rounded-md border bg-background px-2.5 text-muted-foreground">
          <Icon name="search" className="h-3.5 w-3.5" />
          <input placeholder="搜索 AI 频道…" value={q} onChange={e => setQ(e.target.value)}
            className="flex-1 bg-transparent text-[12.5px] outline-none" />
        </div>
        <Tabs value={filter} onValueChange={setFilter}>
          <TabsList className="h-8 w-full">
            <TabsTrigger value="all"   className="flex-1 h-6">全部</TabsTrigger>
            <TabsTrigger value="dm"    className="flex-1 h-6">私信</TabsTrigger>
            <TabsTrigger value="group" className="flex-1 h-6">群组</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex-1 min-h-0 overflow-y-auto space-y-px">
          {filtered.length === 0 && (
            <div className="px-3 py-8 text-center font-mono text-[11px] text-muted-foreground/70">没有匹配项</div>
          )}
          {filtered.map((c) =>
            <button key={c.id} onClick={() => setSel(c.id)}
              data-active={sel === c.id ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] text-left",
                "text-muted-foreground hover:bg-accent hover:text-foreground transition-colors",
                "data-[active=true]:bg-accent data-[active=true]:text-foreground data-[active=true]:font-medium"
              )}>
              <span className="font-mono text-muted-foreground/70">#</span>
              <span className="flex-1 truncate">{c.name}</span>
              {c.unread && <span className="h-1.5 w-1.5 rounded-full bg-brand" />}
            </button>
          )}
        </div>
      </aside>
      <div className="min-h-0 overflow-y-auto p-6">
        {sel ?
          <ChannelDetail channel={channels.find((c) => c.id === sel)} agent={agent} /> :
          <EmptyState icon="channels" title="选择一个 AI 频道" desc={`查看 ${agent.name} 在其中的对话。`} />
        }
      </div>
    </div>);
};

const ChannelDetail = ({ channel, agent }) => {
  const { nav, toast } = useApp();
  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between border-b pb-4">
        <h2 className="text-xl font-semibold tracking-tight flex items-center gap-1.5">
          <span className="text-muted-foreground/70 font-mono">#</span>{channel.name}
        </h2>
        <div className="flex gap-1">
          <Button variant="ghost" size="iconSm" onClick={() => toast("成员列表 — 进入频道查看", { kind: "info" })}>
            <Icon name="people" className="h-3.5 w-3.5" /></Button>
          <Button variant="ghost" size="iconSm" onClick={() => toast("通知设置 — 全部 / 仅提及 / 静音", { kind: "info" })}>
            <Icon name="bell" className="h-3.5 w-3.5" /></Button>
          <Button variant="ghost" size="iconSm" onClick={() => toast("已置顶频道", { kind: "success" })}>
            <Icon name="pin" className="h-3.5 w-3.5" /></Button>
        </div>
      </header>
      <div className="rounded-xl border bg-gradient-to-br from-brand/5 to-transparent p-5">
        <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-brand/10 text-brand">
          <Icon name="hash" className="h-5 w-5" />
        </div>
        <h3 className="text-xl font-semibold tracking-tight mb-1.5">欢迎来到 #{channel.name}</h3>
        <p className="text-[13px] text-muted-foreground leading-relaxed max-w-md">
          邀请需要关注这项工作的成员，或添加频道描述，让队友知道这个频道用来做什么。
        </p>
        <div className="mt-4 flex gap-2">
          <Button variant="outline" size="sm" onClick={() => nav({ section: "group", groupId: channel.id })}>
            <Icon name="arrowRight" className="h-3.5 w-3.5"/> 打开频道
          </Button>
          <Button variant="outline" size="sm" onClick={() => toast("邀请链接已复制", { kind: "success" })}>
            <Icon name="people" className="h-3.5 w-3.5" /> 邀请队友
          </Button>
          <Button variant="outline" size="sm" onClick={() => toast("（占位）添加描述对话框", { kind: "info" })}>
            <Icon name="list" className="h-3.5 w-3.5" /> 添加描述
          </Button>
        </div>
      </div>
      <div className="space-y-1 font-mono text-[11.5px] text-muted-foreground">
        <div>· {agent.name} 创建了频道 · 5月21日 19:48</div>
        <div>· {agent.name} 加入频道 · 5月21日 19:48</div>
      </div>
    </div>
  );
};

/* ═════════════════════ 文件 — Files ═════════════════════ */

const FilesView = () => {
  const { state, dispatch, toast } = useApp();
  const outputs = state.outputs;
  const fileRef = React.useRef(null);
  const [spin, setSpin] = React.useState(false);

  const onUpload = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    files.forEach(f => {
      const reader = new FileReader();
      reader.onload = () => {
        dispatch({ type: "addOutput", output: {
          id: uid("f"), name: f.name,
          kind: /\.diff$/i.test(f.name) ? "diff" : "doc",
          size: `${Math.ceil(f.size / 1024)} KB`,
          status: "input",
          dataURL: reader.result,
        }});
      };
      reader.readAsDataURL(f);
    });
    toast(`已上传 ${files.length} 个文件`, { kind: "success" });
    e.target.value = "";
  };

  const onRefresh = () => {
    setSpin(true);
    setTimeout(() => { setSpin(false); toast("已刷新文件列表", { kind: "success" }); }, 600);
  };

  return (
    <div className="flex flex-col h-full px-6 py-5 gap-4">
      <input ref={fileRef} type="file" multiple className="hidden" onChange={onUpload}/>
      <header className="flex items-center justify-between border-b pb-4">
        <div>
          <h2 className="text-base font-semibold tracking-tight flex items-center gap-2">
            <Icon name="files" className="h-4 w-4 text-muted-foreground" /> 文件
          </h2>
          <p className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-1">频道共享文件 · {outputs.length} 个</p>
        </div>
        <div className="flex gap-1">
          <Button variant="ghost" size="iconSm" onClick={() => fileRef.current?.click()} title="上传">
            <Icon name="upload" className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm" onClick={onRefresh} title="刷新">
            <Icon name="refresh" className={cn("h-3.5 w-3.5 transition-transform", spin && "animate-spin")} />
          </Button>
        </div>
      </header>
      {outputs.length === 0 ?
        <EmptyState icon="files" title="未关联文件" desc="拖到这里，或点右上「上传」。" /> :
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
          {outputs.map((f) =>
            <FileCard key={f.id} f={f} onDelete={() => {
              dispatch({ type: "deleteOutput", id: f.id });
              toast(`已删除「${f.name}」`, { kind: "success" });
            }}/>
          )}
        </div>
      }
    </div>);
};

const FileCard = ({ f, onDelete }) => {
  const { confirm, toast } = useApp();
  return (
    <div className="group/file relative rounded-xl border bg-card p-4 space-y-2 transition-all hover:-translate-y-px hover:shadow-sm">
      <div className="grid h-10 w-10 place-items-center rounded-md border bg-muted/30">
        <Icon name={f.kind === "diff" ? "diff" : "doc"} className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="font-mono text-[13px] truncate">{f.name}</div>
      <div className="font-mono text-[11px] text-muted-foreground">
        {f.kind === "diff" ? "Diff" : "Document"} · {f.size}
      </div>
      <button onClick={() => confirm({
        title: `删除「${f.name}」?`, desc: "文件会从产出列表移除，不可撤销。", danger: true,
        confirmLabel: "删除", onConfirm: onDelete
      })}
        className="absolute top-2 right-2 opacity-0 group-hover/file:opacity-100 transition-opacity grid h-6 w-6 place-items-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10">
        <Icon name="trash" className="h-3 w-3"/>
      </button>
    </div>
  );
};

/* ═════════════════════ 技能 — Skills ═════════════════════ */

const SkillsView = () => {
  const { state, dispatch, toast, confirm } = useApp();
  const skills = state.skills;
  const [tab, setTab] = React.useState("installed");
  const [q, setQ] = React.useState("");
  const [showAdd, setShowAdd] = React.useState(false);
  const filtered = skills.filter(s => !q || (s.name + " " + s.desc).toLowerCase().includes(q.toLowerCase()));
  const browseFiltered = DATA_EXTRA.skillCatalog
    .filter(s => !skills.some(inst => inst.id === s.id))
    .filter(s => !q || (s.name + " " + s.desc).toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="flex flex-col px-6 py-5 gap-4">
      <div className="flex items-center justify-between">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="h-8">
            <TabsTrigger value="installed" className="h-6 px-3">已安装 ({skills.length})</TabsTrigger>
            <TabsTrigger value="browse"    className="h-6 px-3">浏览</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button variant="outline" size="sm" onClick={() => setShowAdd(true)}>
          <Icon name="plus" className="h-3.5 w-3.5" /> 手动添加
        </Button>
      </div>
      <div className="flex h-9 items-center gap-2 rounded-md border bg-background px-2.5 text-muted-foreground">
        <Icon name="search" className="h-3.5 w-3.5" />
        <input placeholder="筛选技能…" value={q} onChange={e => setQ(e.target.value)}
          className="flex-1 bg-transparent text-[13px] outline-none" />
      </div>
      {tab === "installed" ? (
        <section className="rounded-xl border bg-card overflow-hidden">
          <header className="flex items-center justify-between border-b px-4 py-2.5 bg-muted/30">
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">内置</span>
            <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">{filtered.length}</span>
          </header>
          {filtered.map((s, i) =>
            <div key={s.id} className={cn("flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/30", i !== 0 && "border-t")}>
              <div className="grid h-8 w-8 place-items-center rounded-md bg-brand/10 text-brand">
                <Icon name="sparkle" className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[13.5px] font-medium">{s.name}</div>
                <div className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">{s.desc}</div>
              </div>
              {s.locked ? (
                <Button variant="ghost" size="iconSm" className="text-muted-foreground" title="内置技能不可移除"
                  onClick={() => toast("此技能锁定，无法移除", { kind: "info" })}>
                  <Icon name="lock" className="h-3.5 w-3.5" />
                </Button>
              ) : (
                <Button variant="ghost" size="iconSm" className="text-muted-foreground hover:text-destructive"
                  onClick={() => confirm({
                    title: `移除「${s.name}」?`, desc: "助手将不再使用该技能。", danger: true,
                    onConfirm: () => {
                      dispatch({ type: "removeSkill", id: s.id });
                      toast(`已移除「${s.name}」`, { kind: "success" });
                    }
                  })}>
                  <Icon name="trash" className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          )}
        </section>
      ) : (
        <section className="rounded-xl border bg-card overflow-hidden">
          <header className="flex items-center justify-between border-b px-4 py-2.5 bg-muted/30">
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">技能仓库</span>
            <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">{browseFiltered.length}</span>
          </header>
          {browseFiltered.length === 0 ? (
            <div className="px-4 py-10 text-center font-mono text-[11px] text-muted-foreground">仓库已经装完了</div>
          ) : browseFiltered.map((s, i) => (
            <div key={s.id} className={cn("flex items-start gap-3 px-4 py-3 transition-colors hover:bg-muted/30", i !== 0 && "border-t")}>
              <div className="grid h-8 w-8 place-items-center rounded-md bg-muted/40 text-muted-foreground">
                <Icon name="sparkle" className="h-3.5 w-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[13.5px] font-medium">{s.name}</div>
                <div className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">{s.desc}</div>
              </div>
              <Button variant="brand" size="sm"
                onClick={() => {
                  dispatch({ type: "addSkill", skill: { ...s, locked: false } });
                  toast(`已安装「${s.name}」`, { kind: "success" });
                }}>
                <Icon name="plus" className="h-3 w-3"/> 安装
              </Button>
            </div>
          ))}
        </section>
      )}

      <ManualSkillModal open={showAdd} onClose={() => setShowAdd(false)} />
    </div>);
};

const ManualSkillModal = ({ open, onClose }) => {
  const { dispatch, toast } = useApp();
  const [name, setName] = React.useState("");
  const [desc, setDesc] = React.useState("");
  React.useEffect(() => { if (open) { setName(""); setDesc(""); } }, [open]);
  const submit = () => {
    if (!name.trim()) return;
    dispatch({ type: "addSkill", skill: { id: "custom-" + uid(""), name: name.trim(), desc: desc.trim() || "用户自定义技能。", locked: false } });
    toast(`已添加「${name.trim()}」`, { kind: "success" });
    onClose();
  };
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="w-[440px]">
        <header className="flex items-center justify-between border-b px-5 py-3.5">
          <h3 className="text-base font-semibold tracking-tight">手动添加技能</h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5"/>
          </Button>
        </header>
        <div className="p-5 space-y-3">
          <FormRow title="技能名称">
            <Input placeholder="比如 web-search" value={name} onChange={e => setName(e.target.value)} autoFocus/>
          </FormRow>
          <FormRow title="说明">
            <Textarea rows={3} placeholder="一句话讲清楚做什么。" value={desc} onChange={e => setDesc(e.target.value)}/>
          </FormRow>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t bg-muted/20 px-5 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
          <Button variant="brand" size="sm" disabled={!name.trim()} onClick={submit}>添加</Button>
        </footer>
      </DialogContent>
    </Dialog>
  );
};

/* ═════════════════════ 记忆 — Memory ═════════════════════ */

const MemoryView = () => {
  const { state, dispatch, toast, confirm } = useApp();
  const memory = state.memory;
  const [sel, setSel] = React.useState(memory[0]?.id);
  const [sort, setSort] = React.useState("recent");
  const [q, setQ] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState(null);

  const filtered = memory.filter(m => {
    if (statusFilter && m.status !== statusFilter) return false;
    if (sort === "all") return true;
    if (q) {
      const hay = (m.title + " " + m.body + " " + m.tags.join(" ")).toLowerCase();
      if (!hay.includes(q.toLowerCase())) return false;
    }
    return true;
  });

  React.useEffect(() => {
    if (filtered.length && !filtered.some(m => m.id === sel)) setSel(filtered[0].id);
  }, [filtered.length]);

  const item = memory.find((m) => m.id === sel);
  const updateStatus = (id, status, label) => {
    dispatch({ type: "updateMemory", id, patch: { status } });
    toast(`已${label}`, { kind: "success" });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 pt-5 pb-3 space-y-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 items-center gap-2 rounded-md border bg-background px-2.5 text-muted-foreground">
            <Icon name="search" className="h-3.5 w-3.5" />
            <input placeholder="搜索记忆…" value={q} onChange={e => setQ(e.target.value)}
              className="w-56 bg-transparent text-[12.5px] outline-none" />
          </div>
          <StatusFilterMenu value={statusFilter} onChange={setStatusFilter}/>
        </div>
        <div className="flex items-center gap-5 border-b -mb-px">
          {[["recent", "最近"], ["all", "全部"], ["state", "按状态"]].map(([v, l]) =>
            <button key={v} onClick={() => setSort(v)}
              className={cn("pb-2 text-[12.5px] transition-colors border-b-2",
                sort === v ? "border-brand text-foreground font-medium" : "border-transparent text-muted-foreground hover:text-foreground")}>
              {l}
            </button>
          )}
          <span className="font-mono text-[11px] text-muted-foreground pb-2 -ml-3">· {filtered.length} 条结果</span>
        </div>
      </div>

      <div className="flex-1 min-h-0 grid border-t" style={{ gridTemplateColumns: "300px 1fr" }}>
        <aside className="border-r bg-muted/20 p-2 overflow-y-auto">
          {filtered.length === 0 && (
            <div className="px-3 py-8 text-center font-mono text-[11px] text-muted-foreground/70">没有匹配项</div>
          )}
          {filtered.map((m) =>
            <button key={m.id} onClick={() => setSel(m.id)}
              data-active={sel === m.id ? "true" : undefined}
              className={cn(
                "flex w-full flex-col items-start gap-1 rounded-md px-3 py-2.5 text-left mb-0.5 transition-colors",
                "hover:bg-accent",
                "data-[active=true]:bg-accent"
              )}>
              <div className="text-[13px] font-medium truncate w-full">{m.title}</div>
              <div className="flex items-center gap-2">
                <Badge variant={m.status === "accepted" ? "success" : m.status === "pending" ? "brand" : "outline"}>
                  {m.status === "accepted" ? "已接受" : m.status === "pending" ? "待确认" : "已归档"}
                </Badge>
                <span className="font-mono text-[10.5px] text-muted-foreground">{m.when}</span>
              </div>
            </button>
          )}
        </aside>
        <div className="overflow-y-auto p-7">
          {item ?
            <div className="space-y-4">
              <header>
                <h2 className="text-xl font-semibold tracking-tight mb-2">{item.title}</h2>
                <div className="flex gap-1.5">
                  {item.tags.map((t) =>
                    <span key={t} className="rounded border px-2 py-0.5 font-mono text-[10.5px] text-muted-foreground">{t}</span>
                  )}
                </div>
              </header>
              <p className="text-[14px] leading-relaxed" style={{ textWrap: "pretty" }}>{item.body}</p>
              <div className="flex gap-2">
                <Button variant={item.status === "accepted" ? "brand" : "outline"} size="sm"
                  onClick={() => updateStatus(item.id, "accepted", "接受")}>接受</Button>
                <Button variant={item.status === "pending" ? "brand" : "outline"} size="sm"
                  onClick={() => updateStatus(item.id, "pending", "标记待确认")}>延后</Button>
                <Button variant={item.status === "archived" ? "secondary" : "outline"} size="sm"
                  onClick={() => updateStatus(item.id, "archived", "归档")}>归档</Button>
                <div className="flex-1"/>
                <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive"
                  onClick={() => confirm({
                    title: `删除「${item.title}」?`, desc: "记忆会从此助手中移除。", danger: true,
                    onConfirm: () => {
                      dispatch({ type: "deleteMemory", id: item.id });
                      toast("已删除", { kind: "success" });
                    }
                  })}>
                  <Icon name="trash" className="h-3 w-3"/> 删除
                </Button>
              </div>
            </div> :
            <EmptyState icon="brain" title="选择左侧的一条记忆" desc="点开后可以接受、延后或归档。" />
          }
        </div>
      </div>
    </div>);
};

const StatusFilterMenu = ({ value, onChange }) => {
  const [open, setOpen] = React.useState(false);
  const opts = [["accepted", "已接受"], ["pending", "待确认"], ["archived", "已归档"]];
  return (
    <div className="relative">
      <Button variant={value ? "secondary" : "outline"} size="sm" onClick={() => setOpen(v => !v)}>
        {value ? opts.find(o => o[0] === value)?.[1] : "状态"}
        {value
          ? <Icon name="x" className="h-3 w-3 ml-1" onClick={e => { e.stopPropagation(); onChange(null); }}/>
          : <Icon name="chevronDown" className="h-3 w-3"/>}
      </Button>
      {open && (
        <div className="absolute left-0 top-9 w-40 rounded-lg border bg-popover p-1 shadow-lg z-20"
          onMouseLeave={() => setOpen(false)}>
          {opts.map(([v, l]) =>
            <button key={v} onClick={() => { onChange(v); setOpen(false); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left">
              {l}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

/* ═════════════════════ 设置 — Settings ═════════════════════ */

const SettingsView = ({ agent }) => {
  const { dispatch, toast, confirm } = useApp();
  const displayName = agent.name === "编辑" ? "Content editor" : agent.name === "文案" ? "Copywriter" : "Researcher";
  const initialDesc = "Revises existing drafts for clarity, structure, voice, and trust while preserving the author's intent. Wake for line edits, structural revisions, tone alignment, or final polish on existing prose — not for first-draft writing or strategic messaging direction.";

  const [name, setName] = React.useState(displayName);
  const [desc, setDesc] = React.useState(initialDesc);
  const [dirty, setDirty] = React.useState(false);
  const [avatarURL, setAvatarURL] = React.useState(null);
  const fileRef = React.useRef(null);

  React.useEffect(() => {
    setDirty(name !== displayName || desc !== initialDesc || !!avatarURL);
  }, [name, desc, avatarURL]);

  const onAvatar = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => { setAvatarURL(r.result); toast("头像已加载，点保存生效", { kind: "info" }); };
    r.readAsDataURL(f);
    e.target.value = "";
  };
  const onSave = () => {
    dispatch({ type: "updateAgent", id: agent.id, patch: { name: name.split(" ")[0] || name } });
    toast("已保存更改", { kind: "success" });
    setDirty(false);
  };
  const onReset = () => { setName(displayName); setDesc(initialDesc); setAvatarURL(null); toast("已重置", { kind: "info" }); };
  const onDelete = () => confirm({
    title: `删除助手「${agent.name}」?`,
    desc: "将助手从你的侧边栏和所有频道中移除。历史消息仍会保留。此操作无法撤销。",
    danger: true,
    confirmLabel: "删除",
    onConfirm: () => {
      dispatch({ type: "deleteAgent", id: agent.id });
      toast(`已删除「${agent.name}」`, { kind: "success" });
    }
  });

  return (
    <div className="relative">
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onAvatar}/>
      <div className="mx-auto max-w-[760px] px-6 py-6 pb-24 space-y-7">
        {/* Identity */}
        <section>
          <div className="inline-flex items-center gap-2 rounded-t-lg border border-b-0 bg-muted/30 px-3 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse-dot" />
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">HELIO · 身份</span>
            <span className="flex-1 w-16" />
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-medium">已生效</span>
          </div>
          <div className="rounded-r-xl rounded-bl-xl rounded-tl-none border bg-card p-5 flex gap-5">
            <div className="relative">
              {avatarURL ? (
                <img src={avatarURL} alt="" className="h-[72px] w-[72px] rounded-full object-cover"/>
              ) : (
                <Avatar initial={agent.name[0]} color={agent.color} size={72} />
              )}
              <button onClick={() => fileRef.current?.click()}
                className="absolute -right-1 -bottom-1 grid h-6 w-6 place-items-center rounded-md border bg-background text-muted-foreground hover:text-foreground transition-colors">
                <Icon name="files" className="h-3 w-3" />
              </button>
            </div>
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-2xl font-semibold tracking-tight">{name}</h2>
                <Badge variant="brand">AI</Badge>
              </div>
              <p className="border-l-2 border-brand pl-3 text-[13px] text-muted-foreground leading-relaxed" style={{ textWrap: "pretty" }}>
                {desc}
              </p>
              <div className="flex items-center gap-3 font-mono text-[11px] text-muted-foreground">
                <span className="inline-flex items-center gap-1.5"><Icon name="mail" className="h-3 w-3" />未设置邮箱</span>
                <span className="flex-1" />
                <span className="tracking-wider">ID · {agent.id.slice(0, 6).toUpperCase()}…{(agent.id.slice(-6) || "").toUpperCase()}</span>
              </div>
            </div>
          </div>
        </section>

        <FormRow title="显示名称" desc="此助手在提及、会话和私信中显示的名称。">
          <Input value={name} onChange={e => setName(e.target.value)}/>
        </FormRow>

        <FormRow title="模型" desc="在助手创建时锁定。若需使用其他模型，请新建一个助手。">
          <div className="flex h-9 items-center gap-2 rounded-md border bg-muted/30 px-3 font-mono text-[12.5px] text-muted-foreground">
            <Icon name="lock" className="h-3 w-3" />
            <span>claude-sonnet-4-5</span>
          </div>
        </FormRow>

        <FormRow title="简介" desc="此助手的简短描述 — 它做什么，以及队友什么时候应该叫上它。" count={`${desc.length} / 500`}>
          <Textarea rows={4} value={desc} onChange={e => setDesc(e.target.value.slice(0, 500))}/>
        </FormRow>

        <FormRow title="已订阅频道" desc="此助手会在哪些频道监听。可在频道标签页管理。">
          <div className="flex h-9 items-center gap-2 rounded-md border bg-muted/30 px-3 font-mono text-[12.5px] text-muted-foreground">
            <Icon name="channels" className="h-3 w-3" />
            <span>尚未订阅任何频道。</span>
          </div>
        </FormRow>

        <section className="space-y-3">
          <header><h3 className="text-[15px] font-semibold tracking-tight text-destructive">危险区域</h3></header>
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 space-y-3">
            <p className="text-[13px] leading-relaxed text-muted-foreground">
              会将助手从你的侧边栏和所属的所有频道中移除。历史消息仍会显示。部分相关数据可能保留。此操作无法撤销。
            </p>
            <div className="flex justify-end">
              <Button variant="destructive" size="sm" onClick={onDelete}>删除助手</Button>
            </div>
          </div>
        </section>
      </div>

      <div className="sticky bottom-0 bg-gradient-to-t from-background via-background to-transparent pt-6">
        <div className="mx-auto max-w-[760px] px-6 py-3 flex justify-end gap-2">
          <Button variant="outline" disabled={!dirty} onClick={onReset}>重置</Button>
          <Button variant="brand" disabled={!dirty} onClick={onSave}>保存更改</Button>
        </div>
      </div>
    </div>);
};

const FormRow = ({ title, desc, count, children }) =>
  <section className="space-y-2">
    <header className="relative">
      <h3 className="text-[15px] font-semibold tracking-tight">{title}</h3>
      {desc && <p className="text-[12.5px] text-muted-foreground mt-0.5">{desc}</p>}
      {count && <span className="absolute right-0 top-0 font-mono text-[10.5px] text-muted-foreground">{count}</span>}
    </header>
    {children}
  </section>;


/* ═════════════════════ Empty state ═════════════════════ */

const EmptyState = ({ icon, title, desc }) =>
  <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 text-center text-muted-foreground">
    <div className="mb-1 grid h-12 w-12 place-items-center rounded-xl border bg-muted/30">
      <Icon name={icon} className="h-5 w-5" />
    </div>
    <div className="text-[15px] font-semibold text-foreground">{title}</div>
    <div className="text-[12.5px] max-w-[280px] leading-relaxed">{desc}</div>
  </div>;


/* ═════════════════════ Create Task Modal ═════════════════════ */

const CreateTaskModal = ({ open, onClose, agent }) => {
  const { state, dispatch, toast } = useApp();
  const [title, setTitle] = React.useState("");
  const [priority, setPriority] = React.useState("normal");
  const [assignee, setAssignee] = React.useState(agent.id);
  const [due, setDue] = React.useState("—");
  const editorRef = React.useRef(null);
  const [open_, setOpenMenu] = React.useState(null);

  React.useEffect(() => {
    if (open) {
      setTitle(""); setPriority("normal"); setAssignee(agent.id); setDue("—"); setOpenMenu(null);
      if (editorRef.current) editorRef.current.innerHTML = "";
    }
  }, [open, agent.id]);

  const exec = (cmd, arg) => {
    if (editorRef.current) editorRef.current.focus();
    try { document.execCommand(cmd, false, arg); } catch (e) {}
  };
  const promptLink = () => {
    const url = window.prompt("链接 URL", "https://");
    if (url) exec("createLink", url);
  };

  const RtBtn = ({ icon, cmd, arg, title, onClick }) =>
    <Button variant="ghost" size="iconSm" className="h-7 w-7 text-muted-foreground" title={title}
      onMouseDown={e => e.preventDefault()}
      onClick={onClick || (() => exec(cmd, arg))}>
      <Icon name={icon} className="h-3.5 w-3.5" />
    </Button>;
  const Sep = () => <div className="h-4 w-px bg-border mx-0.5" />;

  const submit = () => {
    if (!title.trim()) return;
    const id = "T-" + (state.tasks.length + 1);
    dispatch({ type: "addTask", task: {
      id, title: title.trim(), state: "todo", priority, assignee, due,
      description: editorRef.current?.innerHTML || "",
    }});
    toast(`已创建任务「${title.trim()}」`, {
      kind: "success",
      action: { label: "打开", onClick: () => dispatch({ type: "set", patch: { section: "tasks" } }) }
    });
    onClose();
  };

  const agentOptions = state.agents;
  const dueOptions = ["—", "今天", "明天", "本周内", "周一", "周三", "周五"];

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <header className="flex items-center justify-between border-b px-5 py-3.5">
          <h3 className="text-base font-semibold tracking-tight">创建任务</h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          <Input placeholder="任务标题" value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="h-11 text-[15px] font-medium" autoFocus/>
          <div>
            <div className="flex items-center gap-0.5 rounded-t-md border border-b-0 bg-muted/30 px-2 py-1.5">
              <RtBtn icon="bold"      cmd="bold"          title="加粗"/>
              <RtBtn icon="italic"    cmd="italic"        title="斜体"/>
              <RtBtn icon="underline" cmd="underline"     title="下划线"/>
              <Sep />
              <RtBtn icon="link"      title="链接" onClick={promptLink}/>
              <Sep />
              <RtBtn icon="list"      cmd="insertUnorderedList" title="无序列表"/>
              <RtBtn icon="listCheck" cmd="insertOrderedList"   title="有序列表"/>
              <Sep />
              <RtBtn icon="code"      cmd="formatBlock" arg="pre" title="代码块"/>
            </div>
            <div ref={editorRef} contentEditable suppressContentEditableWarning
              data-placeholder="添加任务描述…"
              className="min-h-[140px] rounded-b-md border bg-background px-3 py-2.5 text-[13.5px] leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring empty:before:content-[attr(data-placeholder)] empty:before:text-muted-foreground"/>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <MetaChip icon="flag" label={PRIORITY_LABEL[priority]} active={open_ === "p"}
              onClick={() => setOpenMenu(open_ === "p" ? null : "p")}>
              {["high","normal","low"].map(p =>
                <button key={p} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left"
                  onClick={() => { setPriority(p); setOpenMenu(null); }}>{PRIORITY_LABEL[p]}</button>
              )}
            </MetaChip>
            <MetaChip icon="people" label={agentOptions.find(a => a.id === assignee)?.name || "分配"} active={open_ === "a"}
              onClick={() => setOpenMenu(open_ === "a" ? null : "a")}>
              {agentOptions.map(a =>
                <button key={a.id} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left"
                  onClick={() => { setAssignee(a.id); setOpenMenu(null); }}>
                  <Avatar initial={a.name[0]} color={a.color} size={18}/> {a.name}
                </button>
              )}
            </MetaChip>
            <MetaChip icon="calendar" label={due === "—" ? "没有截止日期" : due} active={open_ === "d"}
              onClick={() => setOpenMenu(open_ === "d" ? null : "d")}>
              {dueOptions.map(d =>
                <button key={d} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] hover:bg-accent text-left"
                  onClick={() => { setDue(d); setOpenMenu(null); }}>{d === "—" ? "没有截止日期" : d}</button>
              )}
            </MetaChip>
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t bg-muted/20 px-5 py-3">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button variant="brand" disabled={!title.trim()} onClick={submit}>创建任务</Button>
        </footer>
      </DialogContent>
    </Dialog>);
};

const MetaChip = ({ icon, label, active, onClick, children }) =>
  <div className="relative">
    <button onClick={onClick}
      data-active={active ? "true" : undefined}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-md border bg-background px-2.5 text-[12px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors whitespace-nowrap",
        "data-[active=true]:bg-brand/10 data-[active=true]:text-brand data-[active=true]:border-brand/30"
      )}>
      <Icon name={icon} className="h-3 w-3" />
      {label}
      <Icon name="chevronDown" className="h-2.5 w-2.5"/>
    </button>
    {active && (
      <div className="absolute left-0 top-9 w-48 rounded-lg border bg-popover p-1 shadow-lg z-30">
        {children}
      </div>
    )}
  </div>;


/* ═════════════════════ Tasks / Calendar full-page wrappers ═════════════════════ */

const FullPageFrame = ({ icon, title, subtitle, actions, children }) => (
  <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
    <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
      <div className="flex items-center gap-3">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand/10 text-brand flex-shrink-0">
          <Icon name={icon} className="h-4 w-4"/>
        </div>
        <div>
          <h1 className="heading-serif text-[20px] font-medium tracking-tight">{title}</h1>
          {subtitle && (
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-0.5">
              {subtitle}
            </div>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-1">{actions}</div>}
    </header>
    <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
  </main>
);

const TasksPage = ({ openCreate }) => {
  const { state } = useApp();
  const tasks = state.tasks;
  const agents = state.agents;
  const [filterAgent, setFilterAgent] = React.useState(null);
  const byAgent = agents.map((a) => ({ ...a, count: tasks.filter((t) => t.assignee === a.id).length }));
  const open = tasks.filter((t) => t.state !== "done").length;
  const blocked = tasks.filter((t) => t.state === "blocked").length;
  const done = tasks.filter((t) => t.state === "done").length;
  return (
    <FullPageFrame icon="listCheck" title="任务"
      subtitle={`${tasks.length} 个任务 · 跨所有助手`}
      actions={
        <Button variant="brand" size="sm" onClick={openCreate}>
          <Icon name="plus" className="h-3.5 w-3.5"/>创建任务
        </Button>
      }>
      <div className="px-6 py-5 grid gap-4" style={{ gridTemplateRows: "auto 1fr", height: "100%" }}>
        <div className="grid grid-cols-4 gap-3">
          {[{ label: "总计",     value: tasks.length, sub: "all",     tone: "muted" },
            { label: "未完成",   value: open,         sub: "open",    tone: "brand" },
            { label: "阻塞",     value: blocked,      sub: "blocked", tone: "warning" },
            { label: "本周完成", value: done,         sub: "done",    tone: "success" }].map((s) => (
            <div key={s.label} className="rounded-xl border bg-card p-4">
              <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">{s.label}</div>
              <div className="mt-1 flex items-baseline gap-1.5">
                <div className={cn("text-2xl font-semibold tracking-tight tabular-nums",
                  s.tone === "brand"   && "text-brand",
                  s.tone === "warning" && "text-amber-700 dark:text-amber-400",
                  s.tone === "success" && "text-emerald-700 dark:text-emerald-400"
                )}>{s.value}</div>
                <div className="font-mono text-[10.5px] text-muted-foreground">{s.sub}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="grid gap-3 min-h-0" style={{ gridTemplateColumns: "260px 1fr" }}>
          <aside className="rounded-xl border bg-card overflow-hidden flex flex-col min-h-0">
            <header className="border-b px-3 py-2.5">
              <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">按助手</div>
            </header>
            <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
              <button onClick={() => setFilterAgent(null)}
                data-active={!filterAgent ? "true" : undefined}
                className="flex items-center w-full gap-2 rounded-md px-2 py-1.5 text-[13px] text-muted-foreground hover:bg-accent hover:text-foreground data-[active=true]:bg-accent data-[active=true]:text-foreground data-[active=true]:font-medium transition-colors">
                <Icon name="layers" className="h-3.5 w-3.5"/>
                <span className="flex-1 text-left">全部</span>
                <span className="font-mono text-[11px] tabular-nums">{tasks.length}</span>
              </button>
              {byAgent.map((a) => (
                <button key={a.id} onClick={() => setFilterAgent(a.id)}
                  data-active={filterAgent === a.id ? "true" : undefined}
                  className="flex items-center w-full gap-2 rounded-md px-2 py-1.5 text-[13px] text-muted-foreground hover:bg-accent hover:text-foreground data-[active=true]:bg-accent data-[active=true]:text-foreground data-[active=true]:font-medium transition-colors">
                  <Avatar initial={a.name[0]} color={a.color} size={18}/>
                  <span className="flex-1 text-left">{a.name}</span>
                  <span className="font-mono text-[11px] tabular-nums">{a.count}</span>
                </button>
              ))}
            </div>
          </aside>
          <div className="rounded-xl border bg-card overflow-hidden flex flex-col min-h-0">
            <TasksTabView openCreate={openCreate} filterAgentId={filterAgent}/>
          </div>
        </div>
      </div>
    </FullPageFrame>
  );
};

const CalendarPage = ({ agent }) => (
  <FullPageFrame icon="calendar" title="日历" subtitle="工作排程概览">
    <CalendarView agent={agent}/>
  </FullPageFrame>
);


Object.assign(window, {
  ChatView, TasksTabView, ActivityView, CalendarView, ChannelsView,
  FilesView, SkillsView, MemoryView, SettingsView, CreateTaskModal,
  EmptyState, FullPageFrame, TasksPage, CalendarPage, FormRow
});
