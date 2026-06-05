---
状态:
  - 未整理
  - 已整理
创建时间: "[[../../../../04. 🔵 日记周记/01. 日记/2026-04-14]]"
链接:
  - "[[../../../../02. 🟡 归类 Arrange/所有归类/claude笔记目录|claude笔记目录]]"
---

# 📝 Claude 前端设计七重天：从 AI 模板地狱到视觉叙事大师

---

## 📌 元数据

| 项目 | 内容 |
|------|------|
| 标题 | Claude 前端设计七重天：从 AI 模板地狱到视觉叙事大师 |
| 标签 | #AI 前端开发 #ClaudeCode #前端设计 #设计系统 #AI 协作 #前端工程化 |
| 创建时间 | 2026-04-14 |
| 更新时间 | 2026-04-14 |
| 关联笔记 | [[claude-前端设计]] |

---

## 🎯 视频核心总览

> **视频来源**：B 站「Claude Code 前端设计的七个层级，从入门到可复用的设计系统」
> **实战载体**：虚拟产品 `Argus` 社交媒体情报平台
> **核心目标**：不靠玄学提示词，通过**设计教育、视觉输入、代码解构、创意定制**，让 AI 成为真正的视觉合伙人，彻底告别千篇一律的 AI 通用模板

---

## 🔺 七级跃迁总纲

| 层级  | 名称      | 核心目标                        |
| --- | ------- | --------------------------- |
| L1  | 纯文本提示陷阱 | 打破 AI 模板地狱，建立基础设计认知         |
| L2  | 注入设计知识  | 用设计规范给 AI 补课，规避 AI 设计雷区     |
| L3  | 视觉总监模式  | 用参考图代替形容词，让 AI 精准理解需求       |
| L4  | 代码克隆者   | 解构优秀网站的 HTML/CSS/JS，积累可复用组件 |
| L5  | 原创融合者   | 用组件市场+AI 绘图，打造专属品牌视觉资产      |
| L6  | 可视化协作者  | 打通设计工具，实现「所见即所得」迭代          |
| L7  | 前沿探索者   | 用 3D/WebGL 拓展设计边界，锚定长期进化方向  |

---

## 🧱 L1：纯文本提示陷阱

### 核心问题根源

仅靠模糊描述（如「为 Argus 做个着陆页」+ 默认 Plan 模式），会触发 Claude Code 的**审美真空**：

- AI 无专业设计训练，无法弥补人类自身设计词汇匮乏、目标模糊、风格缺位的短板
- 结果必然是千篇一律的「暗黑科技风/极简风套壳」，Hero 区 + 功能区+CTA 三件套，毫无品牌识别度

### 破局关键

必须同步启动 3 项基础能力建设：

- **编写描述性 Prompt**（而非指令式命令）：用设计语言描述需求，而非简单指令
- **指定技术栈**（Next.js/Astro/HTML 等并理解差异）：明确技术约束，避免 AI 生成不可用代码
- **建立设计基础语汇**（排版、间距、色彩情绪等）：用专业术语统一设计认知




---

### LEVEL 1: THE RAW PROMPTER
### 第一层：原始提示词使用者

> *"Just me and a prompt"*
> *"只有我和一个提示词"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- You open Claude Code and type "build me a landing page"
  - 你打开 Claude Code 并输入「给我做个着陆页」
  
- No frameworks, no design direction
  - 没有框架指定，没有设计方向
  
- You hope Claude just ... knows what looks good
  - 你希望 Claude 就是... 知道什么是好看的

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Writing descriptive prompts
  - 编写描述性提示词
  
- [ ] Specifying frameworks (Tailwind, React)
  - 指定技术框架（Tailwind、React）
  
- [ ] Basic design vocabulary
  - 基础设计词汇

---

#### TRAP: The Template Trap
#### 陷阱：模板陷阱

> No direction = average of training data.
> 没有方向 = 训练数据的平均水平

> Every site looks the same. Generic Tailwind + shadcn = "I obviously used AI."
> 每个网站看起来都一样。通用的 Tailwind + shadcn = 「我明显用了 AI」

---

#### UNLOCK > Level 2:
#### 解锁 > 第二层：

> You realize Claude needs design intelligence, not just instructions.
> 你意识到 Claude 需要设计智能，而不仅仅是指令。

---

### 📌 与笔记内容对应

这张图片对应你笔记中 **L1：纯文本提示陷阱** 章节，核心观点一致：

