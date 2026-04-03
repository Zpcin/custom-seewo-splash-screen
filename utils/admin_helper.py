# file: utils/admin_helper.py

import ctypes
import sys
import os
import subprocess
from pathlib import Path


def _write_admin_log(message: str):
    """把提权相关错误写到临时日志，便于窗口程序排查。"""
    try:
        log_path = Path(os.environ.get("TEMP", os.getcwd())) / "SeewoSplash-admin.log"
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(message.rstrip() + "\n")
    except Exception:
        pass


def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _is_python_script_entry() -> bool:
    """判断当前入口是否为 Python 脚本（.py/.pyw）。"""
    if getattr(sys, "frozen", False):
        return False

    entry_suffix = os.path.splitext(sys.argv[0])[1].lower()
    return entry_suffix in {".py", ".pyw"}


def _is_internal_elevated_launch() -> bool:
    """检查是否为内部提权重启。"""
    return "--elevated" in sys.argv


def _strip_internal_flags(arguments: list[str]) -> list[str]:
    """移除内部控制参数。"""
    return [arg for arg in arguments if arg != "--elevated"]


def run_as_admin():
    """
    请求以管理员权限重启程序
    
    Returns:
        bool: 是否成功请求重启
    """
    try:
        current_directory = os.path.dirname(os.path.abspath(sys.executable))

        if _is_python_script_entry():
            # 脚本模式：提升 Python 解释器并传入脚本与参数
            target = os.path.abspath(sys.executable)
            script_path = os.path.abspath(sys.argv[0])
            parameters = subprocess.list2cmdline([script_path, "--elevated", *_strip_internal_flags(sys.argv[1:])])
        else:
            # 打包模式：直接提升当前可执行文件
            target = os.path.abspath(sys.executable)
            parameters = subprocess.list2cmdline(["--elevated", *_strip_internal_flags(sys.argv[1:])]) if len(sys.argv) > 1 else "--elevated"

        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            target,
            parameters,
            current_directory,
            1,
        )

        # ShellExecuteW 返回值 <= 32 表示失败或用户取消UAC
        success = result > 32
        if not success:
            _write_admin_log(f"ShellExecuteW failed, result={result}, target={target}, params={parameters}")
        return success
    except Exception as e:
        print(f"请求管理员权限失败: {e}")
        _write_admin_log(f"Exception while requesting admin: {e}")
        return False


def request_admin_and_exit():
    """请求管理员权限并退出当前进程"""
    if run_as_admin():
        sys.exit(0)
    return False
