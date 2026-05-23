// Phase 5.3 — Inbox view: approval / task / system

const InboxRow = ({ item, active, onClick }) => {
  const typeIcon = item.type === "approval" ? "shieldCheck" : item.type === "task" ? "listCheck" : "info";
  const typeLabel = item.type === "approval" ? "审批" : item.type === "task" ? "任务" : "系统";
  return (
    <button onClick={onClick}
      data-active={active ? "true" : undefined}
      className={cn(
        "group flex w-full items-start gap-3 border-b border-border/60 px-4 py-3 text-left",
        "transition-colors hover:bg-muted/40",
        "data-[active=true]:bg-brand-soft/40 data-[active=true]:border-l-2 data-[active=true]:border-l-brand"
      )}>
      {item.unread && (
        <span className="mt-1.5 h-2 w-2 rounded-full bg-brand flex-shrink-0"/>
      )}
      {!item.unread && <span className="mt-1.5 h-2 w-2 flex-shrink-0"/>}
      <div className="grid h-9 w-9 place-items-center rounded-lg border bg-muted/40 text-muted-foreground flex-shrink-0">
        <Icon name={typeIcon} className="h-4 w-4"/>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant={item.type === "approval" ? "brand" : item.type === "task" ? "outline" : "secondary"}>
            {typeLabel}
          </Badge>
          {item.actorName && (
            <span className="font-mono text-[10.5px] text-muted-foreground">{item.actorName}</span>
          )}
          <span className="flex-1"/>
          <span className="font-mono text-[10.5px] text-muted-foreground">{item.when}</span>
        </div>
        <div className={cn("text-[13.5px] mb-1 truncate", item.unread ? "font-semibold" : "font-medium")}>
          {item.title}
        </div>
        <div className="text-[12.5px] text-muted-foreground line-clamp-2 leading-snug">
          {item.summary}
        </div>
      </div>
    </button>
  );
};

const DiffPreview = ({ diff }) => (
  <div className="rounded-lg border bg-card overflow-hidden font-mono text-[12px] leading-relaxed">
    <header className="flex items-center gap-2 border-b bg-muted/40 px-3 py-1.5">
      <Icon name="diff" className="h-3 w-3 text-muted-foreground"/>
      <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">改动预览</span>
      <span className="flex-1"/>
      <span className="font-mono text-[10.5px] text-emerald-700 dark:text-emerald-400">
        +{diff.filter(d => d.kind === "add").length}
      </span>
      <span className="font-mono text-[10.5px] text-rose-700 dark:text-rose-400">
        −{diff.filter(d => d.kind === "del").length}
      </span>
    </header>
    <div className="divide-y divide-border/60">
      {diff.map((d, i) => (
        <div key={i} className={cn(
          "flex gap-2 px-3 py-1",
          d.kind === "add" && "bg-emerald-50/60 dark:bg-emerald-950/30 text-emerald-900 dark:text-emerald-200",
          d.kind === "del" && "bg-rose-50/60 dark:bg-rose-950/30 text-rose-900 dark:text-rose-200",
          d.kind === "neutral" && "text-muted-foreground"
        )}>
          <span className="select-none w-3 text-right opacity-50">
            {d.kind === "add" ? "+" : d.kind === "del" ? "−" : " "}
          </span>
          <span className="whitespace-pre-wrap break-words flex-1">{d.text}</span>
        </div>
      ))}
    </div>
  </div>
);