| 图片内容 | 笔记对应内容 |
|---------|-------------|
| 模板陷阱 | AI 模板地狱，千篇一律的暗黑科技风/极简风套壳 |
| 需要指定框架 | 指定技术栈（Next.js/Astro/HTML 等） |
| 需要设计词汇 | 建立设计基础语汇（排版、间距、色彩情绪等） |
| 解锁 L2 | 注入设计知识，用 UX Pro Max 给 AI 补课 |

这张卡片是对 L1 层级的精炼总结，可以作为笔记的补充视觉素材。

# 效果图-level_1

![](assets/claude-前端设计/file-20260414220958712.png)
### ✅ L1 专属 Prompt 模板

```markdown
# 角色
你是一名资深前端设计师，精通现代 Web 设计与开发，拥有 10 年以上商业产品前端设计经验。

# 任务
为虚拟产品「Argus（社交媒体情报平台）」设计并开发一个符合现代审美的着陆页。

# 技术栈要求
使用 Next.js 14 + TypeScript + Tailwind CSS v3 开发，代码必须可直接运行，无冗余依赖。

# 设计要求
1. 品牌调性：专业、科技感、可信赖，面向 B 端企业用户，避免过度娱乐化
2. 视觉风格：采用深蓝为主色调，辅以浅灰作为中性色，点缀青绿色作为强调色
3. 排版层次：建立清晰的字体层级，标题使用无衬线粗体，正文使用清晰易读的无衬线字体
4. 交互要求：所有按钮添加悬停反馈，滚动时添加平滑过渡动画
5. 布局结构：包含 Hero 区、核心功能区、客户案例区、CTA 区、页脚

# 输出要求
1. 先输出完整的设计方案（包含色彩系统、排版规范、布局逻辑）
2. 再输出完整的可运行代码，包含所有必要的组件与样式
3. 代码中添加详细注释，说明关键设计决策
```

---

## 🧱 L2：注入设计知识

### 核心动作

安装 GitHub 开源技能 **UX Pro Max**（5k+ stars），它是一套嵌入式设计核对清单文本提示，强制 Claude 规避 AI Slop Design 常见雷区：

- 滥用紫色渐变
- 忽略悬停反馈
- 忽视视觉层次
- 无意义的动效
- 不符合无障碍设计规范

## 📝 Level 2 文字提取

---

### LEVEL 2: THE SKILL STACKER
### 第二层：技能叠加者

> *"Give Claude a design education"*
> *"给 Claude 设计教育"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- You install frontend-design skill, UI/UX Pro Max
  - 你安装了前端设计技能，UI/UX Pro Max
- Claude starts understanding color theory, typography, spacing, layout
  - Claude 开始理解色彩理论、排版、间距、布局
- Output jumps from "template" to "designed"
  - 输出从「模板」跃升到「设计感」

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Choosing the right skill for the job
  - 为任务选择合适的技能
- [ ] Understanding what design skills change
  - 理解设计技能会改变什么
- [ ] Evaluating output with a designer's eye
  - 用设计师的眼光评估输出

---

#### TRAP: The Description Ceiling
#### 陷阱：描述天花板

> Skills improve output but you still can't SHOW Claude what you mean.
> 技能改善了输出，但你仍然无法向 Claude **展示** 你的意思。

> Text descriptions hit a wall fast.
> 文本描述很快遇到瓶颈。

---

#### UNLOCK > Level 3:
#### 解锁 > 第三层：

> What if Claude could SEE what you want?
> 如果 Claude 能 **看见** 你想要的东西会怎样？

---


### 效果对比

启用后生成的 Argus 着陆页出现实质性进化：

- 背景质感提升，层次分明
- 按钮带微光泽与悬停变色，交互反馈清晰
- 模块配色分区明确，品牌识别度提升
- 加入真实图片占位，避免 AI 生成的虚假内容

# 效果图
![](assets/claude-前端设计/file-20260414220958709.png)

### ✅ L2 专属 Prompt 模板

