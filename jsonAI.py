#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import sys
import time
import uuid
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 依赖自动安装 ────────────────────────────────────────────
def _ensure(pkg: str, import_name: str = None):
    name = import_name or pkg
    try:
        __import__(name)
    except ImportError:
        print(f"[安装依赖] pip install {pkg} ...")
        os.system(f'"{sys.executable}" -m pip install {pkg} -q')

_ensure("rich")
_ensure("prompt_toolkit", "prompt_toolkit")

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.table import Table
from rich import box
from rich.rule import Rule
from rich.columns import Columns
from rich.padding import Padding
from rich.align import Align
from prompt_toolkit import prompt as ptk_prompt
from prompt_toolkit.styles import Style as PtkStyle
from prompt_toolkit.history import InMemoryHistory

console = Console(highlight=False)

# ═══════════════════════════════════════════════════════════
#  路径 & 全局配置
# ═══════════════════════════════════════════════════════════
MEMORY_DIR   = Path.home() / ".jsonai"
SESSIONS_DIR = MEMORY_DIR / "sessions"
MEMORY_FILE  = MEMORY_DIR / "memory.json"
MEMORY_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

DEFAULT_CFG = {
    "model"           : "Gemma-4-E4B-Uncensored-Q8_K_P:latest",
    "ollama_url"      : "http://localhost:11434",
    "temperature"     : 0.25,
    "max_ctx_msgs"    : 20,     # 超过此数触发滚动压缩
    "keep_recent"     : 6,      # 压缩后保留最近 N 条
}

# ── 系统提示词 ──────────────────────────────────────────────
SYSTEM_TPL = """\
你是专门排列json格式的AI，并且持续不断的记录用户说的【事情，或是吩咐的事物，亦或是其他想法】变成需要使用的格式。

每一次的回答都是以json格式显现。

规则：
1. 只输出纯JSON
2. 必须确保用户的【意思】固定。
3. 如用户的输入与JSON无关（如闲聊），也请完全记录
4. 若【某某】为【同类】，请合理归类在【一起】
5. 支持将用户的【意思】以另一种形式记录
6. 必须将【上一次的json】进行【融合】，然后在【这一次】写出来【更新版本】的json
7. 禁止闲聊或问答。

当前JSON状态：
{current_json}
"""

class ContextManager:
    def __init__(self, max_messages: int = 20, keep_recent: int = 6):
        self.messages:    list[dict] = []
        self.summary:     str        = ""
        self.max_messages             = max_messages
        self.keep_recent              = keep_recent
        self.total_added: int        = 0

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.total_added += 1
        if len(self.messages) > self.max_messages:
            self._compress()

    def _compress(self):
        to_compress        = self.messages[: -self.keep_recent]
        self.messages      = self.messages[-self.keep_recent :]
        lines = []
        for m in to_compress:
            snippet = m["content"][:150].replace("\n", " ")
            lines.append(f"[{m['role']}] {snippet}")
        block = "\n".join(lines)
        if self.summary:
            self.summary += f"\n{block}"
        else:
            self.summary = f"【早期对话摘要（已压缩）】\n{block}"

    def build_messages(self, system_prompt: str) -> list[dict]:
        sys_content = system_prompt
        if self.summary:
            sys_content += f"\n\n{self.summary}"
        return [{"role": "system", "content": sys_content}, *self.messages]

    def to_dict(self) -> dict:
        return {
            "messages":     self.messages,
            "summary":      self.summary,
            "total_added":  self.total_added,
        }

    @classmethod
    def from_dict(cls, data: dict, max_messages: int = 20, keep_recent: int = 6) -> "ContextManager":
        obj              = cls(max_messages, keep_recent)
        obj.messages     = data.get("messages", [])
        obj.summary      = data.get("summary", "")
        obj.total_added  = data.get("total_added", len(obj.messages))
        return obj


