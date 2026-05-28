"""本地预览 dashboard.html 的静态服务器。

仪表盘通过 fetch 读取 STATUS.md，浏览器禁止 file:// 跨文件读取，
因此必须经由 HTTP 打开。本脚本以项目根目录为服务根，仅绑定回环地址。

用法:
    python scripts/start_server.py            # 默认端口 8080
    python scripts/start_server.py 9000        # 指定端口
端口被占用时自动顺延到下一个可用端口。Ctrl+C 停止。
"""
import os
import sys
import threading
import webbrowser
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

# 项目根目录 = 脚本所在 scripts/ 的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PORT = 8080
MAX_TRIES = 20  # 端口占用时最多顺延的次数


class QuietHandler(SimpleHTTPRequestHandler):
    """安静日志 + 强制 no-cache，确保每次刷新读到最新 STATUS.md。"""

    def log_message(self, fmt, *args):
        # 只在出错时打印，避免刷屏
        if not str(args[1] if len(args) > 1 else "").startswith("2"):
            sys.stderr.write("  %s\n" % (fmt % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


def find_server(start_port):
    """从 start_port 起寻找可绑定的端口，返回 (server, port)。"""
    handler = partial(QuietHandler, directory=ROOT)
    for port in range(start_port, start_port + MAX_TRIES):
        try:
            return HTTPServer(("127.0.0.1", port), handler), port
        except OSError:
            continue
    sys.exit(f"端口 {start_port}–{start_port + MAX_TRIES - 1} 均被占用，请关闭占用程序或指定其他端口。")


def main():
    if not os.path.isfile(os.path.join(ROOT, "dashboard.html")):
        sys.exit(f"未在 {ROOT} 找到 dashboard.html，请确认脚本位于 scripts/ 目录下。")

    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        if not sys.argv[1].isdigit():
            sys.exit(f"端口需为数字，收到: {sys.argv[1]}")
        port = int(sys.argv[1])

    server, port = find_server(port)
    url = f"http://localhost:{port}/dashboard.html"

    print(f"\n  仪表盘服务已启动: {url}")
    print("  浏览器将自动打开。按 Ctrl+C 停止。\n")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
