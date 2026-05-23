// Phase 5.4 — Agent detail page (full-screen replacement of the center frame)

const StatCard = ({ icon, label, value, sub }) => (
  <div className="flex items-center gap-3 rounded-lg border bg-card p-3.5">
    <div className="grid h-9 w-9 place-items-center rounded-md bg-muted/40 text-muted-foreground">
      <Icon name={icon} className="h-4 w-4"/>
    </div>
    <div className="min-w-0">
      <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-[15px] font-semibold tracking-tight truncate">{value}</div>
      {sub && <div className="font-mono text-[10.5px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  </div>
);

const LoadBar = ({ load }) => {
  const pct = Math.round(load * 100);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">当前负载</span>
        <span className="font-mono text-[11.5px] tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full transition-all",
          pct > 80 ? "bg-rose-500" : pct > 50 ? "bg-amber-500" : "bg-emerald-500"
        )} style={{ width: `${pct}%` }}/>
      </div>
    </div>
  );
};

/* ── Overview ────────────────────────────────────────────────── */
const AgentOverview = ({ agent, profile, onSwitchTab }) => {
  const groups = profile.groups.map(gid => DATA_EXTRA.groups.find(g => g.id === gid)).filter(Boolean);
  return (
    <div className="px-7 py-6 space-y-6 max-w-[820px]">
      {/* Hero */}
      <section className="flex items-start gap-5 rounded-2xl border bg-card p-5">
        <div className="relative">
          <Avatar initial={agent.name[0]} color={agent.color} size={80}/>
          <span className={cn("absolute -bottom-1 -right-1 h-4 w-4 rounded-full border-2 border-background",
            agent.online ? "bg-emerald-500" : "bg-zinc-400")}/>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <h2 className="text-2xl font-semibold tracking-tight">{agent.name}</h2>
            <Badge variant="brand">AI</Badge>
            <Badge variant={agent.online ? "success" : "outline"}>{agent.online ? "在线" : "离线"}</Badge>
          </div>
          <p className="text-[13px] text-muted-foreground border-l-2 border-brand pl-3 leading-relaxed" style={{ textWrap: "pretty" }}>
            {profile.bio}
          </p>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <StatCard icon="cpu" label="模型" value={profile.config.model} sub={profile.config.provider}/>
            <StatCard icon="zap" label="并发" value={`${profile.config.concurrency} 路`} sub={`temp ${profile.config.temperature}`}/>
            <StatCard icon="brain" label="技能数" value={agent.skillCount || profile.capabilities.length} sub={profile.capabilities.slice(0,2).join(" · ")}/>
          </div>
        </div>
      </section>

      {/* Load + groups */}
      <section className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border bg-card p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Icon name="activity" className="h-3.5 w-3.5 text-muted-foreground"/>
            <h3 className="text-[15px] font-semibold tracking-tight">负载与状态</h3>
          </div>
          <LoadBar load={profile.load}/>
          <div className="grid grid-cols-3 gap-2 pt-2">
            <div>
              <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">本周任务</div>
              <div className="text-[18px] font-semibold tabular-nums tracking-tight mt-0.5">12</div>
            </div>
            <div>
              <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">完成</div>
              <div className="text-[18px] font-semibold tabular-nums tracking-tight text-emerald-700 dark:text-emerald-400 mt-0.5">8</div>
            </div>
            <div>
              <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">阻塞</div>
              <div className="text-[18px] font-semibold tabular-nums tracking-tight text-rose-700 dark:text-rose-400 mt-0.5">1</div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border bg-card p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Icon name="hash" className="h-3.5 w-3.5 text-muted-foreground"/>
            <h3 className="text-[15px] font-semibold tracking-tight">所属频道</h3>
          </div>
          <div className="space-y-1.5">
            {groups.map(g => (
              <button key={g.id} className="flex items-center gap-2 w-full rounded-md px-2 py-1.5 hover:bg-accent transition-colors">
                <span className="text-muted-foreground/70 font-mono">#</span>
                <span className="text-[13px] flex-1 text-left">{g.name}</span>
                <span className="font-mono text-[10.5px] text-muted-foreground">{g.members.length} 人</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border bg-card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon name="sparkles" className="h-3.5 w-3.5 text-muted-foreground"/>
            <h3 className="text-[15px] font-semibold tracking-tight">能力</h3>
          </div>
          <button onClick={() => onSwitchTab("capabilities")} className="font-mono text-[11px] text-muted-foreground hover:text-foreground">
            管理 →
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {profile.capabilities.map(c => (
            <span key={c} className="inline-flex items-center gap-1 rounded-md border bg-muted/30 px-2 py-0.5 text-[12px]">
              {c}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
};

/* ── Capabilities ─────────────────────────────────────────────── */
const AgentCapabilities = ({ profile, agent }) => {
  const [caps, setCaps] = React.useState(profile.capabilities);
  const [val, setVal] = React.useState("");
  const add = () => { if (!val.trim()) return; setCaps(c => [...c, val.trim()]); setVal(""); };
  return (
    <div className="px-7 py-6 space-y-5 max-w-[820px]">
      <div className="rounded-2xl border bg-card p-5 space-y-4">
        <div>
          <h3 className="text-[15px] font-semibold tracking-tight">{agent.name} 当前可以做</h3>
          <p className="text-[12.5px] text-muted-foreground mt-0.5">能力标签控制协调者在路由时把任务派给谁。</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {caps.map((c, i) => (
            <span key={c} className="group inline-flex items-center gap-1.5 rounded-md border bg-muted/40 pl-2.5 pr-1 py-1 text-[12.5px]">
              {c}
              <button onClick={() => setCaps(caps.filter(x => x !== c))}
                className="grid h-4 w-4 place-items-center rounded text-muted-foreground hover:bg-background hover:text-foreground">
                <Icon name="x" className="h-2.5 w-2.5"/>
              </button>
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Input placeholder="加一个能力，比如 Headline tests" value={val}
            onChange={e => setVal(e.target.value)}
            onKeyDown={e => e.key === "Enter" && add()}/>
          <Button variant="outline" size="sm" onClick={add}>添加</Button>
        </div>
      </div>

      <div className="rounded-2xl border bg-card p-5 space-y-3">
        <h3 className="text-[15px] font-semibold tracking-tight">推荐技能包</h3>
        <p className="text-[12.5px] text-muted-foreground -mt-1">从技能仓库一键挂载，附带预置 prompt 和工具调用模板。</p>
        <div className="grid grid-cols-2 gap-2">
          {DATA_EXTRA.skillCatalog.map(s => (
            <button key={s.id} className="flex items-start gap-2.5 rounded-lg border bg-background p-3 text-left transition-colors hover:bg-accent">
              <div className="grid h-7 w-7 place-items-center rounded-md bg-brand/10 text-brand flex-shrink-0">
                <Icon name="sparkle" className="h-3.5 w-3.5"/>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[12.5px] font-medium">{s.name}</div>
                <div className="text-[11.5px] text-muted-foreground mt-0.5">{s.desc}</div>
              </div>
              <Icon name="plus" className="h-3.5 w-3.5 text-muted-foreground mt-1"/>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ── Memory ───────────────────────────────────────────────────── */
const AgentMemory = ({ profile }) => (
  <div className="px-7 py-6 space-y-4 max-w-[820px]">
    <div className="rounded-2xl border bg-card overflow-hidden">
      <header className="flex items-center justify-between border-b px-4 py-3 bg-muted/30">
        <div className="flex items-center gap-2">
          <Icon name="layers" className="h-3.5 w-3.5 text-muted-foreground"/>
          <h3 className="text-[15px] font-semibold tracking-tight">分层记忆</h3>
        </div>
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">L1 → L4</span>
      </header>
      {profile.memoryByLevel.map((m, i) => (
        <div key={m.level} className={cn("flex items-center gap-3 px-4 py-3", i > 0 && "border-t")}>
          <span className="grid h-9 w-9 place-items-center rounded-md bg-muted/40 font-mono text-[12px] font-medium text-muted-foreground flex-shrink-0">
            {m.level}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-[13.5px] font-medium">{m.name}</div>
            {m.hint && <div className="text-[11.5px] text-muted-foreground truncate">{m.hint}</div>}
          </div>
          <div className="text-right">
            <div className="font-mono text-[18px] font-semibold tabular-nums">{m.count}</div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">条</div>
          </div>
          <Button variant="ghost" size="sm">查看</Button>
        </div>
      ))}
    </div>

    <div className="rounded-2xl border bg-card p-5">
      <h3 className="text-[15px] font-semibold tracking-tight mb-3">最近写入</h3>
      <div className="space-y-2">
        {DATA.memory.map(m => (
          <div key={m.id} className="flex items-start gap-3 rounded-lg border bg-background p-3">
            <Badge variant={m.status === "accepted" ? "success" : m.status === "pending" ? "brand" : "outline"}>
              {m.status === "accepted" ? "已接受" : m.status === "pending" ? "待确认" : "已归档"}
            </Badge>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-medium">{m.title}</div>
              <div className="text-[12px] text-muted-foreground mt-0.5">{m.body}</div>
            </div>
            <span className="font-mono text-[10.5px] text-muted-foreground whitespace-nowrap">{m.when}</span>
          </div>
        ))}
      </div>
    </div>
  </div>
);

/* ── Tasks (filtered to this agent) ───────────────────────────── */
const AgentTasksList = ({ agent }) => {
  const tasks = DATA.tasks.filter(t => t.assignee === agent.id);
  return (
    <div className="px-7 py-6 max-w-[820px]">
      <div className="rounded-2xl border bg-card overflow-hidden">
        <header className="flex items-center justify-between border-b bg-muted/30 px-4 py-3">
          <h3 className="text-[15px] font-semibold tracking-tight">指派给 {agent.name} 的任务</h3>
          <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">{tasks.length}</span>
        </header>
        {tasks.length === 0 ? (
          <div className="px-4 py-12 text-center text-[12.5px] text-muted-foreground">暂无任务</div>
        ) : tasks.map((t, i) => (
          <div key={t.id} className={cn("flex items-center gap-3 px-4 py-3", i > 0 && "border-t")}>
            <TaskCheck state={t.state === "done" ? "done" : t.state === "doing" ? "doing" : null}/>
            <span className="font-mono text-[10.5px] text-muted-foreground w-10">{t.id}</span>
            <span className={cn("flex-1 text-[13px]", t.state === "done" && "line-through text-muted-foreground")}>{t.title}</span>
            <Badge variant={t.state === "done" ? "success" : t.state === "doing" ? "brand" : t.state === "blocked" ? "warning" : "outline"}>
              {t.state === "done" ? "完成" : t.state === "doing" ? "进行中" : t.state === "blocked" ? "阻塞" : "待办"}
            </Badge>
            <span className="font-mono text-[11px] text-muted-foreground w-12 text-right">{t.due}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── Activity ─────────────────────────────────────────────────── */
const AgentActivity = ({ agent }) => (
  <div className="px-7 py-6 max-w-[820px]">
    <ActivityView events={DATA.activity} user={DATA.user}/>
  </div>
);

/* ── Settings ─────────────────────────────────────────────────── */
const AgentDetailSettings = ({ agent, profile }) => {
  const [showKey, setShowKey] = React.useState(false);
  const provider = DATA_EXTRA.providers.find(p => p.id === profile.config.provider);
  return (
    <div className="px-7 py-6 space-y-5 max-w-[760px]">
      <FormRow title="模型" desc="切换底层模型会让对话状态从此刻起在新模型上继续。">
        <div className="grid grid-cols-2 gap-2">
          <select className="h-9 rounded-md border bg-background px-3 text-[13px]" defaultValue={profile.config.provider}>
            {DATA_EXTRA.providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <select className="h-9 rounded-md border bg-background px-3 text-[13px] font-mono" defaultValue={profile.config.model}>
            {provider?.models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      </FormRow>

      <FormRow title="API Key" desc="密钥仅你可见，存储时加密。">
        <div className="flex items-center gap-2 rounded-md border bg-muted/20 pl-3 pr-1">
          <Icon name="key" className="h-3.5 w-3.5 text-muted-foreground"/>
          <input type={showKey ? "text" : "password"} defaultValue="sk-ant-•••••••••••••43d5"
            className="flex-1 h-9 bg-transparent text-[13px] font-mono outline-none"/>
          <Button variant="ghost" size="iconSm" onClick={() => setShowKey(v => !v)}>
            <Icon name={showKey ? "eyeOff" : "eye"} className="h-3.5 w-3.5"/>
          </Button>
        </div>
      </FormRow>

      <FormRow title="System Prompt" desc="助手的人格、风格与边界。">
        <Textarea rows={5} defaultValue={profile.bio}/>
      </FormRow>

      <FormRow title="最大输出 token">
        <Input type="number" defaultValue={profile.config.maxTokens}/>
      </FormRow>

      <FormRow title="并发任务数" desc="同一时刻这个助手最多并行处理几条任务。">
        <Input type="number" defaultValue={profile.config.concurrency}/>
      </FormRow>

      <FormRow title="Temperature" desc="数值越低越严谨，越高越发散。">
        <Input type="number" step="0.1" min="0" max="2" defaultValue={profile.config.temperature}/>
      </FormRow>

      <section className="space-y-3">
        <header>
          <h3 className="text-[15px] font-semibold tracking-tight text-destructive">危险区域</h3>
        </header>
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 flex items-center gap-3">
          <Icon name="trash" className="h-4 w-4 text-destructive flex-shrink-0"/>
          <p className="text-[13px] leading-relaxed text-muted-foreground flex-1">
            把 {agent.name} 从所有频道移除，保留历史消息。无法撤销。
          </p>
          <Button variant="destructive" size="sm">删除</Button>
        </div>
      </section>
    </div>
  );
};

/* ── Top-level detail page ───────────────────────────────────── */
const AGENT_DETAIL_TABS = [
  { id: "overview",     icon: "user",       label: "概览" },
  { id: "capabilities", icon: "sparkles",   label: "能力" },
  { id: "memory",       icon: "brain",      label: "记忆" },
  { id: "tasks",        icon: "listChecks", label: "任务" },
  { id: "activity",     icon: "activity",   label: "活动" },
  { id: "settings",     icon: "settings",   label: "设置" },
];

const AgentDetailPage = ({ agentId, onBack }) => {
  const agent = DATA.agents.find(a => a.id === agentId);
  const profile = DATA_EXTRA.agentProfiles[agentId];
  const [tab, setTab] = React.useState("overview");

  if (!agent || !profile) {
    return (
      <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
        <EmptyState icon="user" title="找不到这个助手" desc="可能已被删除。"/>
      </main>
    );
  }

  return (
    <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
      <header className="flex items-center gap-3 border-b border-border/70 px-5 py-3.5">
        <Button variant="ghost" size="iconSm" onClick={onBack} title="返回">
          <Icon name="chevronLeft" className="h-4 w-4"/>
        </Button>
        <Avatar initial={agent.name[0]} color={agent.color} size={32} online={agent.online}/>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="heading-serif text-[20px] font-medium tracking-tight">{agent.name}</h1>
            <Badge variant="brand">AI</Badge>
          </div>
          <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-0.5">
            助手详情 · {agent.role}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={onBack}>
          <Icon name="chat" className="h-3 w-3"/> 进入对话
        </Button>
      </header>

      <nav className="border-b border-border/70 glass-soft px-3 py-1.5 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
        <div className="flex gap-0.5">
          {AGENT_DETAIL_TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              data-active={tab === t.id ? "true" : undefined}
              className={cn(
                "relative inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[12.5px] font-medium",
                "text-muted-foreground hover:bg-accent/60 hover:text-foreground transition-colors",
                "data-[active=true]:glass-strong data-[active=true]:text-foreground data-[active=true]:shadow-sm"
              )}>
              <Icon name={t.icon} className="h-3.5 w-3.5"/>
              <span>{t.label}</span>
              <span className={cn("absolute -bottom-[7px] left-3 right-3 h-0.5 rounded-full bg-brand transition-transform origin-center",
                tab === t.id ? "scale-x-100" : "scale-x-0")}/>
            </button>
          ))}
        </div>
      </nav>

      <div className="flex-1 min-h-0 overflow-y-auto animate-fade-in" key={tab}>
        {tab === "overview"     && <AgentOverview agent={agent} profile={profile} onSwitchTab={setTab}/>}
        {tab === "capabilities" && <AgentCapabilities agent={agent} profile={profile}/>}
        {tab === "memory"       && <AgentMemory profile={profile}/>}
        {tab === "tasks"        && <AgentTasksList agent={agent}/>}
        {tab === "activity"     && <AgentActivity agent={agent}/>}
        {tab === "settings"     && <AgentDetailSettings agent={agent} profile={profile}/>}
      </div>
    </main>
  );
};

window.AgentDetailPage = AgentDetailPage;