class MemoryManager:
    def __init__(self):
        self.data = self._load()

    # ── 加载全局记忆文件 ──────────────────────────────
    def _load(self) -> dict:
        if MEMORY_FILE.exists():
            try:
                return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"sessions": [], "json_history": [], "facts": []}

    def _save(self):
        MEMORY_FILE.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 会话快照（随时覆写，防丢失） ──────────────────
    def save_snapshot(self, sid: str, ctx: ContextManager, cur_json: dict):
        path = SESSIONS_DIR / f"{sid}.json"
        path.write_text(
            json.dumps(
                {
                    "context":      ctx.to_dict(),
                    "current_json": cur_json,
                    "timestamp":    datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_snapshot(self, sid: str) -> Optional[dict]:
        path = SESSIONS_DIR / f"{sid}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    # ── 会话结束时写入全局记忆 ────────────────────────
    def record_session(self, sid: str, ctx: ContextManager, final_json: dict):
        entry = {
            "id":        sid,
            "timestamp": datetime.now().isoformat(),
            "msg_count": ctx.total_added,
            "final_json": final_json,
        }
        self.data["sessions"].append(entry)
        self.data["sessions"] = self.data["sessions"][-100:]
        if final_json:
            self.data["json_history"].append(
                {"timestamp": datetime.now().isoformat(), "json": final_json}
            )
            self.data["json_history"] = self.data["json_history"][-200:]
        self._save()

    def get_recent_jsons(self, n: int = 5) -> list:
        return self.data["json_history"][-n:]

    def list_sessions(self, n: int = 10) -> list:
        return self.data["sessions"][-n:]


# ═══════════════════════════════════════════════════════════
#  OllamaClient
# ═══════════════════════════════════════════════════════════
class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model    = model

    def chat_stream(self, messages: list[dict], temperature: float = 0.25):
        """生成器：每次 yield (token_str, is_done)"""
        url     = f"{self.base_url}/api/chat"
        payload = {
            "model":   self.model,
            "messages": messages,
            "stream":   True,
            "options": {"temperature": temperature},
        }
        with requests.post(url, json=payload, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if raw_line:
                    chunk = json.loads(raw_line)
                    token = chunk.get("message", {}).get("content", "")
                    done  = chunk.get("done", False)
                    yield token, done

    def check(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════
#  UI 工具函数（多彩 CMD 风格）
# ═══════════════════════════════════════════════════════════

# 调色板
C = {
    "cyan"    : "bright_cyan",
    "mag"     : "bright_magenta",
    "yellow"  : "bright_yellow",
    "green"   : "bright_green",
    "red"     : "bright_red",
    "blue"    : "bright_blue",
    "white"   : "bright_white",
    "dim"     : "grey54",
    "dimmer"  : "grey35",
}

def banner():
    console.print()
    console.print(Rule(style=C["cyan"]))
    lines = [
        Text.assemble(
            ("   ┌─────────────────────────────────────────┐", C["dimmer"])
        ),
        Text.assemble(
            ("   │  ", C["dimmer"]),
            (" J ", C["yellow"] + " bold"),
            ("S", C["cyan"] + " bold"),
            ("O", C["mag"] + " bold"),
            ("N", C["green"] + " bold"),
            ("AI  ", C["yellow"] + " bold"),
            ("─  自然语言  →  结构化 JSON  ", C["dim"]),
            ("│", C["dimmer"]),
        ),
        Text.assemble(
            ("   │  ", C["dimmer"]),
            ("Ollama本地模型 ", C["dim"]),
            ("  │", C["dimmer"]),
        ),
        Text.assemble(
            ("   └─────────────────────────────────────────┘", C["dimmer"])
        ),
    ]
    for line in lines:
        console.print(line)
    console.print(Rule(style=C["cyan"]))
    console.print()


def print_json_panel(j: dict, title: str = "当前 JSON", border: str = "bright_yellow"):
    if not j:
        console.print(Panel(
            Align.center(Text("（空对象）", style=C["dim"])),
            title=f"[{border} bold]{title}[/]",
            border_style=border,
            padding=(0, 2),
        ))
        return
    pretty = json.dumps(j, ensure_ascii=False, indent=2)
    syntax = Syntax(pretty, "json", theme="monokai", word_wrap=True, line_numbers=False)
    console.print(Panel(syntax, title=f"[{border} bold]{title}[/]", border_style=border, padding=(0, 1)))


def ok(msg: str):
    console.print(f"  [bright_green]✔[/]  [bright_green]{msg}[/]")


def err(msg: str):
    console.print(f"  [bright_red]✘[/]  [bright_red]{msg}[/]")


def info(msg: str):
    console.print(f"  [bright_cyan]◈[/]  [grey85]{msg}[/]")


def hint(msg: str):
    console.print(f"  [grey42]·[/]  [grey54]{msg}[/]")


def help_panel():
    t = Table(
        box=box.ROUNDED,
        border_style=C["mag"],
        show_header=True,
        header_style=C["mag"] + " bold",
        padding=(0, 1),
    )
    t.add_column("命令", style=C["cyan"], min_width=22)
    t.add_column("说明", style="grey85")
    cmds = [
        ("/show",           "显示当前JSON"),
        ("/reset",          "清空JSON & 重置上下文"),
        ("/save [文件名]",  "保存JSON到文件（默认按时间命名）"),
        ("/load <文件名>",  "从JSON文件加载状态"),
        ("/history [N]",    "查看最近N条历史JSON（默认3）"),
        ("/sessions",       "查看最近10次会话记录"),
        ("/model [名称]",   "查看或切换Ollama模型"),
        ("/models",         "列出Ollama可用模型"),
        ("/ctx",            "显示当前上下文统计"),
        ("/export",         "导出JSON到剪贴板（Linux需xclip）"),
        ("/help",           "显示此帮助"),
        ("/quit 或 /exit",  "退出（自动保存会话记忆）"),
    ]
    for cmd, desc in cmds:
        t.add_row(cmd, desc)
    console.print(Panel(t, title=f"[{C['mag']} bold]命令列表[/]", border_style=C["mag"]))


# ═══════════════════════════════════════════════════════════
#  JSON 解析（处理 qwen3 的 <think> 标签）
# ═══════════════════════════════════════════════════════════
def strip_think(text: str) -> str:
    """移除 qwen3 thinking 标签中的内容"""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_json_response(raw: str) -> Optional[dict]:
    text = strip_think(raw).strip()
    # 去掉 markdown 代码块
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    # 找最外层 JSON 对象
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        # 尝试更宽松方式（有时模型会输出注释）
        try:
            cleaned = re.sub(r"//[^\n]*", "", text[start:end])
            return json.loads(cleaned)
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════
#  主应用
# ═══════════════════════════════════════════════════════════
class JSONAIApp:
    def __init__(self, cfg: dict):
        self.cfg         = cfg
        self.session_id  = str(uuid.uuid4())[:8]
        self.ctx         = ContextManager(cfg["max_ctx_msgs"], cfg["keep_recent"])
        self.memory      = MemoryManager()
        self.client      = OllamaClient(cfg["ollama_url"], cfg["model"])
        self.cur_json:   dict = {}
        self.turn_count: int  = 0

    # ── 构建 system prompt（注入当前JSON状态） ────────
    def _system(self) -> str:
        return SYSTEM_TPL.format(
            current_json=json.dumps(self.cur_json, ensure_ascii=False, indent=2)
        )

    # ── 调用模型（带 spinner，流式收集） ──────────────
    def _call(self, user_input: str) -> str:
        self.ctx.add("user", user_input)
        messages = self.ctx.build_messages(self._system())

        full = ""
        with console.status(
            f"  [bright_cyan]◌[/]  [grey70]AI 正在构建 JSON...[/]",
            spinner="dots2",
            spinner_style="bright_cyan",
        ):
            for token, done in self.client.chat_stream(
                messages, temperature=self.cfg["temperature"]
            ):
                full += token
                if done:
                    break

        self.ctx.add("assistant", full)
        return full.strip()

    # ── 命令处理器 ────────────────────────────────────
    def _cmd(self, raw: str) -> bool:
        """返回 True = 继续循环，False = 退出"""
        parts = raw.strip().split(None, 1)
        verb  = parts[0].lower()
        arg   = parts[1].strip() if len(parts) > 1 else ""

        if verb in ("/quit", "/exit", "/q"):
            return False

        elif verb == "/show":
            print_json_panel(self.cur_json)

        elif verb == "/reset":
            self.cur_json = {}
            self.ctx      = ContextManager(self.cfg["max_ctx_msgs"], self.cfg["keep_recent"])
            ok("JSON 已清空，上下文已重置")

        elif verb == "/save":
            fname = arg or f"json_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            if not fname.endswith(".json"):
                fname += ".json"
            try:
                Path(fname).write_text(
                    json.dumps(self.cur_json, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                ok(f"已保存到 [bright_cyan]{fname}[/]")
            except Exception as e:
                err(f"保存失败: {e}")

        elif verb == "/load":
            if not arg:
                err("用法: /load <文件名>")
            else:
                p = Path(arg)
                if not p.exists():
                    err(f"文件不存在: {p}")
                else:
                    try:
                        self.cur_json = json.loads(p.read_text(encoding="utf-8"))
                        ok(f"已从 [bright_cyan]{p}[/] 加载")
                        print_json_panel(self.cur_json)
                    except Exception as e:
                        err(f"加载失败: {e}")

        elif verb == "/history":
            n = int(arg) if arg.isdigit() else 3
            records = self.memory.get_recent_jsons(n)
            if not records:
                hint("暂无历史JSON记录")
            else:
                console.print()
                for i, r in enumerate(reversed(records), 1):
                    ts = r["timestamp"][:19].replace("T", " ")
                    console.print(f"  [bright_cyan]#{i}[/]  [grey54]{ts}[/]")
                    print_json_panel(r["json"], title=f"历史 #{i}", border="grey42")

        elif verb == "/sessions":
            sessions = self.memory.list_sessions()
            if not sessions:
                hint("暂无会话记录")
            else:
                t = Table(
                    box=box.SIMPLE_HEAVY,
                    border_style=C["dimmer"],
                    show_header=True,
                    header_style=C["cyan"] + " bold",
                    padding=(0, 1),
                )
                t.add_column("会话ID",  style=C["cyan"],   width=10)
                t.add_column("时间",     style="grey70",    width=20)
                t.add_column("消息数",   style=C["yellow"], width=8)
                t.add_column("JSON字段", style="grey85")
                for s in reversed(sessions):
                    ts    = s["timestamp"][:19].replace("T", " ")
                    fkeys = ", ".join(list(s.get("final_json", {}).keys())[:5]) or "—"
                    t.add_row(s["id"], ts, str(s["msg_count"]), fkeys)
                console.print(Padding(t, (0, 2)))

        elif verb == "/model":
            if not arg:
                info(f"当前模型: [bright_cyan]{self.client.model}[/]")
            else:
                self.client.model = arg
                self.cfg["model"] = arg
                ok(f"模型已切换为 [bright_cyan]{arg}[/]")

        elif verb == "/models":
            with console.status("  [bright_cyan]◌[/]  获取模型列表...", spinner="dots2"):
                models = self.client.list_models()
            if not models:
                hint("无法获取模型列表")
            else:
                for m in models:
                    mark = " [bright_green]◀ 当前[/]" if m == self.client.model else ""
                    console.print(f"  [bright_cyan]·[/]  [grey85]{m}[/]{mark}")

        elif verb == "/ctx":
            info(f"本次会话消息数: [bright_yellow]{self.ctx.total_added}[/]  "
                 f"当前窗口: [bright_yellow]{len(self.ctx.messages)}[/]  "
                 f"已压缩摘要: [bright_yellow]{'是' if self.ctx.summary else '否'}[/]")

        elif verb == "/export":
            text = json.dumps(self.cur_json, ensure_ascii=False, indent=2)
            try:
                import subprocess
                if sys.platform == "win32":
                    subprocess.run("clip", input=text.encode("utf-16"), check=True)
                elif sys.platform == "darwin":
                    subprocess.run("pbcopy", input=text.encode(), check=True)
                else:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=text.encode(),
                        check=True,
                    )
                ok("JSON 已复制到剪贴板")
            except Exception as e:
                err(f"复制失败 ({e})，直接打印：")
                console.print(text)

        elif verb == "/help":
            help_panel()

        else:
            err(f"未知命令 [bright_cyan]{verb}[/]，输入 [bright_cyan]/help[/] 查看帮助")

        return True

    # ── 主循环 ────────────────────────────────────────
    def run(self):
        banner()

        # Ollama 健康检查
        with console.status("  [bright_cyan]◌[/]  连接 Ollama...", spinner="dots2"):
            alive = self.client.check()
        if not alive:
            err(f"无法连接 Ollama ({self.cfg['ollama_url']})，请确认服务已启动")
            sys.exit(1)

        # 状态栏
        console.print(
            Panel(
                Text.assemble(
                    ("  模型  ", C["dim"]),  ("─ ", C["dimmer"]),
                    (self.cfg["model"],       C["cyan"] + " bold"),
                    ("    会话  ", C["dim"]), ("─ ", C["dimmer"]),
                    (self.session_id,          C["mag"] + " bold"),
                    ("    端点  ", C["dim"]), ("─ ", C["dimmer"]),
                    (self.cfg["ollama_url"],   C["dim"]),
                ),
                border_style=C["dimmer"],
                padding=(0, 1),
            )
        )
        console.print()
        hint("输入自然语言描述来构建 JSON，或输入 [bright_cyan]/help[/] 查看全部命令")
        console.print()

        # 最近一条 JSON 提示
        recent = self.memory.get_recent_jsons(1)
        if recent:
            hint(f"上次会话有保存的 JSON，输入 [bright_cyan]/history[/] 查看")
            console.print()

        ptk_style = PtkStyle.from_dict({
            "":       "#e0e0e0",
            "prompt": "#00d7ff bold",
        })
        history = InMemoryHistory()

        try:
            while True:
                console.print(Rule(style=C["dimmer"]))

                try:
                    raw = ptk_prompt(
                        [("class:prompt", f"  [{self.turn_count}] ❯ ")],
                        style=ptk_style,
                        history=history,
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    console.print()
                    break

                if not raw:
                    continue

                # ── 命令分支 ──────────────────────────────
                if raw.startswith("/"):
                    if not self._cmd(raw):
                        break
                    continue

                # ── AI 对话分支 ───────────────────────────
                self.turn_count += 1
                try:
                    response = self._call(raw)
                    parsed   = parse_json_response(response)

                    if parsed is not None:
                        self.cur_json = parsed
                        console.print()
                        print_json_panel(self.cur_json, title=f"✦ JSON  (第 {self.turn_count} 轮)")
                        # 自动快照防丢失
                        self.memory.save_snapshot(self.session_id, self.ctx, self.cur_json)
                    else:
                        err("模型返回内容无法解析为JSON")
                        hint("原始输出（前400字）：")
                        console.print(f"  [grey54]{strip_think(response)[:400]}[/]")

                except requests.exceptions.ConnectionError:
                    err("Ollama 连接断开，请检查服务状态")
                except requests.exceptions.Timeout:
                    err("请求超时，模型可能正在加载中，请稍后重试")
                except Exception as e:
                    err(f"发生错误: {e}")

        finally:
            # ── 退出时持久化 ──────────────────────────────
            console.print()
            with console.status(
                f"  [bright_cyan]◌[/]  保存会话记忆 [{self.session_id}]...",
                spinner="dots2",
            ):
                self.memory.record_session(self.session_id, self.ctx, self.cur_json)
            ok(f"会话 [bright_cyan]{self.session_id}[/] 已写入记忆 ({self.ctx.total_added} 条消息)")
            if self.cur_json:
                console.print()
                print_json_panel(self.cur_json, title="最终 JSON")
            console.print()
            console.print(Rule(Text("  byebye  ", style=C["dim"]), style=C["dimmer"]))
            console.print()


# ═══════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="jsonAI.py — 自然语言 → JSON 构建助手")
    parser.add_argument("--model",  default=os.environ.get("JSONAI_MODEL", DEFAULT_CFG["model"]),
                        help="Ollama 模型名称 (default: %(default)s)")
    parser.add_argument("--url",    default=os.environ.get("OLLAMA_URL", DEFAULT_CFG["ollama_url"]),
                        help="Ollama 服务地址 (default: %(default)s)")
    parser.add_argument("--temp",   type=float, default=DEFAULT_CFG["temperature"],
                        help="Temperature (default: %(default)s)")
    args = parser.parse_args()

    cfg = {**DEFAULT_CFG, "model": args.model, "ollama_url": args.url, "temperature": args.temp}
    JSONAIApp(cfg).run()


if __name__ == "__main__":
    main()
