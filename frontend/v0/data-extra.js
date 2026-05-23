// Extra data for Phase 4-6: groups, coordinator messages, inbox, agent detail.
window.DATA_EXTRA = {
  // Coordinator agent that orchestrates group work
  coordinator: {
    id: "coordinator",
    name: "协调者",
    role: "Coordinator",
    color: "brand",
    online: true,
    bio: "I read what the team needs, break it into the right shape of subtasks, and hand them to the agents who fit. Tag me @协调者 in a channel and tell me the outcome you want.",
  },

  groups: [
    {
      id: "content",
      name: "content",
      description: "Long-form drafts, launch posts, narrative work.",
      members: ["editor", "copywriter", "researcher"],
      pinnedTask: "Q4 launch post draft v3",
    },
    {
      id: "design",
      name: "design",
      description: "Pricing page redesign · shared between editor and PM.",
      members: ["editor", "copywriter"],
      pinnedTask: "Pricing page restructure",
    },
    {
      id: "growth",
      name: "growth",
      description: "Ads, lifecycle copy, retention experiments.",
      members: ["copywriter", "researcher"],
      pinnedTask: "Lifecycle email sequence",
    },
  ],

  // Sample messages for a group channel — shows coordinator pattern
  groupMessages: {
    design: [
      {
        id: "g1", from: "user", who: "user", time: "10月22日 14:02",
        text: "@协调者 帮我把定价页改稿这件事拆一下。需要：三个套餐开头重写、价格表挪到下面、对比表脚注收紧。周五前要发评审。",
      },
      {
        id: "g2", from: "agent", who: "coordinator", time: "10月22日 14:02",
        kind: "plan",
        plan: {
          summary: "我把这个拆成 3 个并行子任务，全部目标周四晚结，周五一起进评审。",
          steps: [
            { id: "s1", who: "editor",     label: "三套餐开头一句话 + 证据点",       eta: 25, depends: [] },
            { id: "s2", who: "editor",     label: "价格表下移到价值主张下方",         eta: 15, depends: ["s1"] },
            { id: "s3", who: "researcher", label: "拉取三家竞品最新定价页 (来源)",    eta: 30, depends: [] },
            { id: "s4", who: "editor",     label: "依据来源收紧对比表脚注",           eta: 20, depends: ["s3"] },
          ],
          watchouts: ["Starter / Team / Business 三档名称已锁，不改。"],
        },
      },
      {
        id: "g3", from: "agent", who: "editor", time: "10月22日 14:04",
        text: "收到 s1 + s2 + s4。开头三句正在写，半小时内回。",
      },
      {
        id: "g4", from: "agent", who: "researcher", time: "10月22日 14:05",
        text: "抓 s3。已经在拉 Linear / Notion / Coda 的当前定价页，30 分钟内出对照表 + 引用链接。",
      },
    ],
  },

  inbox: [
    {
      id: "in1",
      type: "approval",
      title: "编辑 想覆盖 pricing-v3.mdx 第 17-43 行",
      summary: "Three plan openers rewrite — 把每档「unlimited X」替换为一句「这档是给谁」+ 证据点。",
      actor: "editor",
      actorName: "编辑",
      when: "刚刚",
      diff: [
        { kind: "del", text: "## Starter — Unlimited drafts" },
        { kind: "add", text: "## Starter — For solo PMs shipping their first revenue page" },
        { kind: "neutral", text: "Used by 1,200 indie PMs since launch." },
        { kind: "del", text: "## Team — Unlimited seats" },
        { kind: "add", text: "## Team — For 3–12 person PM teams sharing one source of truth" },
      ],
      impact: "影响 pricing-v3.mdx (1 个文件) · 27 行",
      unread: true,
    },
    {
      id: "in2",
      type: "approval",
      title: "研究员 想把 3 个竞品引用加进 pricing-v3.mdx",
      summary: "在脚注引用 Linear / Notion / Coda 的官方定价页，作为对比表来源。",
      actor: "researcher",
      actorName: "研究员",
      when: "12 分钟前",
      diff: [
        { kind: "add", text: "[^1]: Linear pricing — linear.app/pricing · 2026-05-22 11:14 UTC" },
        { kind: "add", text: "[^2]: Notion pricing — notion.so/pricing · 2026-05-22 11:14 UTC" },
        { kind: "add", text: "[^3]: Coda pricing — coda.io/pricing · 2026-05-22 11:14 UTC" },
      ],
      impact: "新增 3 个脚注 · 0 个删除",
      unread: true,
    },
    {
      id: "in3",
      type: "task",
      title: "你被指派为 MO-6 的复核人",
      summary: "Audit footnote citations vs source — 协调者把核对脚注的复核环节路给了你。",
      actor: "coordinator",
      actorName: "协调者",
      when: "30 分钟前",
      unread: true,
    },
    {
      id: "in4",
      type: "system",
      title: "文案 已升级到 claude-sonnet-4-5",
      summary: "周一升级后保留全部 system prompt 与已订阅频道。",
      when: "昨天 18:20",
      unread: false,
    },
    {
      id: "in5",
      type: "task",
      title: "MO-4 完成 · Draft 3 hero directions",
      summary: "文案 提交了 3 个 hero 方向 + 推荐一个上线版本。等你过一眼。",
      actor: "copywriter",
      actorName: "文案",
      when: "昨天 16:42",
      unread: false,
    },
  ],

  // Agent extended profile (one for each agent we already have)
  agentProfiles: {
    editor: {
      bio: "Revises existing drafts for clarity, structure, voice, and trust while preserving the author's intent. Wake for line edits, structural revisions, tone alignment, or final polish on existing prose — not for first-draft writing or strategic messaging direction.",
      load: 0.42,
      groups: ["content", "design"],
      capabilities: ["Line edit", "Copy edit", "Structural", "Tone & voice", "Pacing", "Heading rewrite", "Footnote audit"],
      memoryByLevel: [
        { level: "L1", name: "Session", count: 14, hint: "活跃对话即时上下文" },
        { level: "L2", name: "Project", count: 38, hint: "Pricing redesign 项目状态" },
        { level: "L3", name: "Persona", count: 7, hint: "用户偏好与禁区" },
        { level: "L4", name: "World",   count: 23, hint: "Acme 风格与品牌锁定" },
      ],
      config: { provider: "anthropic", model: "claude-sonnet-4-5", maxTokens: 8192, concurrency: 2, temperature: 0.4 },
    },
    copywriter: {
      bio: "Writes from a brief — landing copy, ads, launch announcements, push notifications. Tell me the audience, the offer, and the one thing they should walk away with.",
      load: 0.61,
      groups: ["design", "growth"],
      capabilities: ["Landing pages", "Ad copy", "Email", "Notifications", "Headline tests", "Microcopy"],
      memoryByLevel: [
        { level: "L1", name: "Session", count: 8,  hint: "" },
        { level: "L2", name: "Project", count: 19, hint: "" },
        { level: "L3", name: "Persona", count: 5,  hint: "" },
        { level: "L4", name: "World",   count: 23, hint: "" },
      ],
      config: { provider: "anthropic", model: "claude-sonnet-4-5", maxTokens: 4096, concurrency: 3, temperature: 0.7 },
    },
    researcher: {
      bio: "I dig through sources, synthesize findings, and surface what's load-bearing. Give me a question and a deadline.",
      load: 0.18,
      groups: ["content", "growth"],
      capabilities: ["Lit review", "Competitive scan", "Synthesis", "Citations"],
      memoryByLevel: [
        { level: "L1", name: "Session", count: 4,  hint: "" },
        { level: "L2", name: "Project", count: 12, hint: "" },
        { level: "L3", name: "Persona", count: 3,  hint: "" },
        { level: "L4", name: "World",   count: 23, hint: "" },
      ],
      config: { provider: "openai", model: "gpt-4o", maxTokens: 8192, concurrency: 1, temperature: 0.2 },
    },
  },

  providers: [
    { id: "anthropic", label: "Anthropic", models: ["claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5"] },
    { id: "openai",    label: "OpenAI",    models: ["gpt-4o", "gpt-4o-mini", "o3"] },
    { id: "azure",     label: "Azure",     models: ["gpt-4o-azure", "gpt-4o-mini-azure"] },
  ],

  // Multi-month calendar events for the real prev/next/today + view-switching.
  // Each event is { date: "YYYY-MM-DD", startHour, endHour, title, tone }.
  // Spans April–June 2026 around the prototype "today" of 2026-05-22.
  calendarEvents: [
    // April 2026
    { id: "ce-apr-1",  date: "2026-04-06", startHour: 10, endHour: 11, title: "Q2 kickoff",            tone: "brand" },
    { id: "ce-apr-2",  date: "2026-04-13", startHour: 14, endHour: 15, title: "Roadmap review",        tone: "sage" },
    { id: "ce-apr-3",  date: "2026-04-21", startHour:  9, endHour: 10, title: "Brand guidelines sync", tone: "brand" },
    { id: "ce-apr-4",  date: "2026-04-28", startHour: 15, endHour: 17, title: "Launch retro",          tone: "sage" },
    // Early May
    { id: "ce-may-1",  date: "2026-05-04", startHour: 11, endHour: 12, title: "Pricing kickoff",       tone: "brand" },
    { id: "ce-may-2",  date: "2026-05-06", startHour: 14, endHour: 15, title: "Competitive scan",      tone: "sage" },
    { id: "ce-may-3",  date: "2026-05-11", startHour:  9, endHour: 10, title: "Editor briefing",       tone: "brand" },
    { id: "ce-may-4",  date: "2026-05-13", startHour: 15, endHour: 16, title: "Copy review",           tone: "sage" },
    // The "current" week (May 17–23, today = May 22)
    { id: "ce-may-5",  date: "2026-05-18", startHour:  9, endHour: 10, title: "Editor briefing",       tone: "brand" },
    { id: "ce-may-6",  date: "2026-05-19", startHour: 13, endHour: 14, title: "Pricing pass v1",       tone: "brand" },
    { id: "ce-may-7",  date: "2026-05-20", startHour: 11, endHour: 12, title: "Sources review",        tone: "sage" },
    { id: "ce-may-8",  date: "2026-05-21", startHour: 14, endHour: 15, title: "Draft review",          tone: "sage" },
    { id: "ce-may-9",  date: "2026-05-22", startHour: 11, endHour: 12, title: "Pricing pass · 阶段 1", tone: "brand" },
    { id: "ce-may-10", date: "2026-05-22", startHour: 16, endHour: 17, title: "Stand-up",              tone: "sage" },
    // Later May
    { id: "ce-may-11", date: "2026-05-26", startHour: 10, endHour: 11, title: "Eval rubric",           tone: "brand" },
    { id: "ce-may-12", date: "2026-05-28", startHour: 14, endHour: 16, title: "Launch dry-run",        tone: "sage" },
    // June 2026
    { id: "ce-jun-1",  date: "2026-06-02", startHour:  9, endHour: 10, title: "Sprint plan",           tone: "brand" },
    { id: "ce-jun-2",  date: "2026-06-09", startHour: 14, endHour: 15, title: "Copy v2 review",        tone: "sage" },
    { id: "ce-jun-3",  date: "2026-06-16", startHour: 11, endHour: 13, title: "Customer call",         tone: "brand" },
    { id: "ce-jun-4",  date: "2026-06-22", startHour: 15, endHour: 16, title: "Mid-quarter check-in",  tone: "sage" },
  ],

  // Curated skill catalog for the Create Agent / capability picker
  skillCatalog: [
    { id: "writing",       name: "writing",       desc: "Drafting, line edits, structural revision." },
    { id: "research",      name: "research",      desc: "Source pulls, synthesis, citations." },
    { id: "ads",           name: "ads",           desc: "Landing copy, paid social, push." },
    { id: "support",       name: "support",       desc: "Customer support replies w/ macros." },
    { id: "analytics",     name: "analytics",     desc: "SQL / pandas / chart generation." },
    { id: "code-review",   name: "code-review",   desc: "Diff review with style/safety checks." },
    { id: "summarize",     name: "summarize",     desc: "Long-doc summarization, action extraction." },
  ],
};
