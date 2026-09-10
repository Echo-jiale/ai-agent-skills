# xmind-mindmap

一个 Claude Code / Codex **Skill**：把一段文字、一个文件或一个主题，提炼成结构化大纲，再生成可直接用 XMind 打开的 `.xmind` 文件。

## 它解决什么

让 Agent 帮你做思维导图，最麻烦的是**内容还没定就先生成文件，改一次重做一次**。这个 skill 把流程拆成两步：

1. 先把内容提炼成 Markdown 大纲 → **交给你核对**
2. 你确认无误后，才生成 `.xmind`

生成环节用纯 Python 标准库手写新版 XMind 格式，**不联网、不装第三方库**，也不需要装 XMind SDK 或 npm 包。

## 效果

- 自动配色：一级分支依次用调色板上色
- 一级分支自动带 priority 图标
- 中文不乱码
- 兼容 XMind 2020+ 的新版文件格式

## 安装

把整个文件夹放进你的 skills 目录：

```
<你的项目>/.claude/skills/xmind-mindmap/
```

或在用户级目录安装，让所有项目都能用：

```
~/.claude/skills/xmind-mindmap/
```

## 用法

在 Agent 里直接说需求即可，例如：

```
帮我把这篇文章整理成思维导图
```

```
做个「工业AI入门」的思维导图
```

支持 4 种输入方式：

| 方式 | 你给什么 |
|------|----------|
| 粘贴文字 | 直接贴一段文字 / 文章 / 笔记 |
| 读取文件 | 给一个 Word / PDF / txt / md 路径 |
| 给个主题 | 只给主题，Agent 组织内容 |
| markdown 转换 | 给已导出的 md 大纲，直接转（不改内容） |

## 直接调用生成器

不想通过 Agent，也可以自己喂 JSON：

```bash
python scripts/gen_xmind.py --root "中心主题" --tree tree.json --out 导图.xmind
```

`tree.json` 结构：

```json
{
  "title": "中心主题",
  "children": [
    {"title": "分支1", "children": [{"title": "叶子1"}, {"title": "叶子2"}]},
    {"title": "分支2", "children": [{"title": "叶子1"}]}
  ]
}
```

参数：

| 参数 | 说明 |
|------|------|
| `--root` | 中心主题名（必填） |
| `--tree` | 大纲 JSON 路径（可选，省略则用内置示例） |
| `--out` | 输出 `.xmind` 路径（必填） |
| `--no-icons` | 不加一级分支自动图标 |

环境要求：**Python 3**，无第三方依赖。

## 关于路径

`SKILL.md` 里的 `{SKILL_DIR}`（skill 所在目录）和 `{OUTPUT_DIR}`（导图输出目录）是示例值，按你自己的环境改一下即可。

## 技术原理

新版 XMind 的 `.xmind` 其实就是一个 zip 包，内含：

| 文件 | 作用 | 关键点 |
|------|------|--------|
| `content.json` | 真正的导图数据 | sheet → rootTopic → children.attached |
| `metadata.json` | 版本信息 | `creator=Vana`、`dataStructureVersion=3` |
| `manifest.json` | 文件清单 | **不能把 manifest.json 自己列进去** |
| `content.xml` | 旧版占位符 | XMind 实际读的是 JSON |
| `Thumbnails/thumbnail.png` | 缩略图 | 占位图即可，保存后 XMind 覆盖成真图 |

**踩过的坑**（都已在脚本里规避）：

- `manifest.json` 把自己列进 `file-entries` → XMind 报「文档损坏」
- 缺 `content.xml` 或缩略图 → 报损坏 / 缩略图黑屏
- 中文没用 `ensure_ascii=False` 写入 → 乱码

## 已知提示

刚生成的导图在 XMind「最近」列表里显示的是浅灰占位图。打开文件后 **Ctrl+S 保存一次**，XMind 会自动生成真实缩略图封面。