```markdown
# 角色
你是一名资深 UX/UI 设计师，严格遵循 UX Pro Max 设计规范。

# UX Pro Max 设计核对清单
1. 色彩系统：主色调不超过 3 种，强调色不超过 1 种，对比度符合 WCAG 2.1 AA 标准（≥4.5:1）
2. 排版系统：建立清晰的字体层级，字体数量不超过 3 种，行高符合可读性要求（正文 1.5-1.6）
3. 交互规范：所有可交互元素必须有明确的悬停/点击反馈，无死区
4. 视觉层次：通过字体大小、字重、颜色、间距建立清晰的信息层级
5. 动效规范：所有动效必须服务于用户体验，动效时长控制在 200-300ms
6. 无障碍设计：支持键盘导航，屏幕阅读器可识别
7. 品牌一致性：所有设计元素必须符合品牌调性，避免 AI 通用模板

# 任务
基于上述规范，优化 Argus 社交媒体情报平台的着陆页设计。

# 输出要求
1. 先输出优化后的设计规范（色彩、排版、交互、动效）
2. 再输出完整的优化后代码
3. 标注每个优化点对应的 UX Pro Max 核对清单项
```

---

## 🧱 L3：视觉总监模式

### 范式转移

放弃「请做一个简洁现代的着陆页」这类失效文本，转而提供**高质量视觉参考图**：

- 来源：Awwwards/Dribbble/Pinterest/Behance/Open Hands 等顶级设计网站
- 示例：截取 Open Hands 网站的滚动 Proven Workflows 区域 + 独特配色 + 社会认同模块

### 双重收益

- Claude 图像理解能力远超文本描述，生成匹配度指数级飙升
- 人类设计师通过高频浏览优质案例，自动内化设计标准


## 📝 Level 3 文字提取

---

### LEVEL 3: THE VISUAL DIRECTOR
### 第三层：视觉总监

> *"Show, don't tell"*
> *"展示，而非讲述"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- You screenshot sites you like and paste them into the conversation
  - 你截取喜欢的网站截图并粘贴到对话中
- "Make it look like this" is your go-to prompt
  - 「做成像这个一样」是你的常用提示词
- Claude reverse-engineers the vibe
  - Claude 逆向工程这种氛围/感觉

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Curating good visual references
  - 策划优质的视觉参考
- [ ] Communicating what specifically you like
  - 沟通你具体喜欢什么
- [ ] Combining references from multiple sites
  - 结合多个网站的参考

---

#### TRAP: The Vibe Gap
#### 陷阱：氛围差距

> Screenshots capture the look, not the code.
> 截图捕捉的是外观，而不是代码。

> Claude interprets, doesn't replicate.
> Claude 是解读，而不是复制。

> Close - but never exact.
> 接近——但从不精确。

---

#### UNLOCK > Level 4:
#### 解锁 > 第四层：

> What if you could grab the actual components, not just screenshots?
> 如果你能获取实际的组件，而不仅仅是截图，会怎样？

---

### 📌 与笔记内容对应

这张卡片对应你笔记中 **L3：视觉总监模式** 章节，核心观点完全一致：

| 图片内容 | 笔记对应内容 |
|---------|-------------|
| Show, don't tell | 用参考图代替形容词 |
| Screenshot sites you like | 让 AI 精准理解需求（视觉输入） |
| Trap: The Vibe Gap | 截图只能捕捉外观，无法获取代码逻辑 |
| Unlock Level 4 | 解构优秀网站的 HTML/CSS/JS（L4 代码克隆者） |

这张卡片揭示了 L3 的核心价值（视觉参考）及其局限性（无法获取代码），为 L4 的代码级克隆做了完美铺垫。

# 效果图
![](assets/claude-前端设计/file-20260414220958702.png)

### ✅ L3 专属 Prompt 模板

```markdown
# 角色
你是一名资深前端设计师，能够精准还原参考图的视觉风格与交互逻辑。

# 参考图
[在此处粘贴参考图截图/上传参考图]
参考图来源：Awwwards 获奖作品「Open Hands」

# 任务
基于参考图的视觉风格、布局逻辑、交互设计，为 Argus 设计着陆页。

# 设计要求
1. 严格还原参考图的视觉风格：滚动动画、卡片设计、配色逻辑、排版层次
2. 适配 Argus 的品牌调性：将参考图的主色调替换为 Argus 的深蓝主色调
3. 保留参考图的交互逻辑：滚动时的卡片动画、悬停效果、平滑过渡
4. 符合 UX Pro Max 设计规范

# 输出要求
1. 先输出设计方案，说明如何将参考图风格与 Argus 品牌结合
2. 再输出完整的可运行代码
3. 标注每个设计点对应的参考图区域
```

---

## 🧱 L4：代码克隆者

