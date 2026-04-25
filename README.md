# jsonAI 🧩

**自然语言 → 结构化 JSON 构建助手**
**Natural Language → Structured JSON Builder**

> 用日常语言描述任何事物，jsonAI 持续将它整理、归类、融合成结构化 JSON——完全本地运行，无需网络，无需 API Key。
>
> Describe anything in plain language. jsonAI continuously organises, categorises, and merges your input into structured JSON — fully local, no internet, no API key required.

---

## ✨ 功能特性 / Features

| | 中文 | English |
|---|---|---|
| 🗣️ | 自然语言驱动，直接说中文（或其他语言） | Natural language input in any language |
| 🔄 | 每轮自动融合上一次 JSON，持续累积 | Incrementally merges each turn into the existing JSON |
| 🧠 | 滚动上下文压缩，长对话不丢语义 | Rolling context compression — long sessions stay coherent |
| 💾 | 会话自动快照 + 持久记忆，历史 JSON 随时调取 | Auto-snapshot per session + persistent memory across runs |
| 🤖 | 本地 Ollama 驱动，支持任意 instruction 模型 | Powered by local Ollama, works with any instruction model |
| 🎨 | Rich 终端 UI，彩色面板 + Monokai 语法高亮 | Rich terminal UI with coloured panels and Monokai highlighting |
| 📦 | 首次运行自动安装依赖 | Auto-installs `rich` and `prompt_toolkit` on first run |

---

## 🚀 快速开始 / Quick Start

### 前置条件 / Prerequisites

- Python **3.10+**
- [Ollama](https://ollama.com/) installed and running

```bash
# 拉取推荐模型（任选其一）/ Pull a recommended model (pick one)
ollama pull qwen3:4b
ollama pull gemma3:4b
```

### 安装 & 运行 / Install & Run

```bash
# 克隆仓库 / Clone the repo
git clone https://github.com/YOUR_USERNAME/jsonAI.git
cd jsonAI

# 直接运行，依赖自动安装 / Run directly — deps auto-install
python jsonAI.py

# 指定模型与服务地址 / Specify model and Ollama URL
python jsonAI.py --model qwen3:4b --url http://localhost:11434

# 调整 temperature / Adjust temperature
python jsonAI.py --temp 0.1
```

### 环境变量 / Environment Variables（可选 / optional）

```bash
export JSONAI_MODEL=qwen3:4b
export OLLAMA_URL=http://localhost:11434
```

---

## 💬 使用示例 / Example

```
[1] ❯ 我要买的东西：苹果、牛奶、面包，还有洗发水
```

```json
{
  "购物清单": {
    "食品": ["苹果", "牛奶", "面包"],
    "日用品": ["洗发水"]
  }
}
```

```
[2] ❯ 再加上鸡蛋，面包改成全麦面包
```

```json
{
  "购物清单": {
    "食品": ["苹果", "牛奶", "全麦面包", "鸡蛋"],
    "日用品": ["洗发水"]
  }
}
```

每一轮输入都会**融合**上一次的 JSON，而不是重写。  
Each turn **merges** into the previous JSON rather than overwriting it.

---

## 🛠 内置命令 / Built-in Commands

| 命令 / Command | 说明 / Description |
|---|---|
| `/show` | 显示当前 JSON / Show current JSON |
| `/reset` | 清空 JSON & 重置上下文 / Clear JSON & reset context |
| `/save [文件名]` | 保存 JSON 到文件 / Save JSON to file |
| `/load <文件名>` | 从文件加载 JSON / Load JSON from file |
| `/history [N]` | 最近 N 条历史 JSON（默认 3）/ Last N JSON snapshots (default 3) |
| `/sessions` | 最近 10 次会话记录 / Last 10 session records |
| `/model [名称]` | 查看或切换模型 / View or switch model |
| `/models` | 列出本地可用模型 / List available local models |
| `/ctx` | 上下文压缩状态 / Context compression stats |
| `/export` | 导出 JSON 到剪贴板 / Copy JSON to clipboard |
| `/help` | 显示帮助面板 / Show help panel |
| `/quit` | 退出并保存记忆 / Exit and save session memory |

---

## 🗂 数据存储 / Data Storage

```
~/.jsonai/
├── memory.json             # 全局记忆 / Global memory (sessions + JSON history)
└── sessions/
    └── <session_id>.json   # 会话快照（自动） / Per-session snapshot (auto-saved)
```

---

## ⚙️ 参数说明 / CLI Arguments

| 参数 / Arg | 默认值 / Default | 说明 / Description |
|---|---|---|
| `--model` | `Gemma-4-E4B-Uncensored-Q8_K_P:latest` | Ollama 模型名称 / Ollama model name |
| `--url` | `http://localhost:11434` | Ollama 服务地址 / Ollama endpoint |
| `--temp` | `0.25` | Temperature（越低越稳定 / lower = more deterministic）|

---

## 📦 依赖 / Dependencies

```
rich
prompt_toolkit
requests
```

> 首次运行时若缺失会自动安装。  
> Missing packages are installed automatically on first run.

---

## 📄 License

MIT © 2025
