import sys
import traceback
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from utils.admin_helper import is_admin, run_as_admin


def _write_startup_error(error_text: str):
    """把启动异常写入临时日志，便于排查窗口程序闪退。"""
    try:
        log_path = Path(__import__("os").environ.get("TEMP", ".")) / "SeewoSplash-startup.log"
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(error_text.rstrip() + "\n")
    except Exception:
        pass


def _startup_excepthook(exc_type, exc_value, exc_tb):
    error_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write_startup_error(error_text)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _consume_internal_startup_flags() -> bool:
    """消费内部启动参数，返回是否为内部提权重启。"""
    elevated = "--elevated" in sys.argv
    if elevated:
        sys.argv = [arg for arg in sys.argv if arg != "--elevated"]
    return elevated

def main():
    sys.excepthook = _startup_excepthook

    try:
        launched_from_internal_elevation = _consume_internal_startup_flags()

        # 默认启动时优先申请管理员权限（用户可取消）
        if not launched_from_internal_elevation and not is_admin():
            if run_as_admin():
                return

        # 在创建QApplication之前设置高DPI支持
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # 设置高DPI缩放策略
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        # 创建应用程序
        app = QApplication(sys.argv)

        # 创建并显示主窗口（主题色由设置界面的apply_saved_theme处理）
        window = MainWindow()
        window.show()

        # 运行应用程序
        sys.exit(app.exec())
    except Exception:
        _write_startup_error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