### 深度解构法

不满足于截图，而是用 `Ctrl+U` 获取目标网站完整 HTML，定位底部 CSS/JS 引用链接：

- 配合自研 Skill（如 Site-to-Own）绕过 WebFetch 摘要限制
- 直取原始样式与交互逻辑全量代码

### 学习闭环

Claude 基于真实代码反向教学：

- 「这个背景是怎么实现？」
- 「滚动动画用的 Intersection Observer 还是 GSAP？」
- 边克隆边积累可复用的技术组件库


## 📝 Level 4 文字提取

---

### LEVEL 4: THE CLONER
### 第四层：克隆者

> *"Learn by stealing from the pros"*
> *"通过向专业人士'偷师'来学习"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- You use site-teardown to break down entire websites - HTML, CSS, JS
  - 你使用网站拆解工具来分解整个网站——HTML、CSS、JS
- Through cloning you discover GSAP, parallax, scroll animations
  - 通过克隆你发现了 GSAP、视差滚动、滚动动画
- You bring pro techniques into your builds
  - 你将专业技术带入你的构建中

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Reading and understanding source code
  - 阅读和理解源代码
- [ ] Identifying which techniques = effects
  - 识别哪些技术对应哪些效果
- [ ] Adapting cloned patterns to your designs
  - 将克隆的模式适配到你的设计中

---

#### TRAP: The Clone Ceiling
#### 陷阱：克隆天花板

> You can copy but can't create. Without understanding WHY designs work, you're limited to what already exists.
> 你会复制但不会创造。如果不理解设计**为什么**有效，你就局限于已有的东西。

---

#### UNLOCK > Level 5:
#### 解锁 > 第五层：

> What if you could curate specific pro components to put your own spin on it?
> 如果你能策划特定的专业组件并加入你自己的风格，会怎样？

---

### 📌 与笔记内容对应

这张卡片对应你笔记中 **L4：代码克隆者** 章节，核心观点完全一致：

| 图片内容 | 笔记对应内容 |
|---------|-------------|
| site-teardown 分解网站 | 解构优秀网站的 HTML/CSS/JS |
| 发现 GSAP、视差、滚动动画 | 积累可复用组件 |
| Trap: Clone Ceiling | 只复制不理解原理，无法原创 |
| Unlock Level 5 | 原创融合者，组件市场+AI 绘图打造专属视觉资产 |

这张卡片点明了 L4 的核心价值（代码级学习）及其局限性（会抄不会创），为 L5 的原创融合做了逻辑铺垫。

# 效果图
![](assets/claude-前端设计/file-20260414220958701.png)

### ✅ L4 专属 Prompt 模板

```markdown
# 角色
你是一名资深前端逆向工程师，精通 HTML/CSS/JS/Next.js。

# 目标网站
[在此处粘贴目标网站的完整 HTML 代码/网站 URL]

# 任务
1. 解构目标网站的核心模块：HTML 结构、CSS 样式、JS 交互逻辑
2. 提取可复用的组件代码，包括滚动动画、卡片设计、悬停效果
3. 将提取的组件迁移到 Argus 项目中，适配品牌调性与技术栈

# 要求
1. 完整还原目标网站的交互逻辑
2. 适配 Argus 的品牌色彩系统
3. 代码必须可直接运行，添加详细注释
4. 说明每个组件的实现原理

# 输出要求
1. 先输出代码解构报告，说明核心组件的实现原理
2. 再输出完整的迁移后代码
3. 标注每个代码块对应的目标网站区域
```

---

## 🧱 L5：原创融合者

### 双轨定制策略

| 策略 | 内容 | 工具 |
|------|------|------|
| 微组件植入 | 从 21stdev/Copenco 等平台选取高质量组件 | 21stdev、Copenco |
| 视觉资产原创 | 用 Midjourney 生成契合产品内核的 AI 艺术图 | Midjourney、Runway/Veo |

### 关键升级

设计重心从「复制结构」转向「注入灵魂」：

- 标语、视觉隐喻（万眼巨人 Argus→预见未来）
- 动态节奏（加载延迟、文字扫光、滚动计数器）
- 共同构成无法被模板化的个性表达


## 📝 Level 5 文字提取

---

### LEVEL 5: THE COMPONENT SNIPER
### 第五层：组件狙击手

> *"You don't design - you curate"*
> *"你不设计——你策划"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- You browse 21st.dev and CodePen
  - 你浏览 21st.dev 和 CodePen