const InboxDetail = ({ item, onApprove, onReject, onArchive }) => {
  if (!item) {
    return <EmptyState icon="inbox" title="选一条消息" desc="左边挑一条，看详情、批准或归档。"/>;
  }
  const agents = AGENT_LOOKUP();
  const actor = item.actor ? agents[item.actor] : null;
  return (
    <div className="flex flex-col h-full">
      <header className="flex items-start justify-between gap-3 border-b px-7 py-5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-2">
            <Badge variant={item.type === "approval" ? "brand" : item.type === "task" ? "outline" : "secondary"}>
              {item.type === "approval" ? "审批" : item.type === "task" ? "任务" : "系统"}
            </Badge>
            <span className="font-mono text-[11px] text-muted-foreground">{item.when}</span>
          </div>
          <h2 className="text-xl font-semibold tracking-tight">{item.title}</h2>
          {actor && (
            <div className="flex items-center gap-2 mt-3">
              <Avatar initial={actor.name[0]} color={actor.color} size={22}/>
              <span className="text-[13px]">{actor.name}</span>
              <span className="font-mono text-[11px] text-muted-foreground">· {actor.role}</span>
            </div>
          )}
        </div>
        <Button variant="ghost" size="iconSm" onClick={() => onArchive(item.id)} title="归档">
          <Icon name="x" className="h-3.5 w-3.5"/>
        </Button>
      </header>

      <div className="flex-1 overflow-y-auto px-7 py-5 space-y-5">
        <p className="text-[14px] leading-relaxed" style={{ textWrap: "pretty" }}>
          {item.summary}
        </p>

        {item.impact && (
          <div className="flex items-center gap-2 rounded-lg border border-dashed bg-muted/30 px-3 py-2">
            <Icon name="layers" className="h-3.5 w-3.5 text-muted-foreground"/>
            <span className="font-mono text-[12px] text-muted-foreground">{item.impact}</span>
          </div>
        )}

        {item.diff && <DiffPreview diff={item.diff}/>}

        {item.type === "task" && (
          <div className="rounded-lg border bg-muted/20 p-3">
            <div className="flex items-center gap-2">
              <Icon name="arrowRight" className="h-3.5 w-3.5 text-muted-foreground"/>
              <span className="text-[13px] text-muted-foreground">在「任务」标签查看完整上下文</span>
              <span className="flex-1"/>
              <Button variant="outline" size="sm">打开任务</Button>
            </div>
          </div>
        )}
      </div>

      {item.type === "approval" && (
        <footer className="border-t bg-muted/20 px-7 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Icon name="info" className="h-3.5 w-3.5"/>
            <span className="font-mono text-[11px]">批准后改动会写入文件，可在历史里撤回。</span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onReject(item.id)}>
              <Icon name="x" className="h-3 w-3"/> 驳回
            </Button>
            <Button variant="brand" size="sm" onClick={() => onApprove(item.id)}>
              <Icon name="check" className="h-3 w-3"/> 批准
            </Button>
          </div>
        </footer>
      )}
    </div>
  );
};

const InboxView = () => {
  const [items, setItems] = React.useState(DATA_EXTRA.inbox);
  const [tab, setTab] = React.useState("all");
  const [sel, setSel] = React.useState(DATA_EXTRA.inbox[0]?.id);

  const filtered = items.filter(i => tab === "all" || i.type === tab);
  const item = items.find(i => i.id === sel);
  const unreadCount = items.filter(i => i.unread).length;

  const markRead = (id) => {
    setItems(list => list.map(i => i.id === id ? { ...i, unread: false } : i));
  };
  const archive = (id) => {
    setItems(list => list.filter(i => i.id !== id));
    setSel(s => s === id ? filtered[0]?.id : s);
  };
  const approve = (id) => {
    setItems(list => list.map(i => i.id === id ? { ...i, unread: false, approved: true, type: "system", summary: "已批准 · " + i.summary } : i));
  };

  return (
    <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        <div className="flex items-center gap-3">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="inbox" className="h-4 w-4"/>
          </div>
          <div>
            <h1 className="heading-serif text-[20px] font-medium tracking-tight">收件箱</h1>
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-0.5">
              {unreadCount} 未读 · {items.length} 总计
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="iconSm" title="刷新"><Icon name="refresh" className="h-3.5 w-3.5"/></Button>
          <Button variant="ghost" size="iconSm" title="筛选"><Icon name="sliders" className="h-3.5 w-3.5"/></Button>
        </div>
      </header>

      <div className="flex-1 min-h-0 grid" style={{ gridTemplateColumns: "380px 1fr" }}>
        <aside className="flex flex-col border-r min-h-0">
          <div className="border-b px-3 py-2">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="h-8 w-full">
                <TabsTrigger value="all"      className="flex-1 h-6 text-[12px]">全部</TabsTrigger>
                <TabsTrigger value="approval" className="flex-1 h-6 text-[12px]">审批</TabsTrigger>
                <TabsTrigger value="task"     className="flex-1 h-6 text-[12px]">任务</TabsTrigger>
                <TabsTrigger value="system"   className="flex-1 h-6 text-[12px]">系统</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="flex-1 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <div className="font-mono text-[11px] text-muted-foreground">没有 {tab === "all" ? "" : tab} 消息</div>
              </div>
            ) : filtered.map(it => (
              <InboxRow key={it.id} item={it}
                active={sel === it.id}
                onClick={() => { setSel(it.id); markRead(it.id); }}/>
            ))}
          </div>
        </aside>
        <div className="min-h-0 overflow-hidden">
          <InboxDetail item={item} onApprove={approve} onReject={archive} onArchive={archive}/>
        </div>
      </div>
    </main>
  );
};

window.InboxView = InboxView;
