"""定时调度模块：每 30 分钟自动执行爬虫流水线 + 数据导入。"""

import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

CRAWLER_DIR = Path(__file__).resolve().parent.parent / "crawler"
BACKEND_DIR = Path(__file__).resolve().parent
INTERVAL_SECONDS = 30 * 60  # 30 分钟

# 当前爬取状态（供前端轮询）
_crawl_state = {
    "running": False,
    "last_result": None,      # "success" | "failed"
    "last_time": None,        # 上次完成时间
    "message": "空闲",
}
_lock = threading.Lock()


def _log(msg: str) -> None:
    print(f"[调度器 {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_status() -> dict:
    """返回当前爬取状态（线程安全）。"""
    with _lock:
        return dict(_crawl_state)


def run_pipeline() -> bool:
    """执行爬虫流水线，成功返回 True。"""
    pipeline_path = CRAWLER_DIR / "run_pipeline.py"
    if not pipeline_path.exists():
        _log(f"爬虫脚本不存在: {pipeline_path}")
        return False

    _log("开始执行爬虫流水线...")
    venv_python = (
        CRAWLER_DIR / ".venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else CRAWLER_DIR / ".venv" / "bin" / "python"
    )
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    try:
        result = subprocess.run(
            [python_exe, str(pipeline_path)],
            cwd=str(CRAWLER_DIR),
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-10:]:
                _log(f"[爬虫] {line}")
        if result.returncode != 0:
            _log(f"爬虫流水线失败 (exit={result.returncode})")
            if result.stderr:
                _log(f"[stderr] {result.stderr[:500]}")
            return False
        _log("爬虫流水线完成")
        return True
    except subprocess.TimeoutExpired:
        _log("爬虫流水线超时（10 分钟）")
        return False
    except Exception as exc:
        _log(f"执行爬虫流水线异常: {exc}")
        return False


def import_data() -> bool:
    """将 analysis_result.json 导入 SQLite。"""
    data_import_path = BACKEND_DIR / "data_import.py"
    if not data_import_path.exists():
        _log(f"数据导入脚本不存在: {data_import_path}")
        return False

    _log("开始导入数据...")
    try:
        result = subprocess.run(
            [sys.executable, str(data_import_path)],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-5:]:
                _log(f"[导入] {line}")
        if result.returncode != 0:
            _log(f"数据导入失败 (exit={result.returncode})")
            return False
        _log("数据导入完成")
        return True
    except Exception as exc:
        _log(f"数据导入异常: {exc}")
        return False


def run_cycle() -> None:
    """执行一次完整的爬取→导入周期（更新状态供前端轮询）。"""
    global _crawl_state
    with _lock:
        _crawl_state["running"] = True
        _crawl_state["message"] = "爬取中..."
        _crawl_state["last_result"] = None

    _log("========== 定时任务开始 ==========")
    ok = False
    if run_pipeline():
        ok = import_data()
    _log(f"========== 定时任务结束（下次: {INTERVAL_SECONDS // 60} 分钟后）==========")

    with _lock:
        _crawl_state["running"] = False
        _crawl_state["last_result"] = "success" if ok else "failed"
        _crawl_state["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _crawl_state["message"] = "爬取完成" if ok else "爬取失败"


def _run_cycle_async() -> None:
    """在后台线程中执行 run_cycle，不阻塞调用方。"""
    try:
        run_cycle()
    except Exception as e:
        _log(f"异步执行异常: {e}")
        with _lock:
            _crawl_state["running"] = False
            _crawl_state["last_result"] = "failed"
            _crawl_state["last_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _crawl_state["message"] = str(e)[:200]


def trigger_async() -> bool:
    """异步触发一次爬取。如果已在运行则返回 False，否则在后台线程启动并立即返回 True。"""
    with _lock:
        if _crawl_state["running"]:
            return False

    thread = threading.Thread(target=_run_cycle_async, daemon=True, name="crawl-on-demand")
    thread.start()
    return True


def _schedule_loop() -> None:
    """后台线程：每 INTERVAL_SECONDS 执行一次。"""
    _log(f"调度器已启动，首次执行将在 60 秒后，之后每 {INTERVAL_SECONDS // 60} 分钟一次")
    time.sleep(60)

    while True:
        run_cycle()
        time.sleep(INTERVAL_SECONDS)


def start_scheduler() -> threading.Thread:
    """启动后台调度线程。"""
    thread = threading.Thread(target=_schedule_loop, daemon=True, name="crawler-scheduler")
    thread.start()
    _log("后台调度线程已创建")
    return thread
