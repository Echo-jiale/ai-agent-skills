# AI Agent Skills

我自己写的 AI Agent Skills 合集，主要用于 Claude Code / Codex 等支持 Skill 机制的 Agent。

每个 skill 一个独立文件夹，文件夹内自带 `SKILL.md`（Agent 读取的说明）和所需的脚本、资源。

## Skill 列表

### 1. [xmind-mindmap](xmind-mindmap/) — 思维导图生成器

把一段文字、一个文件或一个主题，提炼成结构化大纲，再生成可直接用 XMind 打开的 `.xmind` 文件。

- **两步走**：先生成文字大纲给你核对，确认后才生成 `.xmind`，避免内容没定就白做
- **纯 Python 标准库**实现，不联网、不装第三方库
- 自动配色，一级分支自动带图标，中文不乱码
- 支持 4 种输入：粘贴文字 / 读取本地文件 / 给个主题 / markdown 转换

详见 [xmind-mindmap/SKILL.md](xmind-mindmap/SKILL.md)

## 安装

把想要的 skill 文件夹整个复制到你的 skills 目录。

**装到某个项目里**（只在该项目可用）：

```
<你的项目>/.claude/skills/
```

**装到用户级目录**（所有项目都能用）：

```
~/.claude/skills/
```

例如装 `xmind-mindmap`：

```bash
git clone https://github.com/Echo-jiale/ai-agent-skills.git
cp -r ai-agent-skills/xmind-mindmap ~/.claude/skills/
```

装好后在 Agent 里直接说需求即可，比如「帮我把这篇文章整理成思维导图」。

## 环境要求

各 skill 的要求不同，见各自文件夹内的说明。目前：

| Skill | 要求 |
|---|---|
| xmind-mindmap | Python 3（无第三方依赖） |

## 说明

仓库里的 skill 都是我自己写的，还在持续补充中。

## License

MIT
