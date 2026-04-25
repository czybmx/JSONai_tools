# jsonAI 🧩

**自然语言 → 结构化 JSON 构建助手**

用你的日常语言描述任何事物，jsonAI 会持续将它整理、归类、融合成结构化的 JSON 对象——完全在本地运行，无需网络，无需 API Key。

---

## ✨ 功能特性

- **自然语言驱动**：直接说中文（或其他语言），AI 自动将内容转换并累积进 JSON
- **滚动上下文压缩**：Jeanne 同款架构，超出窗口自动摘要，长对话不丢失语义
- **持久记忆**：每次会话自动快照，退出后写入 `~/.jsonai/memory.json`，历史 JSON 随时调取
- **本地 Ollama 驱动**：支持任意 Ollama 模型（推荐 `qwen3:4b`、`gemma` 等 instruction 模型）
- **Rich 终端 UI**：彩色面板、语法高亮、Monokai 主题，命令行也可以很好看
- **依赖自动安装**：首次运行自动 `pip install rich prompt_toolkit`

---

## 🚀 快速开始

### 前置条件

- Python 3.10+
- [Ollama](https://ollama.com/) 已安装并运行

```bash
# 拉取推荐模型（任选其一）
ollama pull qwen3:4b
ollama pull gemma3:4b
```

### 安装 & 运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/jsonAI.git
cd jsonAI

# 直接运行（依赖会自动安装）
python jsonAI.py

# 指定模型 & Ollama 地址
python jsonAI.py --model qwen3:4b --url http://localhost:11434

# 调整 temperature
python jsonAI.py --temp 0.1
```

### 环境变量（可选）

```bash
export JSONAI_MODEL=qwen3:4b
export OLLAMA_URL=http://localhost:11434
```

---

## 💬 使用示例

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

---

## 🛠 内置命令

| 命令 | 说明 |
|------|------|
| `/show` | 显示当前 JSON |
| `/reset` | 清空 JSON & 重置上下文 |
| `/save [文件名]` | 保存 JSON 到文件 |
| `/load <文件名>` | 从 JSON 文件加载状态 |
| `/history [N]` | 查看最近 N 条历史 JSON（默认 3）|
| `/sessions` | 查看最近 10 次会话记录 |
| `/model [名称]` | 查看或切换 Ollama 模型 |
| `/models` | 列出本地可用模型 |
| `/ctx` | 显示上下文压缩状态 |
| `/export` | 导出 JSON 到剪贴板 |
| `/help` | 显示帮助面板 |
| `/quit` | 退出并保存会话记忆 |

---

## 🗂 数据存储

```
~/.jsonai/
├── memory.json          # 全局记忆（会话列表 + JSON 历史）
└── sessions/
    └── <session_id>.json   # 每次会话快照（自动保存）
```

---

## ⚙️ 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model` | `Gemma-4-E4B-Uncensored-Q8_K_P:latest` | Ollama 模型名称 |
| `--url` | `http://localhost:11434` | Ollama 服务地址 |
| `--temp` | `0.25` | Temperature（越低越稳定）|

---

## 📦 依赖

```
rich
prompt_toolkit
requests   # Python 标准库通常已含
```

---

## 📄 License

MIT © 2025
