// Phase 6 — Create Agent modal: Form-based + Conversational creation paths.

const AVATAR_COLORS = [
  { id: "brand",   name: "Coral" },
  { id: "sage",    name: "Sage" },
  { id: "clay",    name: "Clay" },
  { id: "rose",    name: "Rose" },
  { id: "blue",    name: "Blue" },
  { id: "neutral", name: "Neutral" },
];

/* ── Form path ────────────────────────────────────────────────── */

const FormPath = ({ onCancel, onCreate }) => {
  const [form, setForm] = React.useState({
    name: "",
    role: "",
    color: "brand",
    provider: "anthropic",
    model: "claude-sonnet-4-5",
    apiKey: "",
    systemPrompt: "",
    skills: [],
  });
  const [showKey, setShowKey] = React.useState(false);
  const set = (patch) => setForm(f => ({ ...f, ...patch }));
  const provider = DATA_EXTRA.providers.find(p => p.id === form.provider);

  const toggleSkill = (id) => set({
    skills: form.skills.includes(id) ? form.skills.filter(s => s !== id) : [...form.skills, id]
  });

  const valid = form.name.trim() && form.role.trim();

  return (
    <>
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Identity row */}
        <div className="grid grid-cols-[auto_1fr] gap-4 items-start">
          <div className="space-y-2">
            <Avatar initial={form.name[0] || "?"} color={form.color} size={64}/>
            <div className="flex flex-wrap gap-1 w-16 justify-center">
              {AVATAR_COLORS.map(c => (
                <button key={c.id} onClick={() => set({ color: c.id })}
                  title={c.name}
                  className={cn(
                    "h-4 w-4 rounded-full ring-offset-2 ring-offset-background transition-all",
                    c.id === "brand" && "bg-brand",
                    c.id === "sage" && "bg-emerald-400",
                    c.id === "clay" && "bg-amber-400",
                    c.id === "rose" && "bg-rose-400",
                    c.id === "blue" && "bg-blue-400",
                    c.id === "neutral" && "bg-zinc-400",
                    form.color === c.id && "ring-2 ring-foreground/40"
                  )}/>
              ))}
            </div>
          </div>
          <div className="space-y-3 flex-1 min-w-0">
            <FormRow title="名称" desc="助手在频道和提及里显示的名字。">
              <Input placeholder="比如 编辑、文案" value={form.name}
                onChange={e => set({ name: e.target.value })}/>
            </FormRow>
            <FormRow title="角色" desc="一句话说清这个助手负责什么。">
              <Input placeholder="比如 Content editor" value={form.role}
                onChange={e => set({ role: e.target.value })}/>
            </FormRow>
          </div>
        </div>

        <FormRow title="模型">
          <div className="grid grid-cols-2 gap-2">
            <select value={form.provider}
              onChange={e => set({ provider: e.target.value, model: DATA_EXTRA.providers.find(p => p.id === e.target.value).models[0] })}
              className="h-9 rounded-md border bg-background px-3 text-[13px]">
              {DATA_EXTRA.providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
            <select value={form.model}
              onChange={e => set({ model: e.target.value })}
              className="h-9 rounded-md border bg-background px-3 text-[13px] font-mono">
              {provider?.models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </FormRow>

        <FormRow title="API Key" desc="不会发到前端日志，存储时加密。">
          <div className="flex items-center gap-2 rounded-md border bg-muted/20 pl-3 pr-1">
            <Icon name="key" className="h-3.5 w-3.5 text-muted-foreground"/>
            <input type={showKey ? "text" : "password"}
              placeholder="sk-ant-..." value={form.apiKey}
              onChange={e => set({ apiKey: e.target.value })}
              className="flex-1 h-9 bg-transparent text-[13px] font-mono outline-none"/>
            <Button variant="ghost" size="iconSm" onClick={() => setShowKey(v => !v)}>
              <Icon name={showKey ? "eyeOff" : "eye"} className="h-3.5 w-3.5"/>
            </Button>
          </div>
        </FormRow>

        <FormRow title="System Prompt"
          desc="留空也行，可以之后在助手设置里写。"
          count={`${form.systemPrompt.length} / 4000`}>
          <Textarea rows={4} placeholder="你是一位…" value={form.systemPrompt}
            onChange={e => set({ systemPrompt: e.target.value })}/>
        </FormRow>

        <FormRow title="技能（可选）" desc="勾上以后协调者就能把对应类型的任务派给它。">
          <div className="grid grid-cols-2 gap-1.5">
            {DATA_EXTRA.skillCatalog.map(s => (
              <button key={s.id} onClick={() => toggleSkill(s.id)}
                data-on={form.skills.includes(s.id) ? "true" : undefined}
                className={cn(
                  "flex items-start gap-2 rounded-lg border bg-background p-2.5 text-left transition-all",
                  "hover:bg-accent",
                  "data-[on=true]:bg-brand/5 data-[on=true]:border-brand/40"
                )}>
                <span className={cn(
                  "mt-0.5 grid h-4 w-4 place-items-center rounded border flex-shrink-0",
                  form.skills.includes(s.id) ? "bg-brand border-brand text-brand-foreground" : "border-border"
                )}>
                  {form.skills.includes(s.id) && <Icon name="check" className="h-2.5 w-2.5"/>}
                </span>
                <div className="min-w-0">
                  <div className="font-mono text-[12px] font-medium">{s.name}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2 leading-snug">{s.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </FormRow>
      </div>

      <footer className="flex items-center justify-between gap-2 border-t bg-muted/20 px-5 py-3">
        <span className="font-mono text-[11px] text-muted-foreground">
          {valid ? "准备好了" : "名称 + 角色是必填项"}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>取消</Button>
          <Button variant="brand" disabled={!valid} onClick={() => onCreate(form)}>
            <Icon name="userPlus" className="h-3.5 w-3.5"/>创建助手
          </Button>
        </div>
      </footer>
    </>
  );
};

/* ── Conversational path ──────────────────────────────────────── */

const SCRIPTED_REPLY = (text) => {
  // Very lightweight "draft" generation from the user description.
  const name = text.match(/(?:叫|名字|name)[\s::]*([^\s,，。、]{1,8})/)?.[1]
            || text.match(/^([\u4e00-\u9fa5]{2,6})/)?.[1]
            || "新助手";
  const role = /分析|数据|sql/i.test(text) ? "Data analyst"
            : /编辑|改稿/i.test(text)       ? "Content editor"
            : /客服|support/i.test(text)    ? "Support agent"
            : /研究|调研|research/i.test(text) ? "Researcher"
            : /文案|copy/i.test(text)       ? "Copywriter"
            : "Specialist";
  const skills = [];
  if (/python|pandas|sql|图表/i.test(text)) skills.push("analytics");
  if (/编辑|改稿|line edit/i.test(text))   skills.push("writing");
  if (/调研|研究|对比|来源/i.test(text))   skills.push("research");
  if (/客服|支持|工单/i.test(text))         skills.push("support");
  if (/code|代码|diff|审阅/i.test(text))   skills.push("code-review");
  if (skills.length === 0) skills.push("writing");
  return {
    name, role, skills,
    systemPrompt:
`你是一位 ${role}。
基于用户描述：「${text.slice(0, 120)}」。
工作准则：
- 优先解决用户提出的问题，遇到边界先开口问。
- 引用来源，不要编造数据。
- 输出结构化，先结论后细节。`
  };
};

const ConvoPath = ({ onCancel, onCreate }) => {
  const [history, setHistory] = React.useState([
    { from: "agent", text: "好的 —— 用一句话告诉我你想要一个什么样的助手。比如：「专攻 Python 数据分析，擅长 pandas 和 matplotlib」。" },
  ]);
  const [val, setVal] = React.useState("");
  const [draft, setDraft] = React.useState(null);

  const send = () => {
    if (!val.trim()) return;
    const userMsg = { from: "user", text: val.trim() };
    setHistory(h => [...h, userMsg]);
    setVal("");
    setTimeout(() => {
      const d = SCRIPTED_REPLY(userMsg.text);
      setDraft(d);
      setHistory(h => [...h, {
        from: "agent",
        text: `我帮你拟了一个草稿，看一下右边。名字「${d.name}」，角色「${d.role}」，建议挂载：${d.skills.join(" · ")}。如果想调整，告诉我哪里不对。`,
      }]);
    }, 700);
  };

  return (
    <div className="flex-1 min-h-0 grid" style={{ gridTemplateColumns: "1fr 280px" }}>
      <div className="flex flex-col min-h-0 border-r">
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {history.map((m, i) => (
            <div key={i} className="flex gap-3 animate-fade-in">
              <Avatar initial={m.from === "agent" ? "助" : DATA.user.initial} color={m.from === "agent" ? "brand" : "neutral"} size={28}/>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[12px] font-semibold">{m.from === "agent" ? "助手向导" : DATA.user.handle}</span>
                  {m.from === "agent" && <Badge variant="brand">AI</Badge>}
                </div>
                <p className="text-[13.5px] leading-relaxed" style={{ textWrap: "pretty" }}>{m.text}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="border-t p-3">
          <div className="flex items-center gap-2 rounded-xl border bg-background pl-3 pr-1 focus-within:ring-2 focus-within:ring-ring">
            <input value={val}
              onChange={e => setVal(e.target.value)}
              onKeyDown={e => e.key === "Enter" && send()}
              placeholder="告诉我你想要的助手…"
              className="flex-1 h-10 bg-transparent text-[13.5px] outline-none placeholder:text-muted-foreground"/>
            <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
              <Icon name="send" className="h-3.5 w-3.5"/>
            </Button>
          </div>
        </div>
      </div>

      <aside className="flex flex-col min-h-0 bg-muted/20">
        <header className="border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="sparkles" className="h-3.5 w-3.5 text-brand"/>
            <h4 className="text-[13.5px] font-semibold tracking-tight">草稿</h4>
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">系统根据你的描述生成</p>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
          {!draft ? (
            <div className="text-[12px] text-muted-foreground text-center pt-8 leading-relaxed">
              发一条描述<br/>右边会出现一份草稿
            </div>
          ) : (
            <>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">名称</div>
                <div className="text-[14px] font-medium mt-0.5">{draft.name}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">角色</div>
                <div className="text-[14px] mt-0.5">{draft.role}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">技能</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {draft.skills.map(s => (
                    <span key={s} className="rounded border bg-background px-1.5 py-0.5 font-mono text-[10.5px]">{s}</span>
                  ))}
                </div>
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">System prompt</div>
                <pre className="mt-1 rounded border bg-background p-2 font-mono text-[10.5px] leading-relaxed whitespace-pre-wrap text-foreground/80 max-h-[140px] overflow-y-auto">
{draft.systemPrompt}
                </pre>
              </div>
            </>
          )}
        </div>
        <footer className="border-t p-3 space-y-2">
          <Button variant="brand" disabled={!draft} className="w-full"
            onClick={() => draft && onCreate({ ...draft, provider: "anthropic", model: "claude-sonnet-4-5" })}>
            <Icon name="userPlus" className="h-3.5 w-3.5"/>用这份草稿创建
          </Button>
          <Button variant="ghost" size="sm" className="w-full" onClick={onCancel}>取消</Button>
        </footer>
      </aside>
    </div>
  );
};

/* ── Modal shell ──────────────────────────────────────────────── */

const CreateAgentModal = ({ open, onClose, onCreated }) => {
  const [mode, setMode] = React.useState("form");
  const handleCreate = (draft) => {
    onCreated && onCreated(draft);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="w-[760px] max-w-[calc(100vw-2rem)]">
        <header className="flex items-center justify-between gap-3 border-b px-5 py-3.5">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand/10 text-brand">
              <Icon name="userPlus" className="h-4 w-4"/>
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-semibold tracking-tight">创建助手</h3>
              <p className="text-[11px] text-muted-foreground">填表，或者直接描述你要什么</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Tabs value={mode} onValueChange={setMode}>
              <TabsList className="h-8">
                <TabsTrigger value="form"  className="h-6 px-3 text-[12px]">
                  <Icon name="sliders" className="h-3 w-3"/>表单
                </TabsTrigger>
                <TabsTrigger value="convo" className="h-6 px-3 text-[12px]">
                  <Icon name="chat" className="h-3 w-3"/>对话
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <Button variant="ghost" size="iconSm" onClick={onClose}>
              <Icon name="x" className="h-3.5 w-3.5"/>
            </Button>
          </div>
        </header>

        {mode === "form"
          ? <FormPath  onCancel={onClose} onCreate={handleCreate}/>
          : <ConvoPath onCancel={onClose} onCreate={handleCreate}/>}
      </DialogContent>
    </Dialog>
  );
};

window.CreateAgentModal = CreateAgentModal;
