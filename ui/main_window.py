"""主窗口 - 只负责UI组装和事件分发"""

import os
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QApplication, QFileDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, QSize, QEvent
from qfluentwidgets import FluentWindow, FluentIcon as FIF, IndeterminateProgressBar, NavigationItemPosition, SystemThemeListener, SplashScreen, PrimaryPushButton, PushButton, CaptionLabel, MessageBoxBase, SubtitleLabel, ComboBox, BodyLabel

from core.config_manager import ConfigManager
from core.image_manager import ImageManager
from core.replacer import ImageReplacer
from utils.admin_helper import is_admin

from .widgets import PathInfoCard, ImageListWidget, ActionBar
from .dialogs import MessageHelper
from .controllers import PathController, ImageController, PermissionController
from .settings import SettingsInterface


class LogoRefreshTriggerDialog(MessageBoxBase):
    """Logo 替换后启动图触发选择对话框。"""

    def __init__(self, candidates: list, used_filenames: set, parent=None):
        super().__init__(parent)
        self.candidates = candidates

        self.titleLabel = SubtitleLabel("选择触发启动图")
        self.infoLabel = BodyLabel(
            "为使 Logo 更新生效，请手动选择一张启动图执行触发替换。\n"
            "标记“[已用]”表示该图片此前已经用于触发。"
        )
        self.comboBox = ComboBox()

        for image in candidates:
            display_text = image["display_name"]
            self.comboBox.addItem(display_text, userData=image)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.comboBox)

        self.widget.setMinimumWidth(500)
        self.yesButton.setText("执行触发")
        self.cancelButton.setText("跳过")

    def get_selected_trigger_image(self):
        """获取当前选中的触发图片信息。"""
        return self.comboBox.currentData()


