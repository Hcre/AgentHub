// Phase 4 — Groups + Coordinator
// GroupChatView: replaces the center frame entirely when section==="group"

const AGENT_LOOKUP = () => {
  const m = {};
  DATA.agents.forEach((a) => {m[a.id] = a;});
  m[DATA_EXTRA.coordinator.id] = DATA_EXTRA.coordinator;
  m.user = { id: "user", name: DATA.user.handle, color: "neutral", initial: DATA.user.initial, role: "you" };
  return m;
};

/* Coordinator's structured subtask card. */
const CoordinatorPlan = ({ plan, agents }) =>
<div className="mt-2 rounded-xl border bg-card overflow-hidden">
    <header className="flex items-center gap-2 border-b border-border/70 bg-brand/5 px-4 py-2.5">
      <Icon name="network" className="h-3.5 w-3.5 text-brand" />
      <span className="font-mono text-[10.5px] uppercase tracking-wider text-brand">分发方案 · {plan.steps.length} 步</span>
      <div className="flex-1" />
      <Badge variant="brand">协调者</Badge>
    </header>
    <div className="px-4 py-3">
      <p className="text-[13.5px] leading-relaxed text-foreground/90" style={{ textWrap: "pretty" }}>
        {plan.summary}
      </p>
    </div>
    <ol className="divide-y border-t">
      {plan.steps.map((s, i) => {
      const a = agents[s.who];
      const depLabels = s.depends.length ? `依赖 ${s.depends.join(", ")}` : "可立即开始";
      return (
        <li key={s.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/30 transition-colors">
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground w-7">{s.id}</span>
            <div className="flex items-center gap-2 w-[120px] flex-shrink-0">
              {a && <Avatar initial={a.name[0]} color={a.color} size={20} />}
              <span className="text-[12.5px] font-medium truncate">{a?.name}</span>
            </div>
            <span className="flex-1 text-[13px] truncate">{s.label}</span>
            <span className="font-mono text-[10.5px] text-muted-foreground hidden md:inline-flex items-center gap-1">
              <Icon name="clock" className="h-3 w-3" />~{s.eta} min
            </span>
            <span className="font-mono text-[10.5px] text-muted-foreground hidden lg:inline">{depLabels}</span>
          </li>);

    })}
    </ol>
    {plan.watchouts?.length > 0 &&
  <div className="border-t bg-amber-50/40 dark:bg-amber-950/20 px-4 py-2.5">
        <div className="flex items-start gap-2">
          <Icon name="info" className="h-3.5 w-3.5 text-amber-700 dark:text-amber-400 mt-0.5" />
          <div className="space-y-0.5">
            {plan.watchouts.map((w, i) =>
        <div key={i} className="text-[12.5px] text-amber-800 dark:text-amber-300">{w}</div>
        )}
          </div>
        </div>
      </div>
  }
    <footer className="flex items-center justify-between border-t px-4 py-2 bg-muted/20">
      <span className="font-mono text-[11px] text-muted-foreground">每个子任务会作为独立任务进入「任务」标签</span>
      <div className="flex gap-1.5">
        <Button variant="ghost" size="sm">改一下</Button>
        <Button variant="brand" size="sm">
          <Icon name="zap" className="h-3 w-3" />派发
        </Button>
      </div>
    </footer>
  </div>;


/* Parse @mentions and render them as inline tags. */
const renderRichText = (text) => {
  const parts = text.split(/(@\S+)/g);
  return parts.map((p, i) => {
    if (p.startsWith("@")) {
      return (
        <span key={i} className="inline-flex items-center rounded bg-brand/10 px-1.5 py-0.5 font-medium text-brand">
          {p}
        </span>);

    }
    return <React.Fragment key={i}>{p}</React.Fragment>;
  });
};

const GroupMessage = ({ msg, agents }) => {
  const who = agents[msg.who] || { name: msg.who, color: "neutral", initial: "?" };
  const isUser = msg.from === "user";
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="pt-0.5">
        <Avatar initial={who.initial || who.name[0]} color={who.color} size={32} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[13px] font-semibold">{who.name}</span>
          {!isUser && msg.who === "coordinator" && <Badge variant="brand">协调者</Badge>}
          {!isUser && msg.who !== "coordinator" && <Badge variant="brand">AI</Badge>}
          {msg.requiresApproval && (
            <Badge variant="warning" className="gap-1">
              <Icon name="shieldCheck" className="h-2.5 w-2.5"/>
              待批准
            </Badge>
          )}
          <span className="font-mono text-[11px] text-muted-foreground">{msg.time}</span>
        </div>
        {msg.text &&
        <div className="ai-prose text-[14px] leading-[1.6] text-foreground" style={{ textWrap: "pretty" }}>
            {msg.text.split("\n\n").map((p, i) => <p key={i}>{renderRichText(p)}</p>)}
          </div>
        }
        {msg.requiresApproval && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30 px-3 py-2">
            <Icon name="shieldCheck" className="h-3.5 w-3.5 text-amber-700 dark:text-amber-400"/>
            <span className="text-[12px] text-amber-900 dark:text-amber-200">
              已进入「收件箱 · 审批」。助手收到批准后才会执行。
            </span>
            <button className="ml-auto font-mono text-[10.5px] text-amber-900 dark:text-amber-200 underline hover:no-underline">
              去审批 →
            </button>
          </div>
        )}
        {msg.kind === "plan" && <CoordinatorPlan plan={msg.plan} agents={agents} />}
      </div>
    </div>);

};

