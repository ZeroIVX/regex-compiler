"""Web 图形界面服务器 —— 基于标准库的多线程 HTTP 服务。

只依赖 Python 标准库，无需任何第三方 Web 框架。

启动方式::

    python -m regex_compiler --serve
    # 或
    python -m regex_compiler.web.server

然后浏览器访问 http://127.0.0.1:8080
"""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..core.matcher import RegexMatcher
from ..errors import RegexCompilerError
from ..frontend.parser import print_ast
from ..visualization import (
    render_dfa_svg,
    render_min_dfa_svg,
    render_nfa_svg,
)

GUI_PATH = Path(__file__).parent / "gui.html"


class RegexAPIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器：静态页面 + JSON API。"""

    server_version = "RegexCompiler/2.0"
    timeout = 15

    # ---- 请求分发 ----

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        """处理 GET 请求。"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if path in ("/", "/index.html"):
                self._serve_html()
            elif path == "/api/info":
                self._api_info(query)
            elif path == "/api/match":
                self._api_match(query)
            elif path == "/api/visualize":
                self._api_visualize(query)
            elif path == "/api/ast":
                self._api_ast(query)
            elif path == "/api/tokens":
                self._api_tokens(query)
            else:
                self._send_json({"error": "Not found"}, 404)
        except RegexCompilerError as error:
            self._send_json({"error": f"{type(error).__name__}: {error}"}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # 客户端提前断开
        except Exception as error:  # pragma: no cover - 兜底
            self._send_json({"error": str(error)}, 500)

    def log_message(self, format: str, *args) -> None:
        """关闭逐条请求日志，避免刷屏。"""

    # ---- 静态资源 ----

    def _serve_html(self) -> None:
        """返回 GUI 页面。"""
        try:
            html = GUI_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            html = (
                "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:40px'>"
                "<h2>GUI 文件缺失</h2><p>请确认 gui.html 位于 regex_compiler/web/ 目录下。</p>"
                "</body></html>"
            )
        self._send_body(html, "text/html")

    # ---- API ----

    def _api_info(self, query: dict[str, list[str]]) -> None:
        """返回编译流水线的统计信息。"""
        pattern = _first(query, "pattern")
        matcher = RegexMatcher(pattern)

        self._send_json(
            {
                "pattern": pattern,
                "tokens": len(matcher.tokens),
                "nfa_states": len(matcher.nfa.states),
                "dfa_states": len(matcher.dfa.states),
                "min_dfa_states": len(matcher.min_dfa.states),
                "alphabet": [
                    matcher.alphabet.label_of(block_id)
                    for block_id in matcher.alphabet.covered_ids
                ],
                "compression": round(
                    100
                    * (
                        1
                        - len(matcher.min_dfa.states)
                        / max(1, len(matcher.dfa.states))
                    ),
                    1,
                ),
                "token_list": [
                    {"type": token.type.name, "value": token.value, "pos": token.position}
                    for token in matcher.tokens
                ],
            }
        )

    def _api_match(self, query: dict[str, list[str]]) -> None:
        """执行匹配并返回模拟轨迹。"""
        pattern = _first(query, "pattern")
        text = _first(query, "text")
        matcher = RegexMatcher(pattern)

        steps = matcher.simulate(text)
        accepted = matcher.match(text)
        search_result = matcher.search(text)
        all_matches = matcher.findall(text)

        self._send_json(
            {
                "pattern": pattern,
                "text": text,
                "accepted": accepted,
                "search": list(search_result) if search_result else None,
                "findall": [
                    {"start": start, "end": end, "text": value}
                    for start, end, value in all_matches
                ],
                "steps": steps,
            }
        )

    def _api_visualize(self, query: dict[str, list[str]]) -> None:
        """返回自动机的 SVG 可视化。"""
        pattern = _first(query, "pattern")
        kind = _first(query, "type", default="mindfa")
        matcher = RegexMatcher(pattern)

        if kind == "nfa":
            svg = render_nfa_svg(matcher.nfa)
        elif kind == "dfa":
            svg = render_dfa_svg(matcher.dfa)
        else:
            svg = render_min_dfa_svg(matcher.min_dfa)

        self._send_body(svg, "image/svg+xml")

    def _api_ast(self, query: dict[str, list[str]]) -> None:
        """返回 AST 的文本形式。"""
        pattern = _first(query, "pattern")
        matcher = RegexMatcher(pattern)
        self._send_json({"ast": print_ast(matcher.ast)})

    def _api_tokens(self, query: dict[str, list[str]]) -> None:
        """返回 Token 列表。"""
        pattern = _first(query, "pattern")
        matcher = RegexMatcher(pattern)
        self._send_json(
            {
                "tokens": [
                    {"type": token.type.name, "value": token.value, "pos": token.position}
                    for token in matcher.tokens
                ]
            }
        )

    # ---- 响应工具 ----

    def _send_body(self, body: str, content_type: str) -> None:
        """发送非 JSON 响应。"""
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data: dict, status: int = 200) -> None:
        """发送 JSON 响应。"""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def _first(query: dict[str, list[str]], key: str, default: str = "") -> str:
    """从查询参数中取第一个值。"""
    values = query.get(key)
    return values[0] if values else default


def serve(host: str = "127.0.0.1", port: int = 8080, quiet: bool = False) -> None:
    """启动 Web 服务器（阻塞直到 Ctrl+C）。

    Args:
        host: 监听地址。
        port: 监听端口。
        quiet: 为 ``True`` 时不打印启动横幅，交由调用方自行输出。
    """
    server = ThreadingHTTPServer((host, port), RegexAPIHandler)
    if not quiet:
        print()
        print("  正则表达式编译器 — Web 图形界面")
        print(f"  访问地址: http://{host}:{port}")
        print("  按 Ctrl+C 停止服务")
        print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  服务器已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
