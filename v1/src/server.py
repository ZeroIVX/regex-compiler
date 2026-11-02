"""Web 图形交互界面服务器 —— 多线程 HTTP Server (纯标准库)

启动方式:
    python -m src.server

然后浏览器访问 http://localhost:8080
"""

import json
import os
import sys
import socket
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lexer import lex, LexerError
from src.parser import parse, ParserError, print_ast
from src.nfa import ThompsonBuilder, EPSILON
from src.dfa import build_dfa
from src.minimize import minimize_dfa
from src.matcher import RegexMatcher
from src.visualizer import render_nfa_svg, render_dfa_svg, render_min_dfa_svg

HTML_PATH = os.path.join(os.path.dirname(__file__), "gui.html")


class ThreadingHTTPServer(HTTPServer):
    """支持多线程的 HTTP Server（使用 ThreadingMixin 模式）"""
    allow_reuse_address = True

    def process_request(self, request, client_address):
        """为每个请求启动新线程"""
        import threading
        t = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address),
            daemon=True,
        )
        t.start()

    def process_request_thread(self, request, client_address):
        """与标准 HTTPServer 相同的处理逻辑，但在独立线程中"""
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


class RegexAPIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器：静态文件 + API 端点"""

    # 增大超时时间
    timeout = 10

    def handle_one_request(self):
        """重写以捕获连接中断异常"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/" or path == "/index.html":
                self._serve_html()
            elif path == "/api/info":
                self._api_info(query)
            elif path == "/api/match":
                self._api_match(query)
            elif path == "/api/simulate":
                self._api_simulate(query)
            elif path == "/api/visualize":
                self._api_visualize(query)
            elif path == "/api/ast":
                self._api_ast(query)
            elif path == "/api/tokens":
                self._api_tokens(query)
            else:
                self._send_json({"error": "Not found"}, 404)
        except (LexerError, ParserError) as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, 400)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # 客户端断开连接，静默忽略
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        """精简日志"""
        pass

    # ---- 静态文件 ----

    def _serve_html(self):
        try:
            with open(HTML_PATH, "r", encoding="utf-8") as f:
                html = f.read()
        except FileNotFoundError:
            html = """<!DOCTYPE html><html><body style='font-family:sans-serif;padding:40px;'>
                <h2>GUI File Not Found</h2>
                <p>Please ensure <code>gui.html</code> exists in the src/ directory.</p>
                </body></html>"""

        self._send_response_with_body(html, "text/html")

    # ---- API 方法 ----

    def _api_info(self, query):
        """返回编译流水线统计信息"""
        pattern = query.get("pattern", [""])[0]
        tokens = lex(pattern)
        tokens_list = [t for t in tokens if t.type.name != "EOF"]
        ast = parse(pattern)
        nfa = ThompsonBuilder().build(ast)
        dfa = build_dfa(nfa)
        min_dfa = minimize_dfa(dfa)
        alphabet = sorted(set(
            sym for st in nfa.states
            for sym in st.transitions if sym is not EPSILON
        ))

        self._send_json({
            "pattern": pattern,
            "tokens": len(tokens_list),
            "nfa_states": len(nfa.states),
            "dfa_states": len(dfa.states),
            "min_dfa_states": len(min_dfa.states),
            "alphabet": alphabet,
            "compression": round(
                100 * (1 - len(min_dfa.states) / max(1, len(dfa.states))), 1
            ),
            "token_list": [{"type": t.type.name, "value": t.value, "pos": t.position}
                           for t in tokens_list],
        })

    def _api_match(self, query):
        """匹配测试（支持 match / search / findall 三种模式）"""
        pattern = query.get("pattern", [""])[0]
        text = query.get("text", [""])[0]
        mode = query.get("mode", ["match"])[0]

        ast = parse(pattern)
        nfa = ThompsonBuilder().build(ast)
        dfa = build_dfa(nfa)
        min_dfa = minimize_dfa(dfa)

        start = min_dfa.start
        current = start
        steps = [{
            "pos": 0,
            "char": "",
            "from_state": -1,
            "to_state": start.id,
            "accepted": current.is_final,
        }]

        reached_end = True
        for i, ch in enumerate(text):
            from_state = current.id
            if ch in current.transitions:
                current = current.transitions[ch]
                steps.append({
                    "pos": i + 1,
                    "char": ch,
                    "from_state": from_state,
                    "to_state": current.id,
                    "accepted": current.is_final,
                })
            else:
                steps.append({
                    "pos": i + 1,
                    "char": ch,
                    "from_state": from_state,
                    "to_state": -1,
                    "accepted": False,
                    "error": True,
                })
                reached_end = False
                break

        accepted = reached_end and current.is_final

        # search / findall 与完全匹配的判定不同，需分别计算
        if mode in ("search", "findall"):
            matcher = RegexMatcher(pattern)
            if mode == "search":
                accepted = matcher.search(text) is not None
            else:
                accepted = len(matcher.findall(text)) > 0

        self._send_json({
            "pattern": pattern,
            "text": text,
            "accepted": accepted,
            "mode": mode,
            "final_state": current.id,
            "steps": steps,
        })

    def _api_simulate(self, query):
        """DFA 模拟：展示状态转移路径"""
        pattern = query.get("pattern", [""])[0]
        text = query.get("text", [""])[0]

        ast = parse(pattern)
        nfa = ThompsonBuilder().build(ast)
        dfa = build_dfa(nfa)

        current = dfa.start
        path = [current.id]
        labels = []
        error_at = -1

        for i, ch in enumerate(text):
            if ch in current.transitions:
                labels.append(ch)
                current = current.transitions[ch]
                path.append(current.id)
            else:
                error_at = i
                break

        self._send_json({
            "path": path,
            "labels": labels,
            "final": current.is_final,
            "error_at": error_at,
        })

    def _api_visualize(self, query):
        """返回 SVG 可视化"""
        pattern = query.get("pattern", [""])[0]
        vtype = query.get("type", ["mindfa"])[0]

        ast = parse(pattern)
        nfa = ThompsonBuilder().build(ast)
        dfa = build_dfa(nfa)
        min_dfa = minimize_dfa(dfa)

        if vtype == "nfa":
            svg = render_nfa_svg(nfa)
        elif vtype == "dfa":
            svg = render_dfa_svg(dfa)
        else:
            svg = render_min_dfa_svg(min_dfa)

        self._send_response_with_body(svg, "image/svg+xml")

    def _api_ast(self, query):
        """返回 AST 文本"""
        pattern = query.get("pattern", [""])[0]
        ast = parse(pattern)
        self._send_json({"ast": print_ast(ast)})

    def _api_tokens(self, query):
        """返回 Token 列表"""
        pattern = query.get("pattern", [""])[0]
        tokens = lex(pattern)
        self._send_json({
            "tokens": [
                {"type": t.type.name, "value": t.value, "pos": t.position}
                for t in tokens if t.type.name != "EOF"
            ]
        })

    # ---- 工具方法 ----

    def _send_response_with_body(self, body: str, content_type: str):
        """发送非 JSON 响应（HTML / SVG）"""
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def main():
    port = 8080
    server = ThreadingHTTPServer(("127.0.0.1", port), RegexAPIHandler)
    print(f"\n  Regex Compiler GUI Server (multi-threaded)")
    print(f"  Open: http://localhost:{port}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
