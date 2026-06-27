import os
import sys
import io

# Windows下必须在导入任何其他模块前设置事件循环策略
if sys.platform == 'win32':
    try:
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass  # 如果设置失败也继续

import uvicorn


class TeeOutput:
    """同时输出到控制台和日志文件"""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("TeeOutput has no file descriptor")


if __name__ == "__main__":
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        import shutil
        try:
            shutil.copy(".env.example", ".env")
        except (IOError, OSError) as e:
            print(f"[run.py] ⚠️ 复制 .env.example -> .env 失败: {e}", file=sys.stderr)

    # 确保 stdout/stderr 使用 UTF-8 编码
    if sys.platform == 'win32':
        try:
            sys.__stdout__.reconfigure(encoding='utf-8', errors='replace')
            sys.__stderr__.reconfigure(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f"[run.py] ⚠️ 设置 UTF-8 编码失败: {e}", file=sys.stderr)

    # 日志文件路径（打开失败时退化为仅控制台输出，不应中断启动）
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.log")
    try:
        log_stream = open(log_file, "a", encoding="utf-8")
        sys.stdout = TeeOutput(sys.__stdout__, log_stream)
        sys.stderr = TeeOutput(sys.__stderr__, log_stream)
    except (IOError, OSError) as e:
        print(f"[run.py] ⚠️ 无法打开日志文件 {log_file}，仅输出到控制台: {e}", file=sys.stderr)

    print(f"\n{'='*60}")
    print(f"[run.py] 系统启动 - {__file__}")
    print(f"[run.py] 日志文件: {log_file}")
    print(f"{'='*60}")

    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        loop="asyncio",
        log_level="info",
    )
