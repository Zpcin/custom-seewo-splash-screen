import os
import glob
import re
import subprocess
from qfluentwidgets import MessageBox
from PyQt5.QtWidgets import QFileDialog

try:
    import winreg
except ImportError:
    winreg = None


class PathDetector:
    """检测希沃白板启动图片路径"""
    _wps_install_base_paths_cache = None
    
    @staticmethod
    def _get_available_drives():
        """
        获取所有可用的驱动器盘符
        
        Returns:
            list: 可用驱动器盘符列表，如 ['C', 'D', 'E']
        """
        drives = []
        for drive_letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = f"{drive_letter}:\\"
            if os.path.exists(drive_path):
                drives.append(drive_letter)
        
        # 如果没有找到驱动器，尝试从环境变量获取
        if not drives:
            userprofile = os.environ.get("USERPROFILE", "")
            if userprofile:
                drive = os.path.splitdrive(userprofile)[0]
                if drive:
                    drive_letter = drive[0]
                    if drive_letter not in drives:
                        drives.append(drive_letter)
        
        return drives
    
    @staticmethod
    def detect_banner_paths():
        """检测Banner.png路径（支持多驱动器）"""
        paths = []
        
        # 遍历所有可用驱动器
        for drive_letter in PathDetector._get_available_drives():
            users_dir = f"{drive_letter}:\\Users"
            
            if not os.path.exists(users_dir):
                continue
            
            try:
                for user_folder in os.listdir(users_dir):
                    user_dir = os.path.join(users_dir, user_folder)
                    if not os.path.isdir(user_dir):
                        continue
                    
                    banner_path = os.path.join(
                        user_dir, 
                        "AppData\\Roaming\\Seewo\\EasiNote5\\Resources\\Banner\\Banner.png"
                    )
                    if os.path.exists(banner_path):
                        paths.append(banner_path)
            except (PermissionError, OSError):
                continue
        
        return paths
    
    @staticmethod
    def detect_splashscreen_paths():
        """检测SplashScreen.png路径（支持多驱动器）"""
        paths = []
        
        # 遍历所有可用驱动器
        for drive_letter in PathDetector._get_available_drives():
            # 检测 Program Files (x86)
            base_path_x86 = f"{drive_letter}:\\Program Files (x86)\\Seewo\\EasiNote5"
            if os.path.exists(base_path_x86):
                # 所有可能的路径组合
                patterns = [
                    # 旧版路径格式
                    os.path.join(base_path_x86, "EasiNote5*", "Main", "Assets", "SplashScreen.png"),
                    # 新版路径格式
                    os.path.join(base_path_x86, "EasiNote5_*", "Main", "Resources", "Startup", "SplashScreen.png"),
                ]
                
                for pattern in patterns:
                    paths.extend(glob.glob(pattern))
            
            # 检测 Program Files
            base_path = f"{drive_letter}:\\Program Files\\Seewo\\EasiNote5"
            if os.path.exists(base_path):
                # 所有可能的路径组合
                patterns = [
                    # 旧版路径格式
                    os.path.join(base_path, "EasiNote5*", "Main", "Assets", "SplashScreen.png"),
                    # 新版路径格式
                    os.path.join(base_path, "EasiNote5_*", "Main", "Resources", "Startup", "SplashScreen.png"),
                ]
                
                for pattern in patterns:
                    paths.extend(glob.glob(pattern))
        
        return paths
    
    @staticmethod
    def detect_all_easinote_versions():
        """
        检测所有版本的希沃白板安装路径（支持多驱动器）
        
        Returns:
            list: 包含版本信息的字典列表
        """
        versions = []
        
        # 遍历所有可用驱动器
        for drive_letter in PathDetector._get_available_drives():
            # 检测 Program Files (x86) 和 Program Files
            base_paths = [
                f"{drive_letter}:\\Program Files (x86)\\Seewo\\EasiNote5",
                f"{drive_letter}:\\Program Files\\Seewo\\EasiNote5"
            ]
            
            for base_path in base_paths:
                if not os.path.exists(base_path):
                    continue
                
                try:
                    # 查找所有版本目录
                    for item in os.listdir(base_path):
                        item_path = os.path.join(base_path, item)
                        if os.path.isdir(item_path) and item.startswith("EasiNote5"):
                            # 解析版本信息
                            version_info = PathDetector._parse_version_info(item)
                            if version_info:
                                version_info['base_path'] = base_path
                                version_info['full_path'] = item_path
                                versions.append(version_info)
                except (PermissionError, OSError):
                    continue
        
        # 按版本号排序（新版本在前）
        versions.sort(key=lambda x: x['version_tuple'], reverse=True)
        return versions
    
    @staticmethod
    def _parse_version_info(folder_name):
        """
        解析版本信息
        
        Args:
            folder_name: 文件夹名称，如 "EasiNote5_5.2.4.9158"
            
        Returns:
            dict: 版本信息字典
        """
        # 匹配版本号模式
        patterns = [
            r'EasiNote5_(\d+\.\d+\.\d+\.\d+)',  # 新版: EasiNote5_5.2.4.9158
            r'EasiNote5\.(\d+\.\d+\.\d+)',      # 旧版: EasiNote5.5.2.3
            r'EasiNote5_(\d+\.\d+\.\d+)',       # 可能的格式: EasiNote5_5.2.3
            r'EasiNote5\.(\d+)',                # 更简单的格式: EasiNote5.5
        ]
        
        for pattern in patterns:
            match = re.search(pattern, folder_name)
            if match:
                version_str = match.group(1)
                version_parts = version_str.split('.')
                
                # 补齐版本号至4位
                while len(version_parts) < 4:
                    version_parts.append('0')
                
                try:
                    version_tuple = tuple(int(part) for part in version_parts[:4])
                    return {
                        'folder_name': folder_name,
                        'version_str': version_str,
                        'version_tuple': version_tuple,
                        'is_new_format': folder_name.startswith('EasiNote5_')
                    }
                except ValueError:
                    continue
        
        return None
    
    @staticmethod
    def get_splash_paths_by_version():
        """
        按版本获取启动图路径
        
        Returns:
            list: 包含路径和版本信息的字典列表
        """
        splash_paths = []
        versions = PathDetector.detect_all_easinote_versions()
        
        for version in versions:
            # 尝试所有可能的路径组合
            possible_paths = [
                # 路径1: Main/Assets/SplashScreen.png (最常见)
                os.path.join(version['full_path'], "Main", "Assets", "SplashScreen.png"),
                # 路径2: Main/Resources/Startup/SplashScreen.png (新版可能路径)
                os.path.join(version['full_path'], "Main", "Resources", "Startup", "SplashScreen.png"),
            ]
            
            for splash_path in possible_paths:
                if os.path.exists(splash_path):
                    # 确定路径类型
                    if "Resources\\Startup" in splash_path:
                        path_type = "新版路径格式"
                    else:
                        path_type = "标准路径格式"
                    
                    splash_paths.append({
                        'path': splash_path,
                        'version': version['version_str'],
                        'folder_name': version['folder_name'],
                        'is_new_format': version['is_new_format'],
                        'path_type': path_type
                    })
                    break  # 找到一个有效路径就跳出
        
        return splash_paths
    
    @staticmethod
    def detect_all_paths():
        """检测所有可能的路径"""
        all_paths = []
        all_paths.extend(PathDetector.detect_banner_paths())
        all_paths.extend(PathDetector.detect_splashscreen_paths())
        return all_paths
    
    @staticmethod
    def detect_wps_paths():
        r"""检测WPS Office启动图片路径（splash目录结构）
        
        返回splash目录的路径，如果找到splash目录，则返回该目录路径
        如果找不到splash目录，则返回空列表
        
        支持的路径格式：
        1. 用户目录：C:\Users\[用户名]\AppData\Local\Kingsoft\WPS Office\[版本号]\office6\mui\[语言]\resource\splash\
        2. Program Files：C:\Program Files\Kingsoft\WPS Office\office6\mui\[语言]\res\splash\
        3. Program Files (x86)：C:\Program Files (x86)\Kingsoft\WPS Office\office6\mui\[语言]\res\splash\
        """
        splash_dirs = []
        
        # 1. 检测用户目录下的WPS路径
        splash_dirs.extend(PathDetector._detect_wps_user_paths())
        
        # 2. 检测Program Files下的WPS路径
        splash_dirs.extend(PathDetector._detect_wps_program_files_paths())
        
        # 去重并返回所有找到的splash目录
        return list(dict.fromkeys(splash_dirs))
    
    @staticmethod
    def _detect_wps_user_paths():
        r"""检测用户目录下的WPS路径
        
        路径格式：C:\Users\[用户名]\AppData\Local\Kingsoft\WPS Office\[版本号]\office6\mui\[语言]\resource\splash\
        """
        splash_dirs = []
        
        # 获取所有可能的用户目录
        # 尝试常见的盘符（C、D、E等）
        possible_drives = []
        for drive_letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            users_path = f"{drive_letter}:\\Users"
            if os.path.exists(users_path):
                possible_drives.append(drive_letter)
        
        # 如果没有找到Users目录，尝试使用环境变量
        if not possible_drives:
            userprofile = os.environ.get("USERPROFILE", "")
            if userprofile:
                # 从USERPROFILE提取盘符，如 C:\Users\Luminary -> C
                drive = os.path.splitdrive(userprofile)[0]
                if drive:
                    possible_drives.append(drive[0])  # 提取盘符字母
        
        # 优先检查当前用户目录
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            current_user_splash = PathDetector._check_user_wps_path(userprofile)
            if current_user_splash:
                splash_dirs.append(current_user_splash)
                # 如果找到当前用户的路径，直接返回（优先使用当前用户的）
                return splash_dirs
        
        # 遍历所有可能的用户目录（检查其他用户）
        for drive_letter in possible_drives:
            users_dir = f"{drive_letter}:\\Users"
            if not os.path.exists(users_dir):
                continue
            
            # 遍历所有用户目录
            try:
                for user_name in os.listdir(users_dir):
                    user_dir = os.path.join(users_dir, user_name)
                    if not os.path.isdir(user_dir):
                        continue
                    
                    # 跳过已经检查过的当前用户目录
                    if user_dir == userprofile:
                        continue
                    
                    user_splash = PathDetector._check_user_wps_path(user_dir)
                    if user_splash:
                        splash_dirs.append(user_splash)
            except (PermissionError, OSError):
                continue
        
        return splash_dirs
    
    @staticmethod
    def _check_user_wps_path(user_dir):
        r"""检查指定用户目录下的WPS路径
        
        Args:
            user_dir: 用户目录路径，如 C:\Users\Luminary
            
        Returns:
            str: 找到的splash目录路径，如果未找到则返回None
        """
        # 构建WPS路径
        wps_base = os.path.join(user_dir, "AppData", "Local", "Kingsoft", "WPS Office")
        if not os.path.exists(wps_base):
            return None
        
        # 查找所有版本号目录
        try:
            for version_dir in os.listdir(wps_base):
                version_path = os.path.join(wps_base, version_dir)
                if not os.path.isdir(version_path):
                    continue
                
                # 检查office6目录
                office6_path = os.path.join(version_path, "office6")
                if not os.path.exists(office6_path):
                    continue
                
                # 检查mui目录
                mui_path = os.path.join(office6_path, "mui")
                if not os.path.exists(mui_path):
                    continue
                
                # 遍历所有语言目录
                try:
                    for lang_dir in os.listdir(mui_path):
                        lang_path = os.path.join(mui_path, lang_dir)
                        if not os.path.isdir(lang_path):
                            continue
                        
                        # 检查resource目录（注意是resource不是res）
                        resource_path = os.path.join(lang_path, "resource")
                        if not os.path.exists(resource_path):
                            continue
                        
                        # 检查splash目录
                        splash_dir = os.path.join(resource_path, "splash")
                        if os.path.isdir(splash_dir):
                            # 验证splash目录是否包含必要的文件
                            if PathDetector._validate_wps_splash_dir(splash_dir):
                                return splash_dir
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        return None
    
    @staticmethod
    def _detect_wps_program_files_paths():
        r"""检测系统安装目录下的WPS路径
        
        路径格式：C:\Program Files\Kingsoft\WPS Office\office6\mui\[语言]\res\splash\
        或：C:\Program Files\Kingsoft\WPS Office\office6\mui\[语言]\resource\splash\
        """
        splash_dirs = []

        possible_base_paths = PathDetector._get_wps_install_base_paths()
        
        # WPS可能的splash目录路径模式
        # 注意：可能是res或resource
        splash_dir_patterns = [
            "office6\\mui\\*\\resource\\splash",  # 用户目录格式
            "office6\\mui\\*\\res\\splash",        # Program Files格式
            "*\\office6\\mui\\*\\resource\\splash",  # Program Files 含版本号目录
            "*\\office6\\mui\\*\\res\\splash",       # Program Files 含版本号目录
            "office6\\res\\splash",
            "*\\office6\\res\\splash",
            "wps\\res\\splash",
            "*\\wps\\res\\splash",
        ]
        
        for base_path in possible_base_paths:
            if os.path.exists(base_path):
                for pattern in splash_dir_patterns:
                    full_pattern = os.path.join(base_path, pattern)
                    found_dirs = glob.glob(full_pattern)
                    for splash_dir in found_dirs:
                        if os.path.isdir(splash_dir):
                            # 验证splash目录是否包含必要的文件
                            if PathDetector._validate_wps_splash_dir(splash_dir):
                                splash_dirs.append(splash_dir)
        
        return splash_dirs

    @staticmethod
    def _get_wps_install_base_paths():
        """获取WPS Office可能的安装根目录。"""
        if PathDetector._wps_install_base_paths_cache is not None:
            return PathDetector._wps_install_base_paths_cache

        paths = []

        # 1) 注册表安装信息（最可靠）
        paths.extend(PathDetector._get_wps_base_paths_from_registry())

        # 2) Program Files 常见目录兜底
        for root in PathDetector._get_program_files_roots():
            paths.extend([
                os.path.join(root, "Kingsoft", "WPS Office"),
                os.path.join(root, "WPS Office"),
            ])

        dedup_paths = list(dict.fromkeys(paths))

        # 3) 仅在前两步都没有命中现有目录时，再扫描快捷方式（耗时操作）
        if not any(os.path.isdir(path) for path in dedup_paths):
            dedup_paths.extend(PathDetector._get_wps_base_paths_from_shortcuts())

        # 去重并保留顺序
        PathDetector._wps_install_base_paths_cache = list(dict.fromkeys(dedup_paths))
        return PathDetector._wps_install_base_paths_cache

    @staticmethod
    def _get_wps_base_paths_from_registry():
        """从卸载注册表中提取WPS安装目录。"""
        if winreg is None:
            return []

        uninstall_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        paths = []
        for hive, root_path in uninstall_roots:
            try:
                with winreg.OpenKey(hive, root_path) as root_key:
                    index = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(root_key, index)
                            index += 1
                        except OSError:
                            break

                        try:
                            with winreg.OpenKey(root_key, subkey_name) as app_key:
                                display_name = PathDetector._read_registry_value(app_key, "DisplayName")
                                publisher = PathDetector._read_registry_value(app_key, "Publisher")
                                install_location = PathDetector._read_registry_value(app_key, "InstallLocation")
                                uninstall_string = PathDetector._read_registry_value(app_key, "UninstallString")
                                display_icon = PathDetector._read_registry_value(app_key, "DisplayIcon")

                                if not PathDetector._is_wps_registry_entry(display_name, publisher):
                                    continue

                                for raw in (install_location, uninstall_string, display_icon):
                                    paths.extend(PathDetector._extract_wps_base_paths_from_text(raw))
                        except OSError:
                            continue
            except OSError:
                continue

        return list(dict.fromkeys(paths))

    @staticmethod
    def _read_registry_value(reg_key, value_name):
        """读取注册表字符串值，读取失败时返回空字符串。"""
        try:
            value, _ = winreg.QueryValueEx(reg_key, value_name)
            return str(value)
        except OSError:
            return ""

    @staticmethod
    def _is_wps_registry_entry(display_name, publisher):
        """判断注册表项是否为WPS相关软件。"""
        text = f"{display_name} {publisher}".lower()
        if "kingsoft" in text:
            return True
        if "wps office" in text:
            return True
        return bool(re.search(r"\bwps\b", text))

    @staticmethod
    def _extract_wps_base_paths_from_text(text):
        """从注册表字符串中提取WPS安装根目录候选。"""
        if not text:
            return []

        value = text.strip()
        if not value:
            return []

        # DisplayIcon 常见格式: C:\path\to\app.exe,0
        if "," in value and value.lower().endswith((".exe,0", ".exe,1", ".exe,2")):
            value = value.rsplit(",", 1)[0]

        # UninstallString 常见格式: "C:\path\app.exe" /uninstall
        if value.startswith('"'):
            quote_end = value.find('"', 1)
            if quote_end > 1:
                value = value[1:quote_end]

        value = value.split(" /", 1)[0].split(" -", 1)[0]

        exe_marker = value.lower().find(".exe")
        if exe_marker != -1:
            value = value[:exe_marker + 4]

        value = value.strip().strip('"')
        if not value:
            return []

        return PathDetector._normalize_wps_base_paths(value)

    @staticmethod
    def _normalize_wps_base_paths(path_value):
        """将路径标准化为WPS安装根目录候选。"""
        value = path_value.replace("/", "\\").strip().strip('"')
        if not value:
            return []

        if value.lower().endswith(".exe"):
            value = os.path.dirname(value)

        candidates = [value]
        parts = [part for part in value.split("\\") if part]

        # 提取 ...\Kingsoft\WPS Office 或 ...\WPS Office 作为优先根目录
        for i, segment in enumerate(parts):
            seg = segment.lower()
            if seg == "wps office":
                candidates.append("\\".join(parts[:i + 1]))
            if seg == "kingsoft" and i + 1 < len(parts) and parts[i + 1].lower() == "wps office":
                candidates.append("\\".join(parts[:i + 2]))

        # 如果路径在 office6/wps/bin 等子目录，回退到上级目录
        current = value
        for _ in range(6):
            tail = os.path.basename(current).lower()
            if tail in {"office6", "wps", "bin"} or re.fullmatch(r"\d+(\.\d+)+", tail):
                current = os.path.dirname(current)
                if current:
                    candidates.append(current)
                continue
            break

        # 去重并仅保留绝对路径
        unique_candidates = []
        seen = set()
        for item in candidates:
            normalized = os.path.normpath(item)
            if os.path.isabs(normalized) and normalized not in seen:
                seen.add(normalized)
                unique_candidates.append(normalized)

        return unique_candidates

    @staticmethod
    def _get_wps_base_paths_from_shortcuts():
        """从开始菜单和桌面快捷方式中提取WPS安装目录。"""
        if os.name != "nt":
            return []

        shortcut_roots = []
        for env_key, suffix in [
            ("ProgramData", os.path.join("Microsoft", "Windows", "Start Menu", "Programs")),
            ("APPDATA", os.path.join("Microsoft", "Windows", "Start Menu", "Programs")),
            ("PUBLIC", "Desktop"),
            ("USERPROFILE", "Desktop"),
        ]:
            base = os.environ.get(env_key, "")
            if base:
                folder = os.path.join(base, suffix)
                if os.path.isdir(folder):
                    shortcut_roots.append(folder)

        paths = []
        max_shortcuts_to_resolve = 20
        resolved_count = 0
        for root in shortcut_roots:
            patterns = [
                os.path.join(root, "**", "*WPS*.lnk"),
                os.path.join(root, "**", "*Kingsoft*.lnk"),
            ]

            shortcut_candidates = []
            for pattern in patterns:
                shortcut_candidates.extend(glob.glob(pattern, recursive=True))

            for shortcut_path in list(dict.fromkeys(shortcut_candidates)):
                if resolved_count >= max_shortcuts_to_resolve:
                    break

                target_path = PathDetector._resolve_shortcut_target(shortcut_path)
                if target_path:
                    paths.extend(PathDetector._normalize_wps_base_paths(target_path))
                resolved_count += 1

            if resolved_count >= max_shortcuts_to_resolve:
                break

        return list(dict.fromkeys(paths))

    @staticmethod
    def _resolve_shortcut_target(shortcut_path):
        """解析 .lnk 快捷方式目标路径。"""
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            "$shell = New-Object -ComObject WScript.Shell; "
            "$lnk = $shell.CreateShortcut($args[0]); "
            "if ($lnk.TargetPath) { Write-Output $lnk.TargetPath }",
            shortcut_path,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""

        if result.returncode != 0:
            return ""

        return result.stdout.strip()

    @staticmethod
    def _get_program_files_roots():
        """获取系统中可能的 Program Files 根目录列表。"""
        roots = []

        # 优先使用系统环境变量，适配 Program Files 自定义安装位置
        for env_key in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            env_path = os.environ.get(env_key, "")
            if env_path and os.path.isdir(env_path):
                roots.append(env_path)

        # 兜底扫描常见目录名，适配多盘符环境
        for drive_letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            for dir_name in ("Program Files", "Program Files (x86)"):
                candidate = f"{drive_letter}:\\{dir_name}"
                if os.path.isdir(candidate):
                    roots.append(candidate)

        return list(dict.fromkeys(roots))
    
    @staticmethod
    def _validate_wps_splash_dir(splash_dir):
        """验证WPS splash目录是否包含可替换的启动图文件
        
        Args:
            splash_dir: splash目录路径
            
        Returns:
            bool: 如果目录包含必要的文件则返回True
        """
        root_files = PathDetector._collect_wps_splash_files_in_dir(splash_dir)
        hdpi_dir = os.path.join(splash_dir, "hdpi")
        hdpi_files = PathDetector._collect_wps_splash_files_in_dir(hdpi_dir)

        # 兼容不同WPS版本目录结构：根目录或hdpi目录存在可替换文件即可
        return bool(root_files or hdpi_files)

    @staticmethod
    def _is_wps_splash_filename(filename):
        """判断文件名是否属于WPS可替换启动图。"""
        name = filename.lower()
        standard_names = {
            "splash_default_bg.png",
            "splash_sup_default_bg.png",
            "splash_wps365_default_bg.png",
        }

        if name in standard_names:
            return True

        # 支持企业版动态年份命名，例如 ent_background_2023_oem.png
        return re.fullmatch(r"ent_background_\d{4}_(oem|default)\.png", name) is not None

    @staticmethod
    def _collect_wps_splash_files_in_dir(directory):
        """收集目录内可替换的WPS启动图文件路径。"""
        if not os.path.isdir(directory):
            return []

        files = []
        try:
            for entry in os.listdir(directory):
                entry_path = os.path.join(directory, entry)
                if os.path.isfile(entry_path) and PathDetector._is_wps_splash_filename(entry):
                    files.append(entry_path)
        except (PermissionError, OSError):
            return []

        return sorted(files)
    
    @staticmethod
    def get_wps_splash_files(splash_dir):
        """获取WPS splash目录下的所有启动图文件路径
        
        Args:
            splash_dir: splash目录路径
            
        Returns:
            list: 启动图文件路径列表
        """
        if not splash_dir or not os.path.exists(splash_dir):
            return []

        files = PathDetector._collect_wps_splash_files_in_dir(splash_dir)
        files.extend(PathDetector._collect_wps_splash_files_in_dir(os.path.join(splash_dir, "hdpi")))
        return files
    
    @staticmethod
    def detect_all_wps_paths():
        """检测所有WPS路径（用于用户选择）"""
        return PathDetector.detect_wps_paths()
    
    @staticmethod
    def get_all_paths_with_info():
        """
        获取所有路径及其详细信息
        
        Returns:
            list: 包含路径信息的字典列表
        """
        all_paths = []
        
        # Banner路径
        banner_paths = PathDetector.detect_banner_paths()
        for path in banner_paths:
            # 从路径中提取用户名
            user_name = path.split('\\')[2] if len(path.split('\\')) > 2 else 'Unknown'
            all_paths.append({
                'path': path,
'type': 'Banner',
                'description': f'Banner图片 (用户: {user_name})',
                'version': 'N/A'
            })
        
        # SplashScreen路径
        splash_paths = PathDetector.get_splash_paths_by_version()
        for info in splash_paths:
            folder_prefix = "新版" if info['is_new_format'] else "旧版"
            description = f'{folder_prefix}启动图 - {info["path_type"]} (版本: {info["version"]})'
            all_paths.append({
                'path': info['path'],
                'type': 'SplashScreen',
                'description': description,
                'version': info['version']
            })
        
        return all_paths
    
    @staticmethod
    def manual_select_target_image(parent=None, app_type="seewo"):
        """
        手动选择目标图片
        
        Args:
            parent: 父窗口对象
            app_type: 应用类型，"seewo" 或 "wps"
            
        Returns:
            str: 选中的图片路径,如果取消则返回空字符串
        """
        if app_type == "wps":
            content = (
                "无法自动检测到WPS Office的启动图片目录。\n\n"
                "您可以手动选择splash目录。\n"
                "splash目录通常位于以下位置之一:\n\n"
                "1. 用户目录（最常见）:\n"
                "   C:\\Users\\[用户名]\\AppData\\Local\\Kingsoft\\WPS Office\\[版本号]\\office6\\mui\\[语言]\\resource\\splash\\\n"
                "   示例: C:\\Users\\Luminary\\AppData\\Local\\Kingsoft\\WPS Office\\12.1.0.21171\\office6\\mui\\zh_CN\\resource\\splash\\\n\n"
                "2. Program Files:\n"
                "   C:\\Program Files\\Kingsoft\\WPS Office\\office6\\mui\\[语言]\\res\\splash\\\n"
                "   或: C:\\Program Files\\Kingsoft\\WPS Office\\office6\\mui\\[语言]\\resource\\splash\\\n\n"
                "3. Program Files (x86):\n"
                "   C:\\Program Files (x86)\\Kingsoft\\WPS Office\\office6\\mui\\[语言]\\res\\splash\\\n\n"
                "splash目录需包含可替换的启动图文件，支持以下命名:\n"
                "- 标准命名: splash_default_bg.png、splash_sup_default_bg.png、splash_wps365_default_bg.png\n"
                "- 企业命名: ent_background_年份_oem.png、ent_background_年份_default.png\n"
                "根目录或 hdpi 子目录存在可替换文件即可。\n\n"
                "是否现在手动选择splash目录?"
            )
        else:
            # 创建自定义消息框
            content = (
                "无法自动检测到希沃白板的启动图片。\n\n"
                "您可以手动选择要替换的目标图片文件。\n"
                "目标图片通常位于以下位置之一:\n\n"
                "1. Banner.png:\n"
                "   C:\\Users\\[用户名]\\AppData\\Roaming\\Seewo\\EasiNote5\\Resources\\Banner\\Banner.png\n\n"
                "2. SplashScreen.png (旧版):\n"
                "   C:\\Program Files\\Seewo\\EasiNote5\\EasiNote5.xxx\\Main\\Assets\\SplashScreen.png\n\n"
                "3. SplashScreen.png (新版):\n"
                "   C:\\Program Files\\Seewo\\EasiNote5\\EasiNote5_x.x.x.xxxx\\Main\\Resources\\Startup\\SplashScreen.png\n\n"
                "是否现在手动选择目标图片?"
            )
        
        # 使用 MessageBox 创建询问对话框
        title = "手动选择目标图片" if app_type == "seewo" else "手动选择WPS启动图片"
        w = MessageBox(title, content, parent)
        if not w.exec():
            return ""
        
        # 打开文件选择对话框
        dialog_title = "选择WPS Office启动图片" if app_type == "wps" else "选择希沃白板启动图片"
        file_dialog = QFileDialog(parent, dialog_title)
        file_dialog.setNameFilter("PNG图片 (*.png);;所有文件 (*.*)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        # 设置初始目录为常见路径
        if app_type == "wps":
            initial_dir = ""
            for root in PathDetector._get_program_files_roots():
                for candidate in (
                    os.path.join(root, "Kingsoft", "WPS Office"),
                    os.path.join(root, "WPS Office"),
                ):
                    if os.path.exists(candidate):
                        initial_dir = candidate
                        break
                if initial_dir:
                    break
            if not os.path.exists(initial_dir):
                initial_dir = "C:\\"
        else:
            initial_dir = "C:\\Program Files\\Seewo\\EasiNote5"
            if not os.path.exists(initial_dir):
                initial_dir = "C:\\Program Files (x86)\\Seewo\\EasiNote5"
            if not os.path.exists(initial_dir):
                initial_dir = os.path.join(os.environ.get("APPDATA", "C:\\"), "Seewo")
            if not os.path.exists(initial_dir):
                initial_dir = "C:\\"
        
        file_dialog.setDirectory(initial_dir)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                selected_path = selected_files[0]
                
                # 验证选择的文件
                if not selected_path.lower().endswith('.png'):
                    w = MessageBox(
                        "文件类型错误",
                        "请选择PNG格式的图片文件。",
                        parent
                    )
                    w.exec()
                    return ""
                
                if not os.path.exists(selected_path):
                    w = MessageBox(
                        "文件不存在",
                        "选择的文件不存在,请重新选择。",
                        parent
                    )
                    w.exec()
                    return ""
                
                # 确认选择
                filename = os.path.basename(selected_path)
                confirm_content = (
                    f"您选择的目标图片是:\n\n{selected_path}\n\n"
                    f"文件名: {filename}\n\n"
                    "确认使用此图片作为替换目标吗?"
                )
                
                w = MessageBox("确认目标图片", confirm_content, parent)
                if w.exec():
                    return selected_path
        
        return ""
    
    @staticmethod
    def validate_target_path(path):
        """
        验证目标路径是否有效
        
        Args:
            path: 要验证的路径
            
        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not path:
            return False, "路径为空"
        
        if not os.path.exists(path):
            return False, "文件不存在"
        
        if not path.lower().endswith('.png'):
            return False, "不是PNG文件"
        
        if not os.path.isfile(path):
            return False, "不是文件"
        
        # 检查是否有读写权限
        if not os.access(path, os.R_OK):
            return False, "没有读取权限"
        
        # 检查文件大小(启动图片通常不会太小)
        file_size = os.path.getsize(path)
        if file_size < 1024:  # 小于1KB
            return False, "文件太小,可能不是有效的启动图片"
        
        return True, "路径有效"
