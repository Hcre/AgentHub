// Sample data for AgentHub v0
window.DATA = {
  org: { name: "Acme", initial: "A" },
  user: { handle: "xiangbianpangde", name: "旁边胖的", initial: "T" },
  nav: [
    { id: "inbox",    icon: "inbox",     label: "收件箱", count: 3 },
    { id: "tasks",    icon: "listCheck", label: "任务",   count: 7 },
    { id: "calendar", icon: "calendar",  label: "日历" },
  ],
  channels: [
    { id: "content", name: "content", unread: false },
    { id: "design",  name: "design",  unread: true },
    { id: "growth",  name: "growth",  unread: false },
  ],
  agents: [
    { id: "editor",     name: "编辑",   role: "Content editor", color: "brand", online: true,  skillCount: 4 },
    { id: "copywriter", name: "文案",   role: "Copywriter",     color: "sage",  online: true,  skillCount: 6 },
    { id: "researcher", name: "研究员", role: "Researcher",     color: "clay",  online: false, skillCount: 3 },
  ],
  dms: [
    { id: "lin",  name: "林小雨", initial: "林", online: true,  unread: 2 },
    { id: "zhao", name: "赵晨",   initial: "赵", online: false, unread: 0 },
  ],
  centerTabs: [
    { id: "chat",     icon: "chat",      label: "聊天" },
    { id: "tasks",    icon: "listCheck", label: "任务" },
    { id: "activity", icon: "activity",  label: "活动" },
    { id: "calendar", icon: "calendar",  label: "日历" },
    { id: "channels", icon: "channels",  label: "频道" },
    { id: "files",    icon: "files",     label: "文件" },
    { id: "skills",   icon: "sparkle",   label: "技能" },
    { id: "memory",   icon: "brain",     label: "记忆" },
    { id: "settings", icon: "settings",  label: "设置" },
  ],
  conversations: {
    editor: [
      { id: "c1", name: "对话 1", subtitle: "Q4 launch post" },
      { id: "c2", name: "对话 2", subtitle: "Pricing page draft" },
      { id: "c3", name: "对话 3", subtitle: "Investor memo" },
    ],
    copywriter: [{ id: "c1", name: "对话 1", subtitle: "Hero copy v3" }],
    researcher: [{ id: "c1", name: "对话 1", subtitle: "Agent market scan" }],
  },
  messages: {
    editor: {
      c2: [
        { id: "m1", from: "agent", time: "19:48",
          text: "Hi — I'm your content editor. I work on drafts you already have: tightening structure, sharpening claims, fixing pacing and tone, cutting throat-clearing without sanding off your voice.\n\nSend me anything you want a closer read on — a post, an email, a doc, a headline — and tell me who it's for and what kind of pass you want (light copy edit, line edit, structural, or tone)." },
        { id: "m2", from: "user", time: "19:51",
          text: "Pricing page draft attached. Audience is mid-market PMs evaluating us against three named competitors. Want a structural pass — the three plans bleed together right now.",
          attachment: { name: "pricing-v3.mdx", size: "8.4 KB" } },
        { id: "m3", from: "agent", time: "19:52",
          text: "Read it. The plans bleed because every tier opens with capacity (\"unlimited X\") instead of the job each tier is for. I'll rewrite each opener as a one-sentence \"who this is for\" + the proof point, then move pricing below. Drafting now — should land in 阶段 as task 1.",
          actions: ["Open diff", "View outline"] },
      ],
    },
    copywriter: { c1: [{ id: "m1", from: "agent", time: "14:02", text: "Hi — I'm your copywriter. Give me the audience, the offer, and the one thing they should walk away with, and I'll come back with 3 directions plus the one I'd ship." }] },
    researcher: { c1: [{ id: "m1", from: "agent", time: "10:14", text: "Hi — I'm your researcher. Give me a question and a deadline; I'll come back with a synthesis, sources, and the open questions worth a second pass." }] },
  },
  stage: [
    { id: "t1", label: "Rewrite three plan openers",            state: "doing", eta: 8 },
    { id: "t2", label: "Move pricing table below value props",  state: "todo",  eta: 5 },
    { id: "t3", label: "Tighten comparison footnotes",          state: "todo",  eta: 3 },
  ],
  outputs: [
    { id: "f1", name: "pricing-v3.mdx",         kind: "doc",  size: "8.4 KB", status: "input" },
    { id: "f2", name: "pricing-v3-edited.diff", kind: "diff", size: "—",      status: "pending" },
  ],
  tasks: [
    { id: "MO-1", title: "Rewrite three plan openers",           state: "todo",    priority: "high",   assignee: "editor",     due: "Today" },
    { id: "MO-2", title: "Move pricing table below value props", state: "todo",    priority: "normal", assignee: "editor",     due: "Wed" },
    { id: "MO-3", title: "Tighten comparison footnotes",         state: "todo",    priority: "low",    assignee: "editor",     due: "Fri" },
    { id: "MO-4", title: "Draft 3 hero directions",              state: "doing",   priority: "high",   assignee: "copywriter", due: "Today" },
    { id: "MO-5", title: "Source competitor pricing pages",      state: "doing",   priority: "normal", assignee: "researcher", due: "Mon" },
    { id: "MO-6", title: "Audit footnote citations vs source",   state: "blocked", priority: "normal", assignee: "editor",     due: "—" },
    { id: "MO-7", title: "Reconcile copy ↔ design tokens",       state: "done",    priority: "normal", assignee: "editor",     due: "Mon" },
  ],
  activity: [
    { id: "e1", when: "23:26", count: 2, latest: true,  tools: ["pricing-v3.mdx 读取", "结构分析", "生成草稿"],
      text: "Read it. The plans bleed because every tier opens with capacity. Drafting the three openers now — should land in 阶段 as task 1.",
      tail: "running" },
    { id: "e2", when: "19:48", count: 7, tools: ["channel.subscribe", "memory.recall", "ack.send"],
      text: "Hi — I'm your content editor. I work on drafts you already have: tightening structure, sharpening claims, fixing pacing and tone, cutting throat-clearing without sanding off your voice." },
  ],
  skills: [
    { id: "heliox",          name: "heliox",          desc: "Core CLI commands the assistant uses to coordinate work.",                                  locked: true },
    { id: "productivity",    name: "productivity",    desc: "Productivity toolkit — knowledge-work flows the assistant can drive.",                       locked: true },
    { id: "document-skills", name: "document-skills", desc: "Work with PDFs, docs, and spreadsheets.",                                                    locked: true },
    { id: "marketing",       name: "marketing",       desc: "Positioning, message-mapping, and channel-aware drafting helpers.",                          locked: true },
  ],
  memory: [
    { id: "m1", title: "Audience for pricing page",       body: "Mid-market PMs evaluating against three named competitors.", tags: ["audience","pricing"], status: "accepted", when: "2 天前" },
    { id: "m2", title: "Pass type defaults to structural", body: "User skips line edits unless they ask.",                     tags: ["voice"],              status: "pending",  when: "3 天前" },
    { id: "m3", title: "Plan-tier naming locked",         body: "Don't suggest renaming Starter/Team/Business.",               tags: ["copy"],               status: "archived", when: "1 周前" },
  ],
  calendar: {
    range: "May 17 – 23, 2026",
    days: [
      { abbr: "SUN", n: 17 }, { abbr: "MON", n: 18 }, { abbr: "TUE", n: 19 },
      { abbr: "WED", n: 20 }, { abbr: "THU", n: 21 }, { abbr: "FRI", n: 22, today: true }, { abbr: "SAT", n: 23 },
    ],
    events: [
      { day: 1, start: 9,  end: 10, title: "Editor briefing",       tone: "brand" },
      { day: 4, start: 14, end: 15, title: "Draft review",          tone: "sage" },
      { day: 5, start: 11, end: 12, title: "Pricing pass · 阶段 1", tone: "brand" },
    ],
  },
};