- You grab specific navbars, heroes, cards, forms - real code
  - 你获取特定的导航栏、Hero 区、卡片、表单——真实的代码
- "Integrate this" - hand Claude production components
  - 「整合这个」——交给 Claude 生产级组件

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Finding quality components (21st.dev)
  - 寻找优质组件（21st.dev）
- [ ] Evaluating code before integrating
  - 整合前评估代码
- [ ] Knowing what to swap vs. build
  - 知道什么该替换 vs. 什么该自己构建

---

#### TRAP: Frankenstein Sites
#### 陷阱：弗兰肯斯坦网站

> Mixing components from different design systems. Beautiful parts, ugly whole. Nothing feels cohesive.
> 混合来自不同设计系统的组件。部分很美，整体很丑。没有任何 cohesive（连贯性/整体感）。

---

#### UNLOCK > Level 6:
#### 解锁 > 第六层：

> You've curated the best - now it's time to design your own from scratch.
> 你已经策划了最好的——现在是从零开始设计你自己的东西的时候了。

---

### 📌 与笔记内容对应

这张卡片对应你笔记中 **L5：原创融合者** 章节，核心观点完全一致：

| 图片内容 | 笔记对应内容 |
|---------|-------------|
| 浏览 21st.dev 和 CodePen | 组件市场+AI 绘图 |
| 获取真实代码组件 | 打造专属品牌视觉资产 |
| Trap: Frankenstein Sites | 组件风格不统一，缺乏整体 cohesive |
| Unlock Level 6 | 可视化协作者，打通设计工具实现「所见即所得」 |

这张卡片点明了 L5 的核心方法论（策划而非设计）及其风险（风格割裂的弗兰肯斯坦网站），为 L6 的自主设计做了逻辑铺垫。

# 效果图
![](assets/claude-前端设计/file-20260414220958699.png)

### ✅ L5 专属 Prompt 模板

```markdown
# 角色
你是一名资深前端设计师与创意总监。

# 组件来源
1. 21stdev 高质量组件库：Button、Card、Navigation 组件
2. Copenco 动画组件库：滚动动画、文字扫光、加载动画

# AI 视觉资产
1. Midjourney 生成的概念图
2. Runway 生成的动态背景视频

# 技术栈
Next.js 14 + TypeScript + Tailwind CSS v3 + Framer Motion

# 设计要求
1. 植入高质量组件，适配 Argus 的品牌调性
2. 集成 AI 生成的概念图作为 Hero 区主视觉
3. 加入玻璃拟态卡片、文字扫光、滚动计数器等原创交互元素
4. 强化品牌叙事：通过视觉隐喻传递产品价值
5. 拒绝 AI 通用模板，打造专属品牌视觉

# 输出要求
1. 先输出原创视觉系统方案
2. 再输出完整的可运行代码
3. 标注每个原创元素的设计意图与实现原理
```

---

## 🧱 L6：可视化协作者

### 工具链升级

跳出纯终端文本流，接入 AI 原生设计工具：

- **Stitch**（谷歌免费画布）
- **Figma**
- **Pencil.dev**

### 人机协作新范式

```
上传当前 Argus 截图 
  → 指令「保留顶部卷字，重制下半部分为玻璃拟态 + 动态边界」
  → 实时生成多版视觉方案
  → 复制图片回 Claude 提问「如何实现此玻璃效果？」
  → 获得可落地 CSS 代码
  → 再返工优化
```

**人类掌控创意决策，AI 负责技术实现与快速试错**

## 📝 Level 6 文字提取

---

### LEVEL 6: THE DESIGNER
### 第六层：设计师

> *"Stop coding blind"*
> *"停止盲目编码"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- You connect Paper.design, Stitch, or Figma to Claude Code via MCP
  - 你通过 MCP 将 Paper.design、Stitch 或 Figma 连接到 Claude Code
- Claude designs on a live canvas you can see and manipulate
  - Claude 在你可见且可操作的实时画布上进行设计
- Pixel-level refinement with real tools
  - 使用真实工具进行像素级精细化调整

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Paper.design MCP setup & workflow
  - Paper.design MCP 设置与工作流
- [ ] Bidirectional design (visual + code)
  - 双向设计（视觉 + 代码）
- [ ] Asset creation and management
  - 资产创建与管理

---

