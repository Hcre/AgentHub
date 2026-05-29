// AgentHub v0 — main app
const { useReducer, useState, useEffect, useMemo, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#c96342",
  "theme": "light",
  "density": "comfort",
  "headingFont": "Source Serif 4",
  "glass": "frosted"
} /*EDITMODE-END*/;

const ACCENT_MAP = {
  "#c96342": { brand: "12 56% 53%", deep: "16 60% 33%", soft: "22 60% 91%" },
  "#4a6fa5": { brand: "214 38% 47%", deep: "214 50% 30%", soft: "214 50% 92%" },
  "#5f7a68": { brand: "143 13% 43%", deep: "143 20% 26%", soft: "143 25% 91%" },
  "#7d4f6e": { brand: "322 22% 40%", deep: "322 30% 26%", soft: "322 30% 92%" }
};

// Helpers
const nowStamp = () => {
  const n = new Date();
  return `${String(n.getHours()).padStart(2, "0")}:${String(n.getMinutes()).padStart(2, "0")}`;
};
const longStamp = () => {
  const n = new Date();
  return `${String(n.getMonth() + 1).padStart(2, "0")}月${String(n.getDate()).padStart(2, "0")}日 ${nowStamp()}`;
};
const uid = (prefix = "id") => prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

function reducer(state, action) {
  switch (action.type) {
    case "set": return { ...state, ...action.patch };

    /* ── messages ─────────────────────────────────────────────── */
    case "send": {
      const { agentId, conversationId } = state;
      const msgs = state.messages[agentId] || {};
      const list = msgs[conversationId] || [];
      const newList = [...list, { id: uid("u"), from: "user", time: nowStamp(), text: action.text }];
      return {
        ...state,
        messages: { ...state.messages, [agentId]: { ...msgs, [conversationId]: newList } },
        _pendingReply: { agentId, conversationId, at: Date.now() }
      };
    }
    case "agentReply": {
      const { agentId, conversationId, text, time } = action;
      const msgs = state.messages[agentId] || {};
      const list = msgs[conversationId] || [];
      const newList = [...list, { id: uid("a"), from: "agent", time, text }];
      return {
        ...state,
        messages: { ...state.messages, [agentId]: { ...msgs, [conversationId]: newList } },
        _pendingReply: null
      };
    }
    case "sendGroup": {
      const { groupId } = state;
      const list = state.groupMessages[groupId] || [];
      const newList = [...list, { id: uid("gu"), from: "user", who: "user", time: longStamp(), text: action.text, requiresApproval: action.requiresApproval }];
      return {
        ...state,
        groupMessages: { ...state.groupMessages, [groupId]: newList },
        _pendingGroupReply: { groupId, text: action.text, at: Date.now() }
      };
    }
    case "groupReply": {
      const { groupId, msg } = action;
      const list = state.groupMessages[groupId] || [];
      return {
        ...state,
        groupMessages: { ...state.groupMessages, [groupId]: [...list, msg] },
        _pendingGroupReply: null
      };
    }

    /* ── stage (right-panel mini task list) ───────────────────── */
    case "toggleStage": {
      const cycle = { todo: "doing", doing: "done", done: "todo" };
      return { ...state, stage: state.stage.map((t) => t.id === action.id ? { ...t, state: cycle[t.state] } : t) };
    }
    case "addStage": {
      return { ...state, stage: [...state.stage, { id: uid("st"), label: action.label || "新任务", state: "todo", eta: action.eta || 10 }] };
    }
    case "removeStage": {
      return { ...state, stage: state.stage.filter((t) => t.id !== action.id) };
    }

    /* ── tasks (the big kanban / list) ────────────────────────── */
    case "addTask": {
      return { ...state, tasks: [...state.tasks, action.task] };
    }
    case "updateTask": {
      return { ...state, tasks: state.tasks.map(t => t.id === action.id ? { ...t, ...action.patch } : t) };
    }
    case "deleteTask": {
      return { ...state, tasks: state.tasks.filter(t => t.id !== action.id) };
    }
    case "moveTask": {
      return { ...state, tasks: state.tasks.map(t => t.id === action.id ? { ...t, state: action.toState } : t) };
    }

    /* ── memory ───────────────────────────────────────────────── */
    case "updateMemory": {
      return { ...state, memory: state.memory.map(m => m.id === action.id ? { ...m, ...action.patch } : m) };
    }
    case "deleteMemory": {
      return { ...state, memory: state.memory.filter(m => m.id !== action.id) };
    }

    /* ── skills ───────────────────────────────────────────────── */
    case "addSkill": {
      if (state.skills.some(s => s.id === action.skill.id)) return state;
      return { ...state, skills: [...state.skills, action.skill] };
    }
    case "removeSkill": {
      return { ...state, skills: state.skills.filter(s => s.id !== action.id) };
    }

    /* ── agents ───────────────────────────────────────────────── */
    case "addAgent": {
      return { ...state, agents: [...state.agents, action.agent] };
    }
    case "deleteAgent": {
      return {
        ...state,
        agents: state.agents.filter(a => a.id !== action.id),
        agentId: state.agentId === action.id ? state.agents.find(a => a.id !== action.id)?.id : state.agentId,
      };
    }
    case "updateAgent": {
      return { ...state, agents: state.agents.map(a => a.id === action.id ? { ...a, ...action.patch } : a) };
    }

    /* ── conversations ────────────────────────────────────────── */
    case "addConversation": {
      const { agentId, conv } = action;
      const list = state.conversations[agentId] || [];
      return {
        ...state,
        conversations: { ...state.conversations, [agentId]: [...list, conv] },
        conversationId: conv.id,
        messages: { ...state.messages, [agentId]: { ...(state.messages[agentId] || {}), [conv.id]: [] } },
      };
    }

    /* ── outputs ──────────────────────────────────────────────── */
    case "addOutput": {
      return { ...state, outputs: [...state.outputs, action.output] };
    }
    case "deleteOutput": {
      return { ...state, outputs: state.outputs.filter(o => o.id !== action.id) };
    }

    /* ── inbox ────────────────────────────────────────────────── */
    case "updateInboxItem": {
      return { ...state, inbox: state.inbox.map(i => i.id === action.id ? { ...i, ...action.patch } : i) };
    }
    case "deleteInboxItem": {
      return { ...state, inbox: state.inbox.filter(i => i.id !== action.id) };
    }

    /* ── channels ─────────────────────────────────────────────── */
    case "addChannel": {
      return { ...state, channels: [...state.channels, action.channel] };
    }

    /* ── calendar ─────────────────────────────────────────────── */
    case "setCalendar": {
      return { ...state, calendar: { ...state.calendar, ...action.patch } };
    }
    case "addEvent": {
      return { ...state, calendarEvents: [...state.calendarEvents, action.event] };
    }

    /* ── toasts ───────────────────────────────────────────────── */
    case "pushToast": {
      return { ...state, toasts: [...(state.toasts || []), action.toast] };
    }
    case "dismissToast": {
      return { ...state, toasts: (state.toasts || []).filter(t => t.id !== action.id) };
    }

    /* ── confirm ──────────────────────────────────────────────── */
    case "openConfirm": {
      return { ...state, confirm: action.payload };
    }
    case "closeConfirm": {
      return { ...state, confirm: null };
    }

    default: return state;
  }
}

