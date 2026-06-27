import sys
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import webbrowser

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist'), **kwargs)
    
    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}")

def run_server(port=8080):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, FrontendHandler)
    print(f"\n{'='*60}")
    print(f"[SERVER] 前端静态服务器已启动")
    print(f"[SERVER] 访问地址: http://localhost:{port}")
    print(f"[SERVER] 按 Ctrl+C 停止服务")
    print(f"{'='*60}\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] 服务已停止")
        httpd.server_close()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