const GroupMembersStrip = ({ memberIds, agents, onPick }) =>
<div className="flex items-center gap-2">
    <div className="flex -space-x-1.5">
      {memberIds.map((id) => {
      const a = agents[id];
      if (!a) return null;
      return (
        <button key={id} onClick={() => onPick(id)}
        title={a.name}
        className="rounded-full ring-2 ring-background hover:translate-y-[-2px] transition-transform">
            <Avatar initial={a.name[0]} color={a.color} size={26} online={a.online} />
          </button>);

    })}
    </div>
    <span className="font-mono text-[10.5px] text-muted-foreground ml-1">{memberIds.length} 个成员</span>
  </div>;


const GroupComposer = ({ group, onSend, agents }) => {
  const [val, setVal] = React.useState("");
  const [showMentions, setShowMentions] = React.useState(false);
  const [requiresApproval, setRequiresApproval] = React.useState(false);
  const inputRef = React.useRef(null);

  const send = () => {if (!val.trim()) return;onSend(val.trim(), { requiresApproval });setVal("");setShowMentions(false);setRequiresApproval(false);};

  const mentionables = [
  { id: "coordinator", name: "协调者", hint: "拆分并分发任务" },
  ...group.members.map((id) => ({ id, name: agents[id]?.name, hint: agents[id]?.role }))];


  const insertMention = (mid) => {
    setVal((v) => `@${agents[mid]?.name || mid} ${v.replace(/@\S*$/, "")}`.trimStart());
    setShowMentions(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  return (
    <div className="relative mx-4 mb-4 rounded-xl border bg-background shadow-sm transition-all focus-within:ring-2 focus-within:ring-ring">
      {requiresApproval && (
        <div className="flex items-center gap-2 rounded-t-xl border-b bg-brand-soft/60 px-3 py-1.5">
          <Icon name="shieldCheck" className="h-3 w-3 text-brand-deep"/>
          <span className="text-[11.5px] text-brand-deep">发送后该消息会进入「收件箱 · 审批」，得到你手动批准后助手才会执行。</span>
          <button onClick={() => setRequiresApproval(false)}
            className="ml-auto font-mono text-[10.5px] text-brand-deep hover:opacity-70">取消</button>
        </div>
      )}
      {showMentions &&
      <div className="absolute left-2 bottom-full mb-1.5 w-[280px] rounded-lg border bg-popover p-1 shadow-lg z-20">
          <div className="px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">提及</div>
          {mentionables.map((m) =>
        <button key={m.id} onClick={() => insertMention(m.id)}
        className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-accent">
              <Avatar initial={agents[m.id]?.name[0] || "?"} color={agents[m.id]?.color || "brand"} size={22} />
              <div className="min-w-0">
                <div className="text-[13px] font-medium truncate">{m.name}</div>
                <div className="font-mono text-[10.5px] text-muted-foreground truncate">{m.hint}</div>
              </div>
            </button>
        )}
        </div>
      }
      <textarea
        ref={inputRef}
        rows={1}
        placeholder={`在 #${group.name} 给团队留言，输入 @ 提及…`}
        value={val}
        onChange={(e) => {
          setVal(e.target.value);
          setShowMentions(/(^|\s)@\S*$/.test(e.target.value));
        }}
        onKeyDown={(e) => {if (e.key === "Enter" && !e.shiftKey) {e.preventDefault();send();}}}
        className="w-full resize-none rounded-t-xl border-0 bg-transparent px-3 py-3 text-[14px] outline-none placeholder:text-muted-foreground"
        style={{ maxHeight: 200 }} />
      
      <div className="flex items-center justify-between px-2 py-2">
        <div className="flex gap-0.5">
          <Button variant="ghost" size="iconSm" className="text-muted-foreground h-7 w-7">
            <Icon name="paperclip" className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm" onClick={() => setShowMentions((v) => !v)}
          className={cn("text-muted-foreground h-7 w-7", showMentions && "bg-accent text-foreground")}>
            <Icon name="atSign" className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground h-7 w-7">
            <Icon name="smile" className="h-3.5 w-3.5" />
          </Button>
          <div className="mx-1 h-4 w-px self-center bg-border"/>
          <Button variant="ghost" size="iconSm" onClick={() => setRequiresApproval(v => !v)}
            title={requiresApproval ? "下一条消息将需要批准" : "标记为需批准才可执行"}
            className={cn("h-7 px-2 gap-1.5 text-[11px] font-medium",
              requiresApproval
                ? "bg-brand-soft text-brand-deep hover:bg-brand-soft/80"
                : "text-muted-foreground hover:text-foreground")}>
            <Icon name="shieldCheck" className="h-3.5 w-3.5" />
            {requiresApproval ? "需批准" : "权限认可"}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-muted-foreground">↵ 发送</span>
          <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
            <Icon name="send" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>);

};

const CHANNEL_TABS = [
  { id: "chat",  icon: "chat",      label: "聊天" },
  { id: "files", icon: "files",     label: "文件" },
  { id: "tasks", icon: "listCheck", label: "任务" },
];

const ChannelFiles = ({ group }) => {
  const files = [
    { id: "cf1", name: `${group.name}-brief.mdx`, kind: "doc",  size: "4.1 KB" },
    { id: "cf2", name: `${group.name}-tokens.json`, kind: "doc",  size: "1.2 KB" },
  ];
  return (
    <div className="px-5 py-4">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
        {files.map(f => (
          <div key={f.id} className="rounded-xl border bg-card p-4 space-y-2 transition-all hover:-translate-y-px hover:shadow-sm">
            <div className="grid h-10 w-10 place-items-center rounded-md border bg-muted/30">
              <Icon name="doc" className="h-4 w-4 text-muted-foreground"/>
            </div>
            <div className="font-mono text-[13px] truncate">{f.name}</div>
            <div className="font-mono text-[11px] text-muted-foreground">Document · {f.size}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const ChannelTasks = ({ group, agents }) => {
  const subset = (DATA.tasks || []).filter(t => group.members.includes(t.assignee));
  return (
    <div className="px-5 py-4">
      <div className="rounded-xl border bg-card overflow-hidden">
        {subset.length === 0 ? (
          <div className="px-4 py-10 text-center text-[12.5px] text-muted-foreground">该频道还没有任务</div>
        ) : subset.map((t, i) => {
          const a = agents[t.assignee];
          return (
            <div key={t.id} className={cn("flex items-center gap-3 px-4 py-2.5", i > 0 && "border-t")}>
              <TaskCheck state={t.state === "done" ? "done" : t.state === "doing" ? "doing" : null}/>
              <span className="font-mono text-[10.5px] text-muted-foreground w-10">{t.id}</span>
              <span className="flex-1 text-[13px]">{t.title}</span>
              {a && <Avatar initial={a.name[0]} color={a.color} size={20}/>}
              <span className="font-mono text-[10.5px] text-muted-foreground w-12 text-right">{t.due}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const GroupChatView = ({ groupId, state, setState, onSend, onPickAgent, tweaks, setTweak }) => {
  const group = DATA_EXTRA.groups.find((g) => g.id === groupId);
  const agents = AGENT_LOOKUP();
  const msgs = state.groupMessages && state.groupMessages[groupId] || DATA_EXTRA.groupMessages[groupId] || [];
  const scrollRef = React.useRef(null);
  const [channelTab, setChannelTab] = React.useState("chat");

  React.useEffect(() => {
    if (scrollRef.current && channelTab === "chat") scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [msgs.length, channelTab]);

  if (!group) {
    return (
      <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
        <EmptyState icon="channels" title="选个频道" desc="左侧「频道」里挑一个团队对话。" />
      </main>);

  }

  return (
    <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        <div className="flex items-center gap-3 min-w-0">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand/10 text-brand flex-shrink-0">
            <Icon name="hash" className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h1 className="heading-serif text-[20px] font-medium tracking-tight truncate">{group.name}</h1>
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-0.5 truncate">
              群聊 · {group.description}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <GroupMembersStrip memberIds={group.members} agents={agents} onPick={onPickAgent} />
          <div className="h-5 w-px bg-border" />
          <Button variant="ghost" size="iconSm" title="置顶任务"><Icon name="pin" className="h-3.5 w-3.5" /></Button>
          {tweaks && setTweak && (
            <Button variant="ghost" size="iconSm"
              onClick={() => setTweak("theme", tweaks.theme === "dark" ? "light" : "dark")}
              title={tweaks.theme === "dark" ? "切换为浅色" : "切换为深色"}>
              <Icon name={tweaks.theme === "dark" ? "sun" : "moon"} className="h-3.5 w-3.5"/>
            </Button>
          )}
          <Button variant="ghost" size="iconSm" title="频道设置"><Icon name="settings" className="h-3.5 w-3.5" /></Button>
        </div>
      </header>

      {/* Channel tabs — replaces the pinned-task bar */}
      <nav className="border-b border-border/70 glass-soft px-3 py-1.5">
        <div className="flex gap-0.5">
          {CHANNEL_TABS.map((t) =>
            <button key={t.id} onClick={() => setChannelTab(t.id)}
              data-active={channelTab === t.id ? "true" : undefined}
              className={cn(
                "relative inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[12.5px] font-medium",
                "text-muted-foreground hover:bg-accent/60 hover:text-foreground transition-colors",
                "data-[active=true]:glass-strong data-[active=true]:text-foreground data-[active=true]:shadow-sm"
              )}>
              <Icon name={t.icon} className="h-3.5 w-3.5" />
              <span>{t.label}</span>
              <span className={cn("absolute -bottom-[7px] left-3 right-3 h-0.5 rounded-full bg-brand transition-transform origin-center",
                channelTab === t.id ? "scale-x-100" : "scale-x-0")} />
            </button>
          )}
        </div>
      </nav>

      {channelTab === "chat" && (
        <>
          {group.pinnedTask && (
            <div className="flex items-center gap-2 border-b border-border/60 bg-brand-soft/30 px-5 py-1.5">
              <Icon name="pin" className="h-2.5 w-2.5 text-brand-deep"/>
              <span className="text-[12px] text-brand-deep">{group.pinnedTask}</span>
              <div className="flex-1"/>
              <button className="font-mono text-[10.5px] text-muted-foreground hover:text-foreground">打开 →</button>
            </div>
          )}
          <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-5 space-y-5">
            {msgs.map((m) => <GroupMessage key={m.id} msg={m} agents={agents} />)}
          </div>
          <GroupComposer group={group} agents={agents} onSend={onSend} />
        </>
      )}

      {channelTab === "files" && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <ChannelFiles group={group}/>
        </div>
      )}

      {channelTab === "tasks" && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <ChannelTasks group={group} agents={agents}/>
        </div>
      )}
    </main>);

};

window.GroupChatView = GroupChatView;