function init() {
  return {
    // Routing
    agentId: "editor",
    conversationId: "c2",
    section: "chat",
    centerTab: "chat",
    groupId: null,
    sidebarCollapsed: false,
    rightCollapsed: false,
    historyOpen: true,
    modal: null,

    // Mutable data (lifted out of DATA constants)
    agents: DATA.agents.slice(),
    conversations: { ...DATA.conversations },
    messages: { ...DATA.messages },
    groupMessages: { ...DATA_EXTRA.groupMessages },
    stage: DATA.stage.slice(),
    outputs: DATA.outputs.slice(),
    tasks: DATA.tasks.slice(),
    memory: DATA.memory.slice(),
    skills: DATA.skills.slice(),
    channels: DATA.channels.slice(),
    inbox: DATA_EXTRA.inbox.slice(),
    calendarEvents: DATA_EXTRA.calendarEvents.slice(),

    // Calendar UI state
    calendar: {
      // "today" anchor for the prototype: 2026-05-22
      cursor: "2026-05-22",
      view: "week", // month | week | day
    },

    // Ephemeral
    toasts: [],
    confirm: null,
    _pendingReply: null,
    _pendingGroupReply: null,
  };
}

function App() {
  const [state, dispatch] = useReducer(reducer, undefined, init);
  const setState = (patch) => dispatch({ type: "set", patch: typeof patch === "function" ? patch(state) : patch });
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // theme class
  useEffect(() => {
    document.documentElement.classList.toggle("dark", tweaks.theme === "dark");
  }, [tweaks.theme]);

  const accent = ACCENT_MAP[tweaks.accent] || ACCENT_MAP["#c96342"];
  const headFontFallback = tweaks.headingFont === "Geist" ? "ui-sans-serif, system-ui" :
    tweaks.headingFont === "IBM Plex Sans" ? "sans-serif" :
    tweaks.headingFont === "Inter" ? "sans-serif" :
    "\"Tiempos Headline\", Georgia, serif";

  // fake agent reply
  useEffect(() => {
    if (!state._pendingReply) return;
    const { agentId, conversationId } = state._pendingReply;
    const t = setTimeout(() => {
      const replies = [
        "Got it. Reading through now — I'll come back with a structured pass.",
        "On it. Will queue a new task in 阶段 so you can watch progress.",
        "Understood. Want me to flag any open questions inline, or save them as a separate task?",
        "Drafting. Be back in ~30s."
      ];
      const text = replies[Math.floor(Math.random() * replies.length)];
      dispatch({ type: "agentReply", agentId, conversationId, text, time: nowStamp() });
    }, 1100);
    return () => clearTimeout(t);
  }, [state._pendingReply]);

  // fake group reply — try to figure out who was @'d
  useEffect(() => {
    if (!state._pendingGroupReply) return;
    const { groupId, text } = state._pendingGroupReply;
    const group = DATA_EXTRA.groups.find((g) => g.id === groupId);
    const mentioned = text.match(/@(\S+)/g)?.map((m) => m.slice(1)) || [];
    const who = mentioned.includes("协调者") ? "coordinator" :
      group?.members.find((mid) => mentioned.includes(state.agents.find((a) => a.id === mid)?.name)) || group?.members[0] || "editor";
    const t = setTimeout(() => {
      const replyText = who === "coordinator" ?
        "收到。我看一下上下文，20 秒后回一份拆分方案。" :
        `收到。我走一下，不退进就出初稿。`;
      dispatch({
        type: "groupReply",
        groupId,
        msg: { id: uid("gr"), from: "agent", who, time: longStamp(), text: replyText }
      });
    }, 1200);
    return () => clearTimeout(t);
  }, [state._pendingGroupReply]);

  const agent = state.agents.find((a) => a.id === state.agentId) || state.agents[0];
  const showRight = state.section === "chat" || state.section === "group";

  return (
    <AppProvider state={state} dispatch={dispatch}>
      <div className="flex h-full ah-shell"
        data-density={tweaks.density}
        data-glass={tweaks.glass}
        style={{
          "--brand": accent.brand,
          "--brand-deep": accent.deep,
          "--brand-soft": accent.soft,
          "--ring": accent.brand,
          "--ah-head-font": `"${tweaks.headingFont}", ${headFontFallback}`
        }}>
        {/* Sidebar */}
        <div className={cn(
          "transition-all duration-300 ease-out overflow-hidden flex-shrink-0 p-2.5 pr-1.5",
          state.sidebarCollapsed ? "w-0 p-0" : "w-[280px]"
        )}>
          <Sidebar state={state} setState={setState}
            onCollapse={() => setState({ sidebarCollapsed: true })}
            onCreateAgent={() => setState({ modal: "createAgent" })} />
        </div>

        {/* Floating reopen */}
        {state.sidebarCollapsed &&
          <button onClick={() => setState({ sidebarCollapsed: false })}
            className="fixed left-3 top-3 z-30 grid h-9 w-9 place-items-center rounded-lg border glass-strong text-muted-foreground shadow-sm hover:text-foreground transition-colors animate-fade-in"
            title="展开侧边栏">
            <Icon name="panelLeft" className="h-3.5 w-3.5" />
          </button>
        }

        {/* Center — routed by state.section */}
        <div className="flex-1 min-w-0 py-2.5">
          {state.section === "group" &&
            <GroupChatView groupId={state.groupId} state={state} setState={setState}
              tweaks={tweaks} setTweak={setTweak}
              onSend={(text, opts) => dispatch({ type: "sendGroup", text, requiresApproval: opts?.requiresApproval })}
              onPickAgent={(aid) => setState({ section: "agent-detail", agentId: aid })} />
          }
          {state.section === "inbox" && <InboxView />}
          {state.section === "tasks" && <TasksPage openCreate={() => setState({ modal: "createTask" })} />}
          {state.section === "calendar" && <CalendarPage agent={agent} />}
          {state.section === "agent-detail" &&
            <AgentDetailPage agentId={state.agentId}
              onBack={() => setState({ section: "chat" })} />
          }
          {state.section === "chat" &&
            <CenterPanel agent={agent} state={state} setState={setState}
              tweaks={tweaks} setTweak={setTweak}
              onSend={(text) => dispatch({ type: "send", text })}
              onToggleStage={(id) => dispatch({ type: "toggleStage", id })}
              openCreateTask={() => setState({ modal: "createTask" })} />
          }
        </div>

        {/* Right */}
        <div className={cn(
          "transition-all duration-300 ease-out overflow-hidden flex-shrink-0 p-2.5 pl-1.5",
          state.rightCollapsed || !showRight ? "w-0 p-0" : "w-[340px]"
        )}>
          {showRight && <RightPanel state={state} onToggleTask={(id) => dispatch({ type: "toggleStage", id })} />}
        </div>

        <CreateTaskModal open={state.modal === "createTask"} agent={agent}
          onClose={() => setState({ modal: null })} />
        <CreateAgentModal open={state.modal === "createAgent"}
          onClose={() => setState({ modal: null })}
          onCreated={(draft) => {
            const id = uid("agent");
            const newAgent = {
              id,
              name: draft.name || "新助手",
              role: draft.role || "Specialist",
              color: draft.color || "brand",
              online: true,
              skillCount: (draft.skills || []).length,
            };
            dispatch({ type: "addAgent", agent: newAgent });
            dispatch({ type: "set", patch: { agentId: id, section: "chat" } });
            dispatch({
              type: "pushToast",
              toast: { id: uid("t"), message: `已创建助手「${newAgent.name}」`, kind: "success" },
            });
          }} />

        <TweaksPanel title="Tweaks">
          <TweakSection title="Theme">
            <TweakRadio label="Mode" value={tweaks.theme} onChange={(v) => setTweak("theme", v)}
              options={[{ value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
            <TweakColor label="Accent" value={tweaks.accent}
              options={Object.keys(ACCENT_MAP)}
              onChange={(v) => setTweak("accent", v)} />
          </TweakSection>
          <TweakSection title="Layout">
            <TweakRadio label="Density" value={tweaks.density} onChange={(v) => setTweak("density", v)}
              options={[{ value: "compact", label: "Compact" }, { value: "comfort", label: "Comfort" }]} />
            <TweakRadio label="Glass" value={tweaks.glass} onChange={(v) => setTweak("glass", v)}
              options={[{ value: "frosted", label: "Frosted" }, { value: "solid", label: "Solid" }]} />
          </TweakSection>
          <TweakSection title="Type">
            <TweakSelect label="Heading" value={tweaks.headingFont}
              options={[
                { value: "Source Serif 4", label: "Source Serif (Editorial)" },
                { value: "Instrument Serif", label: "Instrument Serif" },
                { value: "Geist", label: "Geist Sans" },
                { value: "IBM Plex Sans", label: "IBM Plex Sans" },
                { value: "Inter", label: "Inter" }
              ]}
              onChange={(v) => setTweak("headingFont", v)} />
          </TweakSection>
        </TweaksPanel>
      </div>
    </AppProvider>
  );
}

const CenterPanel = ({ agent, state, setState, tweaks, setTweak, onSend, onToggleStage, openCreateTask }) => {
  const tabId = state.centerTab;
  const setTab = (id) => setState({ centerTab: id });
  return (
    <main className="flex h-full flex-col min-w-0 glass-panel border rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        <div className="flex items-center gap-3">
          <Avatar initial={agent.name[0]} color={agent.color} size={32} online={agent.online} />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="heading-serif text-[22px] font-medium tracking-tight">{agent.name}</h1>
              <Badge variant="brand">AI</Badge>
            </div>
            <div className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-0.5">
              {agent.role} · 私密 · 仅你可见
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="iconSm"
            onClick={() => setTweak("theme", tweaks.theme === "dark" ? "light" : "dark")}
            title={tweaks.theme === "dark" ? "切换为浅色" : "切换为深色"}>
            <Icon name={tweaks.theme === "dark" ? "sun" : "moon"} className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm"
            onClick={() => setState((s) => ({ rightCollapsed: !s.rightCollapsed }))}
            title="收起侧面板">
            <Icon name="panelRight" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>

      {/* Tabs */}
      <nav className="border-b border-border/70 glass-soft px-3 py-1.5 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
        <div className="flex gap-0.5">
          {DATA.centerTabs.map((t) =>
            <button key={t.id} onClick={() => setTab(t.id)}
              data-active={tabId === t.id ? "true" : undefined}
              className={cn(
                "relative inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[12.5px] font-medium",
                "text-muted-foreground hover:bg-accent/60 hover:text-foreground transition-colors",
                "data-[active=true]:glass-strong data-[active=true]:text-foreground data-[active=true]:shadow-sm"
              )}>
              <Icon name={t.icon} className="h-3.5 w-3.5" />
              <span>{t.label}</span>
              <span className={cn("absolute -bottom-[7px] left-3 right-3 h-0.5 rounded-full bg-brand transition-transform origin-center",
                tabId === t.id ? "scale-x-100" : "scale-x-0")} />
            </button>
          )}
        </div>
      </nav>

      {/* Body */}
      <div className="flex-1 min-h-0 flex flex-col animate-fade-in" key={tabId}>
        {tabId === "chat" &&
          <ChatView agent={agent} user={DATA.user}
            conversations={state.conversations}
            messages={state.messages}
            activeConvId={state.conversationId}
            setActiveConvId={(id) => setState({ conversationId: id })}
            historyOpen={state.historyOpen}
            setHistoryOpen={(v) => setState({ historyOpen: v })}
            pendingReply={state._pendingReply && state._pendingReply.agentId === agent.id && state._pendingReply.conversationId === state.conversationId}
            onSend={onSend} />
        }
        {tabId === "tasks" && <TasksTabView openCreate={openCreateTask} />}
        {tabId === "activity" && <ActivityView events={DATA.activity} user={DATA.user} />}
        {tabId === "calendar" && <CalendarView agent={agent} />}
        {tabId === "channels" && <ChannelsView agent={agent} />}
        {tabId === "files" && <FilesView />}
        {tabId === "skills" && <SkillsView />}
        {tabId === "memory" && <MemoryView />}
        {tabId === "settings" && <SettingsView agent={agent} />}
      </div>
    </main>
  );
};

window.uid = uid;
window.nowStamp = nowStamp;
window.longStamp = longStamp;

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