#### TRAP: Tool Paralysis
#### 陷阱：工具瘫痪

> Paper, Stitch, Figma, Pencil – too many options. Pick ONE and master it.
> Paper、Stitch、Figma、Pencil——太多选择了。选 **一个** 并精通它。

> The tool isn't the point.
> 工具不是重点。

---

#### UNLOCK > Level 7:
#### 解锁 > 第七层：

> You've mastered 2D. What about the third dimension?
> 你已经掌握了 2D。那第三维度呢？

---

### 📌 与笔记内容对应

这张卡片对应你笔记中 **L6：可视化协作者** 章节，核心观点完全一致：

| 图片内容 | 笔记对应内容 |
|---------|-------------|
| 连接 Paper.design/Stitch/Figma via MCP | 打通设计工具 |
| 实时画布可见可操作 | 实现「所见即所得」迭代 |
| 像素级精细化调整 | 可视化协作的核心价值 |
| Trap: Tool Paralysis | 工具选择过多，需专注精通一个 |
| Unlock Level 7: 3D | 用 3D/WebGL 拓展设计边界 |

这张卡片强调了 L6 的核心突破（可视化实时协作）及其风险（工具选择困难），为 L7 的 3D/前沿探索做了逻辑铺垫。
# 效果图
![](assets/claude-前端设计/file-20260414220958697.png)
>底下的动画

### ✅ L6 专属 Prompt 模板

```markdown
# 角色
你是一名资深前端工程师，精通 CSS/Next.js。

# 设计图
[在此处粘贴 Stitch/Figma 设计图截图]

# 技术栈
Next.js 14 + TypeScript + Tailwind CSS v3 + Framer Motion

# 任务
1. 精准还原设计图的视觉效果：玻璃拟态卡片、动态边界、布局结构
2. 实现玻璃拟态效果：backdrop-filter、透明度、阴影、渐变
3. 实现动态边界效果：滚动时的边界动画、悬停时的边界变色
4. 适配 Argus 的品牌调性与现有代码结构

# 输出要求
1. 先输出实现方案，说明技术原理
2. 再输出完整的可运行代码
3. 标注每个效果的 CSS 属性与实现细节
4. 提供迭代优化建议
```

---

## 🧱 L7：前沿探索者

### 理性认知边界

以 Awwwards 顶级作品为例，指出当前自定义 WebGL 着色器、游戏级 3D 交互仍属专业团队手工打造范畴：

- AI 尚无法端到端生成可靠、高性能、可维护的 3D 前端
- 本层意义在于**打开视野，锚定长期进化方向**

### 务实启示

真正的「第七层」不是技术炫技，而是：

- 能自主判断「何时该用 3D 增强叙事」
- 协调 AI 与人类工程师分工协作
- 主导从字体选择、动态节奏到加载心理暗示的全链路体验设计


##  Level 7 文字提取

---

### LEVEL 7: THE ARCHITECT
### 第七层：架构师

> *"The frontier"*
> *"前沿"*

---

#### YOU'RE HERE WHEN ...
#### 你处于这个阶段时...

- Three.js, custom WebGL, shaders
  - Three.js、自定义 WebGL、着色器
- Mouse-reactive, scroll-driven, immersive 3D experiences
  - 鼠标响应、滚动驱动、沉浸式 3D 体验
- You're building $15-50K agency-level sites (Igloo, Awwwards winners)
  - 你在构建价值 1.5-5 万美元的代理机构级别网站（Igloo、Awwwards 获奖作品）

---

#### SKILLS TO MASTER
#### 需要掌握的技能

- [ ] Three.js fundamentals
  - Three.js 基础
- [ ] Shader programming (GLSL)
  - 着色器编程（GLSL）
- [ ] Performance optimization (GPU, FPS)
  - 性能优化（GPU、帧率）

---

#### TRAP: The Performance Trap
#### 陷阱：性能陷阱

> Beautiful 3D at 12fps = worse than no 3D.
> 12 帧的精美 3D = 不如没有 3D。

> AI struggles here. This is where the human still matters most.
> AI 在这里很吃力。这是人类仍然最重要的地方。

---

#### THIS IS THE CEILING
#### 这就是天花板

> But it keeps rising. The best builders are always pushing it higher.
> 但它不断上升。最优秀的构建者总是在把它推得更高。

---

### 📌 与笔记内容对应

这张卡片对应你笔记中 **L7：前沿探索者** 章节，核心观点完全一致：