class MainWindow(FluentWindow):
    """主窗口 - 只负责UI和事件分发"""
    
    def __init__(self):
        super().__init__()
        self._init_window()
        self._init_managers()
        self._init_controllers()
        self._init_ui()
        self._init_settings_interface()
        self._connect_signals()
        self._logo_card_base_text = ""

        # 监听全局点击，实现 Logo 路径列表“点击外部自动收起”
        QApplication.instance().installEventFilter(self)
        
        # 创建系统主题监听器
        self.themeListener = SystemThemeListener(self)
        
        # 应用保存的主题设置（必须在 show() 之前）
        self.settings_interface.apply_saved_theme()
        
        # 现在显示窗口和启动屏幕（主题已应用，不会闪烁）
        self.splashScreen.raise_()
        self.show()
        
        # 处理事件队列以显示启动屏幕
        QApplication.processEvents()
        
        # 启动系统主题监听
        self.themeListener.start()
        
        # 延迟加载数据
        QTimer.singleShot(100, self._load_initial_data)
        QTimer.singleShot(200, self._check_admin_status)
    
    def _init_window(self):
        """初始化窗口属性"""
        from utils.resource_path import get_resource_path  # 确保导入路径处理模块

        self.setWindowTitle("SeewoSplash")
        self.setWindowIcon(QIcon(get_resource_path("assets/icon.ico")))
        self.resize(900, 650)
        
        # 创建启动屏幕（不在此处显示，延迟到主题应用后）
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(106, 106))
        
        self.center_window()
    
    def _init_managers(self):
        """初始化管理器"""
        self.config_manager = ConfigManager()
        self.image_manager = ImageManager()
        self.replacer = ImageReplacer(self.config_manager)
    
    def _init_controllers(self):
        """初始化控制器"""
        # 主页控制器
        self.path_ctrl = PathController(self, self.config_manager, "home")
        self.image_ctrl = ImageController(self, self.config_manager, self.image_manager)
        self.permission_ctrl = PermissionController()
        
        # WPS页面控制器
        self.wps_path_ctrl = PathController(self, self.config_manager, "wps")
        self.wps_image_ctrl = ImageController(self, self.config_manager, self.image_manager)
    
    def _init_ui(self):
        """初始化主界面UI"""
        # 主页
        self.homeInterface = QWidget()
        self.homeInterface.setObjectName("homeInterface")
        self.addSubInterface(self.homeInterface, FIF.HOME, '希沃白板')
        
        layout = QVBoxLayout(self.homeInterface)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.path_card = PathInfoCard(self.homeInterface)
        self.image_list = ImageListWidget(self.homeInterface)
        self.action_bar = ActionBar(self.homeInterface)
        self.progress_bar = IndeterminateProgressBar(self.homeInterface)
        self.progress_bar.setVisible(False)
        
        layout.addWidget(self.path_card)
        layout.addWidget(self.image_list, 1)
        layout.addWidget(self.action_bar)
        layout.addWidget(self.progress_bar)
        
        # WPS页面
        self.wpsInterface = QWidget()
        self.wpsInterface.setObjectName("wpsInterface")
        self.addSubInterface(self.wpsInterface, FIF.DOCUMENT, 'WPS Office')
        
        wps_layout = QVBoxLayout(self.wpsInterface)
        wps_layout.setContentsMargins(20, 20, 20, 20)
        wps_layout.setSpacing(15)
        
        self.wps_path_card = PathInfoCard(self.wpsInterface)
        self.wps_image_list = ImageListWidget(self.wpsInterface)
        self.wps_action_bar = ActionBar(self.wpsInterface)
        self.wps_progress_bar = IndeterminateProgressBar(self.wpsInterface)
        self.wps_progress_bar.setVisible(False)
        
        wps_layout.addWidget(self.wps_path_card)
        wps_layout.addWidget(self.wps_image_list, 1)
        wps_layout.addWidget(self.wps_action_bar)
        wps_layout.addWidget(self.wps_progress_bar)

        # Logo 页面（独立资源与替换逻辑）
        self.logoInterface = QWidget()
        self.logoInterface.setObjectName("logoInterface")
        self.addSubInterface(self.logoInterface, FIF.PALETTE, 'WPS Logo')

        logo_layout = QVBoxLayout(self.logoInterface)
        logo_layout.setContentsMargins(20, 20, 20, 20)
        logo_layout.setSpacing(15)

        self.logo_path_card = PathInfoCard(self.logoInterface)
        self.logo_path_list_title = CaptionLabel("Logo 目标路径列表")
        self.logo_path_list = QTextEdit(self.logoInterface)
        self.logo_path_list.setReadOnly(True)
        self.logo_path_list.setPlaceholderText("检测到路径后，这里会列出所有 Logo 文件位置")
        self.logo_path_list.setFixedHeight(120)
        self.logo_path_list.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.88);
                padding: 10px 12px;
                font-family: Consolas, "Microsoft YaHei UI";
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        self.logo_image_list = ImageListWidget(self.logoInterface)
        self.logo_action_row = QWidget(self.logoInterface)
        self.logo_action_layout = QHBoxLayout(self.logo_action_row)
        self.logo_action_layout.setContentsMargins(0, 0, 0, 0)
        self.logo_action_layout.setSpacing(10)
        self.logo_import_btn = PushButton(FIF.ADD, "导入Logo")
        self.logo_delete_btn = PushButton(FIF.DELETE, "删除Logo")
        self.logo_restore_btn = PushButton(FIF.SYNC, "从备份还原Logo")
        self.logo_replace_btn = PrimaryPushButton(FIF.UPDATE, "替换Logo")
        self.logo_action_layout.addWidget(self.logo_import_btn)
        self.logo_action_layout.addWidget(self.logo_delete_btn)
        self.logo_action_layout.addWidget(self.logo_restore_btn)
        self.logo_action_layout.addStretch(1)
        self.logo_action_layout.addWidget(self.logo_replace_btn)
        self.logo_progress_bar = IndeterminateProgressBar(self.logoInterface)
        self.logo_progress_bar.setVisible(False)

        # 默认折叠，点击路径卡后展开
        self.logo_path_list_title.setVisible(False)
        self.logo_path_list.setVisible(False)

        logo_layout.addWidget(self.logo_path_card)
        logo_layout.addWidget(self.logo_path_list_title)
        logo_layout.addWidget(self.logo_path_list)
        logo_layout.addWidget(self.logo_image_list, 1)
        logo_layout.addWidget(self.logo_action_row)
        logo_layout.addWidget(self.logo_progress_bar)
    
    def _init_settings_interface(self):
        """初始化设置界面"""
        self.settings_interface = SettingsInterface(self)
        
        # 添加到导航栏底部
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            '设置',
            position=NavigationItemPosition.BOTTOM
        )

    def _connect_signals(self):
        """连接信号槽"""
        # 主页信号
        self.path_card.detect_button.clicked.connect(self._on_detect_path)
        self.path_card.history_button.clicked.connect(self._on_show_history)
        self.image_list.imageSelected.connect(self._on_image_selected)
        self.image_list.imagesDropped.connect(self._on_images_dropped)
        self.action_bar.importClicked.connect(self._on_import_image)
        self.action_bar.renameClicked.connect(self._on_rename_image)
        self.action_bar.deleteClicked.connect(self._on_delete_image)
        self.action_bar.replaceClicked.connect(self._on_replace_image)
        self.action_bar.restoreClicked.connect(self._on_restore_backup)
        self.action_bar.set_logo_replace_visible(False)
        
        # WPS页面信号
        self.wps_path_card.detect_button.clicked.connect(self._on_wps_detect_path)
        self.wps_path_card.history_button.clicked.connect(self._on_wps_show_history)
        self.wps_image_list.imageSelected.connect(self._on_wps_image_selected)
        self.wps_image_list.imagesDropped.connect(self._on_wps_images_dropped)
        self.wps_action_bar.importClicked.connect(self._on_wps_import_image)
        self.wps_action_bar.renameClicked.connect(self._on_wps_rename_image)
        self.wps_action_bar.deleteClicked.connect(self._on_wps_delete_image)
        self.wps_action_bar.replaceClicked.connect(self._on_wps_replace_image)
        self.wps_action_bar.restoreClicked.connect(self._on_wps_restore_backup)
        self.wps_action_bar.replaceLogoClicked.connect(self._goto_logo_page)
        self.wps_action_bar.set_logo_replace_visible(True)

        # Logo 页面信号
        self.logo_path_card.detect_button.clicked.connect(self._on_logo_detect_path)
        self.logo_path_card.history_button.clicked.connect(self._on_logo_show_history)
        self.logo_path_card.clicked.connect(self._on_logo_path_card_clicked)
        self.logo_image_list.imageSelected.connect(self._on_logo_image_selected)
        self.logo_import_btn.clicked.connect(self._on_logo_import_image)
        self.logo_delete_btn.clicked.connect(self._on_logo_delete_image)
        self.logo_restore_btn.clicked.connect(self._on_wps_restore_logo_backup)
        self.logo_replace_btn.clicked.connect(self._on_wps_replace_logo)
    
    def _load_initial_data(self):
        """加载初始数据"""
        # 加载主页数据
        self.load_images()
        success, message = self.path_ctrl.load_and_validate_target_path()
        if success:
            self.path_card.update_path_display(self.path_ctrl.target_path)
            MessageHelper.show_success(self, message, 3000)
        else:
            self.path_card.update_path_display("")
        
        # 加载WPS页面数据
        self.load_wps_images()
        self.load_logo_images()
        wps_success, wps_message = self.wps_path_ctrl.load_and_validate_target_path()
        if wps_success:
            self._update_wps_related_path_cards()
            MessageHelper.show_success(self, wps_message, 3000)
        else:
            self._update_wps_related_path_cards()
        
        # 启动屏幕加载完成
        if hasattr(self, 'splashScreen'):
            self.splashScreen.finish()
    
    def _check_admin_status(self):
        """检查管理员权限状态"""
        if is_admin():
            current_title = self.windowTitle()
            self.setWindowTitle(f"{current_title} [管理员]")
    
    # === 事件处理方法 (简洁的分发逻辑) ===
    
    def _on_image_selected(self, image_info: dict):
        """图片选中事件"""
        self.config_manager.set_last_selected_image(image_info["filename"], "home")
        is_custom = image_info["type"] == "custom"
        self.action_bar.set_rename_delete_enabled(is_custom)
    
    def _on_wps_image_selected(self, image_info: dict):
        """WPS页面图片选中事件"""
        self.config_manager.set_last_selected_image(image_info["filename"], "wps")
        is_custom = image_info["type"] == "custom"
        self.wps_action_bar.set_rename_delete_enabled(is_custom)

    def _on_logo_image_selected(self, image_info: dict):
        """Logo页面图片选中事件"""
        pass

    def _on_logo_import_image(self):
        """Logo 页面导入图片事件。"""
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "选择Logo图片",
                os.path.expanduser("~"),
                "PNG图片 (*.png)"
            )

            if not file_paths:
                return

            success_count = 0
            failed_files = []
            first_import_name = ""

            for file_path in file_paths:
                success, result = self.image_manager.import_image(file_path)
                if success:
                    imported_filename = os.path.basename(result)
                    if not first_import_name:
                        first_import_name = imported_filename
                    self.config_manager.add_logo_custom_image(imported_filename)
                    success_count += 1
                else:
                    failed_files.append((os.path.basename(file_path), result))

            if success_count > 0:
                tip = f"成功导入 {success_count} 个Logo"
                if first_import_name:
                    tip += f"（示例: {first_import_name}）"
                if failed_files:
                    tip += f"，{len(failed_files)} 个失败"
                MessageHelper.show_success(self, tip, 3500)
                self.load_logo_images()
                self.load_wps_images()
                self.load_images()

            if failed_files:
                error_details = "\n".join([f"• {name}: {reason}" for name, reason in failed_files[:5]])
                if len(failed_files) > 5:
                    error_details += f"\n... 还有 {len(failed_files) - 5} 个文件失败"
                MessageHelper.show_error(self, "部分Logo导入失败", error_details)
        except Exception as e:
            MessageHelper.show_error(self, "Logo导入异常", str(e))

    def _on_logo_delete_image(self):
        """Logo 页面删除图片事件。"""
        image_info = self.logo_image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先选择要删除的 Logo 图片")
            return

        if image_info.get("type") != "custom":
            MessageHelper.show_warning(self, "不可删除", "预设 Logo 资源不可删除")
            return

        success, msg = self.wps_image_ctrl.delete_image(image_info)
        if success:
            self.config_manager.remove_logo_custom_image(image_info["filename"])
            MessageHelper.show_success(self, msg, 2500)
            self.load_logo_images()
            self.load_wps_images()
        else:
            MessageHelper.show_error(self, "删除失败", msg)
    
    def _on_images_dropped(self, drop_data):
        """图片拖放事件"""
        file_paths, ignored_files = drop_data
        
        if ignored_files:
            ignored_str = "、".join(ignored_files[:3])
            if len(ignored_files) > 3:
                ignored_str += f" 等{len(ignored_files)}个文件"
            MessageHelper.show_warning(
                self, "文件格式错误",
                f"以下文件不是PNG格式，已忽略：\n{ignored_str}"
            )
        
        if not file_paths:
            return
        
        self.show_progress(f"正在导入 {len(file_paths)} 个文件...")
        success_count, failed_files = self.image_ctrl.import_multiple_images(file_paths)
        self.hide_progress()
        
        if success_count > 0:
            MessageHelper.show_success(
                self,
                f"成功导入 {success_count} 个图片" + 
                (f"，{len(failed_files)} 个失败" if failed_files else ""),
                3000
            )
            self.load_images()
        
        if failed_files:
            error_details = "\n".join([f"• {name}: {msg}" for name, msg in failed_files[:5]])
            if len(failed_files) > 5:
                error_details += f"\n... 还有 {len(failed_files) - 5} 个文件失败"
            MessageHelper.show_error(self, "部分文件导入失败", error_details)
    
    def _on_detect_path(self):
        """检测路径事件"""
        self.show_progress("正在检测路径...")
        success, message = self.path_ctrl.detect_with_user_interaction()
        self.hide_progress()
        
        self.path_card.update_path_display(self.path_ctrl.target_path)
        if success:
            MessageHelper.show_success(self, message, 5000)
        elif message:
            MessageHelper.show_error(self, "检测失败", message)
    
    def _on_show_history(self):
        """显示历史路径事件"""
        success, result, need_detect = self.path_ctrl.select_from_history()
        if success:
            self.path_card.update_path_display(result)
            MessageHelper.show_success(self, f"已设置目标路径: {os.path.basename(result)}", 5000)
        elif need_detect:
            self._on_detect_path()
    
    def _on_import_image(self):
        """导入图片事件"""
        self.show_progress("正在导入...")
        success, msg, source_path = self.image_ctrl.import_single_image(allow_multiple=True)
        self.hide_progress()
        
        if success:
            MessageHelper.show_success(self, f"图片导入成功: {os.path.basename(source_path)}", 3000)
            self.load_images()
        elif msg:
            MessageHelper.show_error(self, "导入失败", msg)
    
    def _on_rename_image(self):
        """重命名图片事件"""
        image_info = self.image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先选择要重命名的图片")
            return
        
        success, msg = self.image_ctrl.rename_image(image_info)
        if success:
            MessageHelper.show_success(self, msg, 2000)
            self.load_images()
        elif msg:
            MessageHelper.show_warning(self, "重命名失败", msg)
    
    def _on_delete_image(self):
        """删除图片事件"""
        image_info = self.image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先选择要删除的图片")
            return
        
        success, msg = self.image_ctrl.delete_image(image_info)
        if success:
            MessageHelper.show_success(self, msg, 2000)
            self.load_images()
        else:
            MessageHelper.show_error(self, "删除失败", msg)
    
    def _on_replace_image(self):
        """替换启动图片事件"""
        if not self.path_ctrl.target_path:
            MessageHelper.show_warning(self, "未检测到路径", "请先点击'检测路径'按钮")
            return
        
        image_info = self.image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先从列表中选择要替换的图片")
            return
        
        self.show_progress("正在替换...")
        success, msg, is_permission_error = self.replacer.replace_image(
            image_info["path"],
            self.path_ctrl.target_path,
            self.config_manager
        )
        self.hide_progress()
        
        if success:
            MessageHelper.show_success(self, f"启动图片已替换为: {image_info['display_name']}", 3000)
        elif is_permission_error:
            self.permission_ctrl.handle_permission_error(self, msg)
        else:
            MessageHelper.show_error(self, "替换失败", msg)
    
    def _on_restore_backup(self):
        """从备份还原事件"""
        if not self.path_ctrl.target_path:
            MessageHelper.show_warning(self, "未检测到路径", "请先点击'检测路径'按钮")
            return
        
        self.show_progress("正在还原...")
        success, msg, is_permission_error = self.replacer.restore_backup(self.path_ctrl.target_path)
        self.hide_progress()
        
        if success:
            MessageHelper.show_success(self, "已从备份还原启动图片", 3000)
        elif is_permission_error:
            self.permission_ctrl.handle_permission_error(self, msg)
        else:
            MessageHelper.show_error(self, "还原失败", msg)
    
    # === WPS页面事件处理方法 ===
    
    def _on_wps_images_dropped(self, drop_data):
        """WPS页面图片拖放事件"""
        file_paths, ignored_files = drop_data
        
        if ignored_files:
            ignored_str = "、".join(ignored_files[:3])
            if len(ignored_files) > 3:
                ignored_str += f" 等{len(ignored_files)}个文件"
            MessageHelper.show_warning(
                self, "文件格式错误",
                f"以下文件不是PNG格式，已忽略：\n{ignored_str}"
            )
        
        if not file_paths:
            return
        
        self.show_progress(f"正在导入 {len(file_paths)} 个文件...", "wps")
        success_count, failed_files = self.wps_image_ctrl.import_multiple_images(file_paths)
        self.hide_progress("wps")
        
        if success_count > 0:
            MessageHelper.show_success(
                self,
                f"成功导入 {success_count} 个图片" + 
                (f"，{len(failed_files)} 个失败" if failed_files else ""),
                3000
            )
            self.load_wps_images()
        
        if failed_files:
            error_details = "\n".join([f"• {name}: {msg}" for name, msg in failed_files[:5]])
            if len(failed_files) > 5:
                error_details += f"\n... 还有 {len(failed_files) - 5} 个文件失败"
            MessageHelper.show_error(self, "部分文件导入失败", error_details)
    
    def _on_wps_detect_path(self):
        """WPS页面检测路径事件"""
        self.show_progress("正在检测路径...", "wps")
        success, message = self.wps_path_ctrl.detect_with_user_interaction()
        self.hide_progress("wps")

        self._update_wps_related_path_cards()
        if success:
            MessageHelper.show_success(self, message, 5000)
        elif message:
            MessageHelper.show_error(self, "检测失败", message)

    def _on_logo_detect_path(self):
        """Logo页面检测路径事件"""
        self._on_wps_detect_path()
    
    def _on_wps_show_history(self):
        """WPS页面显示历史路径事件"""
        success, result, need_detect = self.wps_path_ctrl.select_from_history()
        if success:
            self.wps_path_ctrl.target_path = result
            self._update_wps_related_path_cards()
            MessageHelper.show_success(self, f"已设置目标路径: {os.path.basename(result)}", 5000)
        elif need_detect:
            self._on_wps_detect_path()

    def _on_logo_show_history(self):
        """Logo页面显示历史路径事件"""
        self._on_wps_show_history()
    
    def _on_wps_import_image(self):
        """WPS页面导入图片事件"""
        self.show_progress("正在导入...", "wps")
        success, msg, source_path = self.wps_image_ctrl.import_single_image(allow_multiple=True)
        self.hide_progress("wps")
        
        if success:
            MessageHelper.show_success(self, f"图片导入成功: {os.path.basename(source_path)}", 3000)
            self.load_wps_images()
        elif msg:
            MessageHelper.show_error(self, "导入失败", msg)
    
    def _on_wps_rename_image(self):
        """WPS页面重命名图片事件"""
        image_info = self.wps_image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先选择要重命名的图片")
            return
        
        success, msg = self.wps_image_ctrl.rename_image(image_info)
        if success:
            MessageHelper.show_success(self, msg, 2000)
            self.load_wps_images()
        elif msg:
            MessageHelper.show_warning(self, "重命名失败", msg)
    
    def _on_wps_delete_image(self):
        """WPS页面删除图片事件"""
        image_info = self.wps_image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先选择要删除的图片")
            return
        
        success, msg = self.wps_image_ctrl.delete_image(image_info)
        if success:
            MessageHelper.show_success(self, msg, 2000)
            self.load_wps_images()
        else:
            MessageHelper.show_error(self, "删除失败", msg)
    
    def _on_wps_replace_image(self):
        """WPS页面替换启动图片事件"""
        if not self.wps_path_ctrl.target_path:
            MessageHelper.show_warning(self, "未检测到路径", "请先点击'检测路径'按钮")
            return
        
        image_info = self.wps_image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择图片", "请先从列表中选择要替换的图片")
            return
        
        # 获取所有需要替换的文件路径
        target_paths = self.wps_path_ctrl.get_target_paths()
        if not target_paths:
            MessageHelper.show_warning(self, "未找到启动图文件", "请确保splash目录包含所有必要的启动图文件")
            return

        if not self.permission_ctrl.ensure_admin_for_system_paths(self, target_paths, "替换启动图"):
            return
        
        self.show_progress(f"正在替换 {len(target_paths)} 个文件...", "wps")
        success, msg, is_permission_error, success_count, failed_count = self.replacer.replace_multiple_images(
            image_info["path"],
            target_paths,
            self.config_manager
        )
        self.hide_progress("wps")
        
        if success:
            if success_count == len(target_paths):
                MessageHelper.show_success(self, f"启动图片已替换为: {image_info['display_name']}\n成功替换 {success_count} 个文件", 4000)
            else:
                MessageHelper.show_warning(self, "部分替换成功", msg, 5000)
                if is_permission_error:
                    self.permission_ctrl.handle_permission_error(
                        self,
                        "部分文件替换失败，可能需要管理员权限才能写入 Program Files 目录。"
                    )
        elif is_permission_error:
            self.permission_ctrl.handle_permission_error(self, msg)
        else:
            MessageHelper.show_error(self, "替换失败", msg)
    
    def _on_wps_restore_backup(self):
        """WPS页面从备份还原事件"""
        if not self.wps_path_ctrl.target_path:
            MessageHelper.show_warning(self, "未检测到路径", "请先点击'检测路径'按钮")
            return
        
        # 获取所有需要还原的文件路径
        target_paths = self.wps_path_ctrl.get_target_paths()
        if not target_paths:
            MessageHelper.show_warning(self, "未找到启动图文件", "请确保splash目录包含所有必要的启动图文件")
            return

        if not self.permission_ctrl.ensure_admin_for_system_paths(self, target_paths, "还原启动图"):
            return
        
        self.show_progress(f"正在还原 {len(target_paths)} 个文件...", "wps")
        success, msg, is_permission_error, success_count, failed_count = self.replacer.restore_multiple_backups(target_paths)
        self.hide_progress("wps")
        
        if success:
            if success_count == len(target_paths):
                MessageHelper.show_success(self, f"已从备份还原启动图片\n成功还原 {success_count} 个文件", 4000)
            else:
                MessageHelper.show_warning(self, "部分还原成功", msg, 5000)
                if is_permission_error:
                    self.permission_ctrl.handle_permission_error(
                        self,
                        "部分文件还原失败，可能需要管理员权限才能写入 Program Files 目录。"
                    )
        elif is_permission_error:
            self.permission_ctrl.handle_permission_error(self, msg)
        else:
            MessageHelper.show_error(self, "还原失败", msg)

    def _goto_logo_page(self):
        """从 WPS 页面跳转到 Logo 页面。"""
        self.switchTo(self.logoInterface)

    def _on_wps_replace_logo(self):
        """WPS页面单独替换 Logo 事件"""
        if not self.wps_path_ctrl.target_path:
            MessageHelper.show_warning(self, "未检测到路径", "请先点击'检测路径'按钮")
            return

        image_info = self.logo_image_list.get_selected_image_info()
        if not image_info:
            MessageHelper.show_warning(self, "未选择Logo资源", "请先在 Logo 页面选择一个资源图片")
            return

        logo_paths = self.wps_path_ctrl.get_logo_target_paths()
        if not logo_paths:
            MessageHelper.show_warning(self, "未找到Logo文件", "当前 WPS 目录未检测到可替换的 companylogo.png")
            return

        startup_targets = self.wps_path_ctrl.get_target_paths()
        precheck_paths = list(dict.fromkeys(logo_paths + startup_targets[:1]))
        if not self.permission_ctrl.ensure_admin_for_system_paths(self, precheck_paths, "替换 Logo"):
            return

        self.show_progress(f"正在替换 {len(logo_paths)} 个Logo文件...", "logo")
        success, msg, is_permission_error, success_count, failed_count = self.replacer.replace_multiple_images(
            image_info["path"],
            logo_paths,
            self.config_manager
        )
        self.hide_progress("logo")

        source_name = image_info["display_name"]
        if success:
            if success_count == len(logo_paths):
                trigger_ok, trigger_msg = self._apply_logo_refresh_trigger_after_replace()
                msg = f"Logo已替换为: {source_name}\n成功替换 {success_count} 个文件"
                if trigger_msg:
                    msg += f"\n{trigger_msg}"
                if trigger_ok:
                    MessageHelper.show_success(self, msg, 5000)
                else:
                    MessageHelper.show_warning(self, "Logo替换完成（触发未完成）", msg, 6000)
            else:
                MessageHelper.show_warning(self, "Logo部分替换成功", msg, 5000)
                if is_permission_error:
                    self.permission_ctrl.handle_permission_error(
                        self,
                        "部分 Logo 文件替换失败，可能需要管理员权限才能写入 Program Files 目录。"
                    )
        elif is_permission_error:
            self.permission_ctrl.handle_permission_error(self, msg)
        else:
            MessageHelper.show_error(self, "Logo替换失败", msg)

    def _on_wps_restore_logo_backup(self):
        """Logo 页面从备份还原 Logo 事件。"""
        if not self.wps_path_ctrl.target_path:
            MessageHelper.show_warning(self, "未检测到路径", "请先点击'检测路径'按钮")
            return

        logo_paths = self.wps_path_ctrl.get_logo_target_paths()
        if not logo_paths:
            MessageHelper.show_warning(self, "未找到Logo文件", "当前 WPS 目录未检测到可还原的 companylogo.png")
            return

        if not self.permission_ctrl.ensure_admin_for_system_paths(self, logo_paths, "还原 Logo"):
            return

        self.show_progress(f"正在还原 {len(logo_paths)} 个Logo文件...", "logo")
        success, msg, is_permission_error, success_count, failed_count = self.replacer.restore_multiple_backups(logo_paths)
        self.hide_progress("logo")

        if success:
            if success_count == len(logo_paths):
                MessageHelper.show_success(self, f"已从备份还原Logo\n成功还原 {success_count} 个文件", 4000)
            else:
                MessageHelper.show_warning(self, "Logo部分还原成功", msg, 5000)
                if is_permission_error:
                    self.permission_ctrl.handle_permission_error(
                        self,
                        "部分 Logo 文件还原失败，可能需要管理员权限才能写入 Program Files 目录。"
                    )
        elif is_permission_error:
            self.permission_ctrl.handle_permission_error(self, msg)
        else:
            MessageHelper.show_error(self, "Logo还原失败", msg)

    def _apply_logo_refresh_trigger_after_replace(self):
        """Logo 替换后，手动选择启动图触发一次刷新。"""
        startup_targets = self.wps_path_ctrl.get_target_paths()
        if not startup_targets:
            return False, "未找到可用于触发刷新的启动图目标文件"

        # 仅使用非 logo 的 WPS 预设图作为触发源
        preset_images = self.image_manager.get_preset_images("wps")
        trigger_candidates = [
            image for image in preset_images
            if "logo" not in image["filename"].lower()
        ]

        if not trigger_candidates:
            return False, "未找到可用于触发的启动图预设"

        used_filenames = set(self.config_manager.get_wps_logo_trigger_used_images())

        dialog = LogoRefreshTriggerDialog(trigger_candidates, used_filenames, self)
        if not dialog.exec():
            return True, "已跳过启动图触发步骤"

        selected_trigger = dialog.get_selected_trigger_image()
        if not selected_trigger:
            return True, "未选择触发图，已跳过启动图触发步骤"

        trigger_target = startup_targets[0]
        trigger_success, trigger_msg, is_permission_error = self.replacer.replace_image(
            selected_trigger["path"],
            trigger_target,
            self.config_manager
        )

        if not trigger_success:
            if is_permission_error:
                self.permission_ctrl.handle_permission_error(self, "触发启动图刷新时权限不足")
            return False, f"触发失败：{trigger_msg}"

        self.config_manager.add_wps_logo_trigger_used_image(selected_trigger["filename"])
        return True, f"已自动触发刷新：{selected_trigger['display_name']}"

    def _update_wps_related_path_cards(self):
        """同步更新 WPS 启动图页与 Logo 页的路径显示。"""
        target_path = self.wps_path_ctrl.target_path
        if not target_path:
            self.wps_path_card.update_path_display("")
            self.logo_path_card.update_path_display("")
            self._logo_card_base_text = self.logo_path_card.path_label.text()
            self._set_logo_path_list_visible(False)
            self.logo_path_list.setPlainText("")
            return

        splash_paths = self.wps_path_ctrl.get_target_paths()
        splash_count = len(splash_paths)
        logo_paths = self.wps_path_ctrl.get_logo_target_paths()
        logo_count = len(logo_paths)

        self.wps_path_card.update_path_display(target_path, splash_count)
        if logo_paths:
            self.logo_path_card.update_path_display(logo_paths[0], logo_count, "Logo")
            self._logo_card_base_text = self.logo_path_card.path_label.text()
            self._set_logo_path_list_visible(self.logo_path_list.isVisible())
            self.logo_path_list.setPlainText("\n".join(logo_paths))
        else:
            self.logo_path_card.update_path_display("", 0, "Logo")
            self._logo_card_base_text = self.logo_path_card.path_label.text()
            self._set_logo_path_list_visible(False)
            self.logo_path_list.setPlainText("未检测到 Logo 目标文件")

    def _on_logo_path_card_clicked(self):
        """点击 Logo 路径卡时展开路径列表。"""
        self._set_logo_path_list_visible(True)

    def _set_logo_path_list_visible(self, visible: bool):
        """设置 Logo 路径小列表显示状态。"""
        self.logo_path_list_title.setVisible(visible)
        self.logo_path_list.setVisible(visible)

        if self._logo_card_base_text:
            arrow = "▲" if visible else "▼"
            self.logo_path_card.path_label.setText(f"{self._logo_card_base_text}  {arrow}")

    def _is_widget_in_container(self, widget, container):
        """判断控件是否位于指定容器内。"""
        current = widget
        while isinstance(current, QWidget):
            if current is container:
                return True
            current = current.parentWidget()
        return False

    def eventFilter(self, obj, event):
        """全局点击处理：点击外部时收起 Logo 路径列表。"""
        if event.type() == QEvent.Type.MouseButtonPress and hasattr(self, "logo_path_list"):
            if self.logo_path_list.isVisible() and isinstance(obj, QWidget):
                clicked_in_path_card = self._is_widget_in_container(obj, self.logo_path_card)
                clicked_in_path_list = self._is_widget_in_container(obj, self.logo_path_list)
                if not clicked_in_path_card and not clicked_in_path_list:
                    self._set_logo_path_list_visible(False)

        return super().eventFilter(obj, event)
    
    # === 辅助方法 ===
    
    def show_progress(self, message: str, page="home"):
        """显示进度"""
        if page == "wps":
            self.wps_progress_bar.setVisible(True)
            self.wps_progress_bar.start()
        elif page == "logo":
            self.logo_progress_bar.setVisible(True)
            self.logo_progress_bar.start()
        else:
            self.progress_bar.setVisible(True)
            self.progress_bar.start()
        MessageHelper.show_success(self, message, 2000)

    def hide_progress(self, page="home"):
        """隐藏进度"""
        if page == "wps":
            self.wps_progress_bar.stop()
            self.wps_progress_bar.setVisible(False)
        elif page == "logo":
            self.logo_progress_bar.stop()
            self.logo_progress_bar.setVisible(False)
        else:
            self.progress_bar.stop()
            self.progress_bar.setVisible(False)
    
    def load_images(self):
        """加载图片列表"""
        preset_images = self.image_manager.get_preset_images("home")
        logo_custom_set = set(self.config_manager.get_logo_custom_images())
        custom_images = [
            img for img in self.image_manager.get_custom_images(mode="all")
            if img["filename"] not in logo_custom_set and "logo" not in img["filename"].lower()
        ]
        self.image_list.load_images(preset_images, custom_images)
        
        last_selected = self.config_manager.get_last_selected_image("home")
        if last_selected:
            self.image_list.select_image_by_filename(last_selected)
    
    def load_wps_images(self):
        """加载WPS页面图片列表"""
        preset_images = self.image_manager.get_preset_images("wps")
        logo_custom_set = set(self.config_manager.get_logo_custom_images())
        custom_images = [
            img for img in self.image_manager.get_custom_images(mode="all")
            if img["filename"] not in logo_custom_set and "logo" not in img["filename"].lower()
        ]
        self.wps_image_list.load_images(preset_images, custom_images)
        
        last_selected = self.config_manager.get_last_selected_image("wps")
        if last_selected:
            self.wps_image_list.select_image_by_filename(last_selected)

    def load_logo_images(self):
        """加载 Logo 页面资源（仅 Logo）。"""
        preset_images = self.image_manager.get_logo_preset_images()
        logo_custom_set = set(self.config_manager.get_logo_custom_images())
        custom_images = [
            img for img in self.image_manager.get_custom_images(mode="all")
            if img["filename"] in logo_custom_set or "logo" in img["filename"].lower()
        ]
        self.logo_image_list.load_images(preset_images, custom_images)

        if preset_images:
            self.logo_image_list.select_image_by_filename(preset_images[0]["filename"])
        elif custom_images:
            self.logo_image_list.select_image_by_filename(custom_images[0]["filename"])

    def center_window(self):
        """将窗口移动到屏幕中心"""
        screen = self.screen().availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen.center())
        self.move(frame.topLeft())
    
    def resizeEvent(self, e):
        """处理窗口大小改变事件"""
        super().resizeEvent(e)
        # 调整启动屏幕大小
        if hasattr(self, 'splashScreen'):
            self.splashScreen.resize(self.size())
    
    def closeEvent(self, e):
        """处理窗口关闭事件"""
        # 清理系统主题监听器
        if hasattr(self, 'themeListener'):
            self.themeListener.terminate()
            self.themeListener.deleteLater()

        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        
        super().closeEvent(e)