| 图片内容 | 笔记对应内容 |
|---------|-------------|
| Three.js、WebGL、shaders | 用 3D/WebGL 拓展设计边界 |
| 沉浸式 3D 体验 | 前沿设计技术探索 |
| $15-50K 代理机构级别网站 | 高端商业项目能力 |
| Trap: Performance Trap | AI 在性能优化上仍有局限，需要人类专业判断 |
| This is the Ceiling | 锚定长期进化方向，天花板不断上升 |

---

###  七层完整总结

| 层级 | 名称 | 核心突破 | 核心陷阱 |
|------|------|----------|----------|
| L1 | 原始提示词使用者 | 建立基础设计认知 | 模板陷阱 |
| L2 | 技能叠加者 | 注入设计知识 | 描述天花板 |
| L3 | 视觉总监 | 视觉参考代替文字 | 氛围差距 |
| L4 | 克隆者 | 代码级解构学习 | 克隆天花板 |
| L5 | 组件狙击手 | 策划优质组件 | 弗兰肯斯坦网站 |
| L6 | 设计师 | 可视化实时协作 | 工具瘫痪 |
| L7 | 架构师 | 3D/WebGL 前沿探索 | 性能陷阱 |

这张卡片是七重天的终极层级，强调了**人类专业价值的不可替代性**（性能优化、审美判断），同时指出这是一个持续进化的过程，没有真正的终点。
### ✅ L7 专属 Prompt 模板

```markdown
# 角色
你是一名资深前端 3D 工程师，精通 Three.js/React Three Fiber/WebGL。

# 任务
为 Argus 着陆页 Hero 区添加 3D 视觉效果，增强品牌叙事。

# 技术栈
Next.js 14 + TypeScript + Tailwind CSS v3 + React Three Fiber + Three.js

# 设计要求
1. 3D 效果必须服务于品牌叙事：围绕「万眼巨人 Argus→预见未来」
2. 保证性能：3D 场景帧率≥60fps，移动端适配
3. 交互友好：3D 元素支持鼠标交互，悬停时添加反馈
4. 代码可维护：模块化结构，详细注释

# 输出要求
1. 先输出 3D 场景设计方案
2. 再输出完整的可运行代码
3. 标注性能优化点与适配方案
4. 提供长期迭代建议
```

---

## 🛠️ 核心工具与资源清单

| 层级 | 核心工具/技能 | 核心作用 | 获取方式 |
|------|----------------|----------|----------|
| L2 | UX Pro Max | 设计核对清单，规避 AI 设计雷区 | GitHub 开源，免费 |
| L3 | Awwwards/Dribbble/Pinterest | 高质量视觉参考源 | 免费访问 |
| L4 | 浏览器开发者工具、Site-to-Own | 完整代码解构与克隆 | 浏览器自带 |
| L5 | 21stdev/Copenco、Midjourney | 组件市场+AI 视觉资产 | 部分付费 |
| L6 | Stitch、Figma、Pencil.dev | 可视化协作，所见即所得 | 部分免费 |
| L7 | Three.js/React Three Fiber | 3D 前端开发 | 开源免费 |

---

## 🎯 核心方法论总结

- **拒绝「一键生成」**：Claude 是可被精准引导的执行者，而非一次性生成器，**设计主权永远在人类手中**
- **分层递进**：从提示词优化→知识注入→视觉参考→代码解构→原创融合→工具协同→前沿探索，每一层都为下一层打基础
- **实战驱动**：以真实产品 Argus 为载体，所有方法均为可复现、可迁移的工程化路径
- **人机协作**：人类负责创意决策、设计方向，AI 负责技术实现、快速试错

---

## 📸 图片插入说明

你可以使用系统截图工具截取原长图中每个层级的视频截图：

| 平台 | 截图方式 | 插入方法 |
|------|----------|----------|
| Obsidian | Windows: `Win+Shift+S` / Mac: `Cmd+Shift+4` | 保存到附件文件夹，用 `![[图片文件名]]` 插入 |
| Notion | 同上 | 直接粘贴截图到对应位置，自动上传 |

---

## 🏷️ 相关标签

#AI 前端开发 #ClaudeCode #前端设计 #设计系统 #AI 协作 #前端工程化 #Next.js #TailwindCSS

---

> 💡 **提示**：本笔记为可复现、可迁移的工程化路径，建议按层级逐步实践，不可跳过。