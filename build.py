import sys
import os
import shutil
import subprocess
import argparse
import tempfile
import zipfile
from importlib import metadata
from pathlib import Path
from core.app_info import __version__, __author__, __app_name__, get_version_string


def _detect_vsdevcmd_path():
    """自动探测 Visual Studio 的 VsDevCmd.bat 路径。"""
    candidates = []

    # 1) 优先通过 vswhere 查询最新安装
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        try:
            result = subprocess.run(
                [
                    str(vswhere),
                    "-latest",
                    "-products",
                    "*",
                    "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "-property",
                    "installationPath",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            install_path = result.stdout.strip()
            if install_path:
                candidates.append(Path(install_path) / "Common7" / "Tools" / "VsDevCmd.bat")
        except Exception:
            pass

    # 2) 兼容常见安装目录
    base_roots = [
        Path(r"C:\Program Files\Microsoft Visual Studio"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio"),
    ]
    for base in base_roots:
        if base.exists():
            candidates.extend(base.glob("*/*/Common7/Tools/VsDevCmd.bat"))

    # 3) 使用第一个有效路径
    for path in candidates:
        if path.exists():
            return str(path)

    return None


DEFAULT_VSDEVCMD = _detect_vsdevcmd_path()
# 仅需修改这里即可切换默认构建后端: "nuitka" 或 "pyinstaller"
DEFAULT_BACKEND = "nuitka"


class Builder:
    """应用打包构建器"""
    
    def __init__(self, backend=DEFAULT_BACKEND, nuitka_jobs=2, nuitka_mode="onefile", vsdevcmd=None):
        self.root_dir = Path(__file__).parent
        self.dist_dir = self.root_dir / "dist"
        self.nuitka_build_dir = self.root_dir / "nuitka_build"
        self.build_dir = self.root_dir / "build"
        self.app_name = __app_name__
        self.version = __version__
        self.author = __author__
        self.main_script = "main.py"
        self.version_file = None  # 版本信息文件路径
        self.backend = backend
        self.nuitka_jobs = nuitka_jobs
        self.nuitka_mode = nuitka_mode
        normalized_vsdevcmd = (vsdevcmd or DEFAULT_VSDEVCMD or "").strip()
        # Tolerate pasted inputs like \"C:\\...\\VsDevCmd.bat\"
        normalized_vsdevcmd = normalized_vsdevcmd.replace('\\"', '"').strip()
        if (normalized_vsdevcmd.startswith('"') and normalized_vsdevcmd.endswith('"')) or (
            normalized_vsdevcmd.startswith("'") and normalized_vsdevcmd.endswith("'")
        ):
            normalized_vsdevcmd = normalized_vsdevcmd[1:-1].strip()
        self.vsdevcmd = Path(normalized_vsdevcmd) if normalized_vsdevcmd else None
        
    def clean(self):
        """清理之前的构建文件"""
        print("=" * 60)
        print("步骤 1: 清理旧的构建文件...")
        print("=" * 60)
        
        dirs_to_clean = [self.dist_dir, self.nuitka_build_dir, self.build_dir]
        
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                print(f"正在删除: {dir_path}")
                shutil.rmtree(dir_path, ignore_errors=True)
        
        # 删除 .spec 文件
        spec_files = list(self.root_dir.glob("*.spec"))
        for spec_file in spec_files:
            print(f"正在删除: {spec_file}")
            spec_file.unlink()
        
        # 删除旧的版本信息文件
        old_version_file = self.root_dir / "version_info.txt"
        if old_version_file.exists():
            print(f"正在删除旧的版本信息文件: {old_version_file}")
            old_version_file.unlink()

        # 删除根目录下可能残留的旧可执行文件
        for old_exe_name in [f"{self.app_name}.exe", "main.exe"]:
            old_exe = self.root_dir / old_exe_name
            if old_exe.exists():
                print(f"正在删除旧的可执行文件: {old_exe}")
                old_exe.unlink()
        
        print("✓ 清理完成\n")
    
    def check_dependencies(self):
        """检查依赖"""
        print("=" * 60)
        print("步骤 2: 检查依赖...")
        print("=" * 60)
        
        if self.backend == "pyinstaller":
            try:
                import PyInstaller
                print(f"✓ PyInstaller 版本: {PyInstaller.__version__}")
            except ImportError:
                print("✗ PyInstaller not installed.")
                print("Installing PyInstaller...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
                print("✓ PyInstaller installed")
        else:
            try:
                nuitka_version = metadata.version("Nuitka")
                print(f"✓ Nuitka 版本: {nuitka_version}")
            except metadata.PackageNotFoundError:
                print("✗ Nuitka not installed.")
                print("Installing Nuitka...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"])
                print("✓ Nuitka installed")
        
        try:
            import PyQt5
            print(f"✓ PyQt5 已安装")
        except ImportError:
            print("✗ PyQt5 is not installed. Please install it first: pip install PyQt5")
            sys.exit(1)
        
        print("✓ 依赖检查完成\n")
    
    def create_version_file(self):
        """生成版本信息文件"""
        print("=" * 60)
        print("步骤 3: 生成版本信息文件...")
        print("=" * 60)
        
        try:
            # 导入并运行版本文件生成器
            from create_version_file import create_version_file
            self.version_file = create_version_file()
            print("✓ 版本信息文件生成完成\n")
            return True
        except Exception as e:
            print(f"⚠ 生成版本信息文件失败: {e}")
            print("  将继续构建，但 exe 文件将不包含版本信息\n")
            return False
    
    def create_icon(self):
        """创建/检查图标文件"""
        print("=" * 60)
        print("步骤 4: 检查图标文件...")
        print("=" * 60)
        
        icon_path = self.root_dir / "assets" / "icon.ico"
        
        if not icon_path.exists():
            print(f"⚠ 未找到图标文件: {icon_path}")
            print("  将使用默认图标")
            return None
        else:
            print(f"✓ 找到图标文件: {icon_path}")
            return str(icon_path)
    
    def collect_data_files(self):
        """收集需要打包的数据文件"""
        print("=" * 60)
        print("步骤 5: 收集数据文件...")
        print("=" * 60)
        
        data_files = []
        if self.backend == "nuitka":
            assets_dir = self.root_dir / "assets"
            presets_dir = assets_dir / "presets"
            if presets_dir.exists():
                data_files.append((str(presets_dir), "assets/presets"))
                print(f"✓ 添加预设图片目录: {presets_dir}")
            else:
                print(f"⚠ 未找到预设图片目录: {presets_dir}")
        else:
            separator = ";" if sys.platform == "win32" else ":"
            
            # 只打包 assets/presets 目录（预设图片）
            presets_dir = self.root_dir / "assets" / "presets"
            if presets_dir.exists():
                data_files.append((str(presets_dir), "assets/presets"))
                print(f"✓ 添加预设图片目录: {presets_dir}")

            # 打包 assets/icon.ico 图标
            icon_dir = self.root_dir / "assets" / "icon.ico"
            if icon_dir.exists():
                data_files.append((str(icon_dir), "assets/"))
                print(f"✓ 添加图标: {icon_dir}")
                
            # 统计预设图片数量
                image_files = list(presets_dir.glob("*.png"))
                print(f"  共找到 {len(image_files)} 个预设图片")
                for img in image_files:
                    print(f"    - {img.name}")
            else:
                print(f"⚠ 未找到预设图片目录: {presets_dir}")
            
            # 不打包 images/custom 目录（用户自定义图片目录，运行时创建）
            custom_dir = self.root_dir / "images" / "custom"
            if custom_dir.exists():
                print(f"⚠ 跳过自定义图片目录: {custom_dir} (运行时创建)")
        
        if not data_files:
            print("⚠ 未找到需要打包的数据文件")
        
        print(f"✓ 数据文件收集完成\n")
        return data_files

    def _build_pyinstaller(self):
        print("=" * 60)
        print("步骤 6: 开始打包（PyInstaller）...")
        print("=" * 60)
        
        icon_path = self.create_icon()
        data_files = self.collect_data_files()
        
        pyinstaller_args = [
            "pyinstaller",
            "--name", self.app_name,
            "--onedir",
            "--windowed",
            "--clean",
            "--noconfirm",
        ]
        
        if icon_path:
            pyinstaller_args.extend(["--icon", icon_path])
        
        if self.version_file and self.version_file.exists():
            pyinstaller_args.extend(["--version-file", str(self.version_file)])
            print(f"✓ 使用版本信息文件: {self.version_file}")
        
        separator = ";" if sys.platform == "win32" else ":"
        for src, dst in data_files:
            pyinstaller_args.extend(["--add-data", f"{src}{separator}{dst}"])
        
        excludes = [
            "PyQt5.QtWebEngineCore",
            "PyQt5.QtWebEngineWidgets",
            "PyQt5.QtWebEngine",
            "PyQt5.QtMultimedia",
            "PyQt5.QtMultimediaWidgets",
            "PyQt5.QtNetwork",
            "PyQt5.QtSql",
            "PyQt5.QtTest",
            "PyQt5.QtDBus",
            "PyQt5.QtBluetooth",
            "PyQt5.QtNfc",
            "PyQt5.QtPositioning",
            "PyQt5.QtWebChannel",
            "PyQt5.QtWebSockets",
            "PyQt5.Qt3DCore",
            "PyQt5.Qt3DRender",
            "PyQt5.Qt3DInput",
            "PyQt5.Qt3DLogic",
            "PyQt5.Qt3DAnimation",
            "PyQt5.Qt3DExtras",
            "pyinstaller",
            "setuptools",
        ]
        
        for module in excludes:
            pyinstaller_args.extend(["--exclude-module", module])
        
        pyinstaller_args.append(str(self.main_script))
        
        print("\n执行命令:")
        print(" ".join(pyinstaller_args))
        print()
        
        try:
            subprocess.check_call(pyinstaller_args)
            print("\n✓ 打包完成")
        except subprocess.CalledProcessError as e:
            print(f"\n✗ 打包失败: {e}")
            sys.exit(1)

    def _build_nuitka(self):
        print("=" * 60)
        print("Step 6: Building with Nuitka...")
        print("=" * 60)

        icon_path = self.create_icon()
        self.collect_data_files()

        nuitka_args = [
            sys.executable,
            "-m",
            "nuitka",
            "--mode=onefile" if self.nuitka_mode == "onefile" else "--mode=standalone",
            f"--output-dir={self.nuitka_build_dir}",
            f"--output-filename={self.app_name}.exe",
            "--low-memory",
            f"--jobs={self.nuitka_jobs}",
            "--windows-console-mode=disable",
            "--enable-plugin=pyqt5",
            "--include-qt-plugins=sensible,styles",
            "--include-data-dir=assets/presets=assets/presets",
            "--noinclude-pytest-mode=nofollow",
            "--noinclude-unittest-mode=nofollow",
            "--nofollow-import-to=scipy",
            "--nofollow-import-to=qfluentwidgets.common.image_utils",
            "--nofollow-import-to=PyQt5.QtWebEngineCore",
            "--nofollow-import-to=PyQt5.QtWebEngineWidgets",
            "--nofollow-import-to=PyQt5.QtWebEngine",
            "--nofollow-import-to=PyQt5.QtWebChannel",
            "--nofollow-import-to=PyQt5.QtWebSockets",
            "--nofollow-import-to=PyQt5.QtMultimedia",
            "--nofollow-import-to=PyQt5.QtMultimediaWidgets",
            "--nofollow-import-to=PyQt5.QtNetwork",
            "--nofollow-import-to=PyQt5.QtSql",
            "--nofollow-import-to=PyQt5.QtTest",
            "--nofollow-import-to=PyQt5.QtDBus",
            "--nofollow-import-to=PyQt5.QtBluetooth",
            "--nofollow-import-to=PyQt5.QtNfc",
            "--nofollow-import-to=PyQt5.QtPositioning",
            "--nofollow-import-to=PyQt5.Qt3DCore",
            "--nofollow-import-to=PyQt5.Qt3DRender",
            "--nofollow-import-to=PyQt5.Qt3DInput",
            "--nofollow-import-to=PyQt5.Qt3DLogic",
            "--nofollow-import-to=PyQt5.Qt3DAnimation",
            "--nofollow-import-to=PyQt5.Qt3DExtras",
            str(self.main_script),
        ]

        if icon_path:
            nuitka_args.insert(8, f"--include-data-files={icon_path}=assets/icon.ico")
            nuitka_args.insert(9, "--windows-icon-from-ico=assets/icon.ico")

        if self.version_file and self.version_file.exists():
            print(f"✓ Version file generated: {self.version_file}")

        if self.vsdevcmd and self.vsdevcmd.exists():
            nuitka_args.insert(6, "--msvc=latest")
            build_env = self._load_vsdevcmd_env()
            print(f"✓ 编译器: MSVC ({self.vsdevcmd})")
        else:
            # 无 MSVC 时回退 MinGW64，提升在 CI/Actions 环境的可用性。
            nuitka_args.insert(6, "--mingw64")
            build_env = dict(os.environ)
            print("⚠ 未检测到可用的 VsDevCmd.bat，已回退到 MinGW64 构建。")
            print("  若在 GitHub Actions 使用 Zig，可安装 Zig 后设置:")
            print("  CC='zig cc'  CXX='zig c++'")

        print("\nExecuting command:")
        print(" ".join(f'"{arg}"' if " " in arg else arg for arg in nuitka_args))
        print()

        try:
            subprocess.check_call(nuitka_args, env=build_env)
            print("\n✓ Nuitka build completed")
        except subprocess.CalledProcessError as e:
            print(f"\n✗ Nuitka build failed: {e}")
            sys.exit(1)

    def _get_release_dir(self):
        """获取当前后端的发布目录。"""
        return self.dist_dir / self.app_name

    def _prepare_release_bundle(self):
        """准备发布目录：可执行文件 + 文档 + 运行所需空目录。"""
        print("\n" + "=" * 60)
        print("步骤 9: 准备发布目录...")
        print("=" * 60)

        release_dir = self._get_release_dir()

        if self.backend == "nuitka" and self.nuitka_mode == "onefile":
            exe_path = self.nuitka_build_dir / f"{self.app_name}.exe"
            if not exe_path.exists():
                print(f"✗ 未找到可执行文件: {exe_path}")
                return None

            if release_dir.exists():
                shutil.rmtree(release_dir, ignore_errors=True)

            release_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(exe_path, release_dir / exe_path.name)
            print(f"✓ 已复制可执行文件: {release_dir / exe_path.name}")
        elif not release_dir.exists():
            print(f"✗ 输出目录不存在: {release_dir}")
            return None

        # 添加分发文档
        for doc_name in ["README.md", "LICENSE"]:
            src = self.root_dir / doc_name
            dst = release_dir / doc_name
            if src.exists():
                shutil.copy2(src, dst)
                print(f"✓ 已添加文档: {dst.name}")

        # 创建运行时目录，避免用户在其他位置启动时新建目录造成困惑
        runtime_dirs = [
            release_dir / "images" / "custom",
            release_dir / "backups",
        ]
        for directory in runtime_dirs:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ 已创建目录: {directory.relative_to(release_dir)}")

        return release_dir

    def _zip_dir_with_empty_dirs(self, source_dir: Path, zip_file: Path):
        """压缩目录并保留空目录条目。"""
        with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            base_dir = source_dir.parent
            for root, dirs, files in os.walk(source_dir):
                root_path = Path(root)
                rel_root = root_path.relative_to(base_dir).as_posix()

                if not dirs and not files:
                    zf.writestr(rel_root + "/", "")

                for filename in files:
                    file_path = root_path / filename
                    arcname = file_path.relative_to(base_dir).as_posix()
                    zf.write(file_path, arcname)

    def _load_vsdevcmd_env(self):
        """加载 VsDevCmd.bat 设置后的环境变量。"""
        temp_cmd_path = None
        cmd_content = (
            "@echo off\n"
            f'call "{self.vsdevcmd}" -arch=x64 -host_arch=x64 >nul\n'
            "if errorlevel 1 exit /b 1\n"
            "set\n"
        )

        try:
            with tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False, encoding="utf-8") as temp_cmd:
                temp_cmd.write(cmd_content)
                temp_cmd_path = temp_cmd.name

            result = subprocess.run(
                ["cmd", "/d", "/c", temp_cmd_path],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to load Visual Studio environment from: {self.vsdevcmd}")
            print("Please verify the path and Visual Studio installation.")
            if e.stderr:
                print("\n[VsDevCmd stderr]")
                print(e.stderr.strip())
            elif e.stdout:
                print("\n[VsDevCmd output]")
                print(e.stdout.strip())
            sys.exit(1)
        finally:
            if temp_cmd_path and os.path.exists(temp_cmd_path):
                try:
                    os.remove(temp_cmd_path)
                except OSError:
                    pass

        env = dict(os.environ)
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key:
                env[key] = value
        return env
    
    def build(self):
        """执行打包"""
        if self.backend == "nuitka":
            self._build_nuitka()
        else:
            self._build_pyinstaller()
    
    def post_build(self):
        """打包后处理"""
        print("\n" + "=" * 60)
        print("步骤 7: 打包后处理...")
        print("=" * 60)
        
        # 在目录模式下，可执行文件在 dist/应用名/ 目录下
        exe_dir = self.dist_dir / self.app_name
        
        if not exe_dir.exists():
            print(f"✗ 未找到输出目录: {exe_dir}")
            return
        
        # 创建必要的目录结构（在可执行文件目录外部）
        dirs_to_create = [
            exe_dir / "images" / "custom",  # 自定义图片目录
            exe_dir / "backups",             # 备份目录
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ 创建目录: {dir_path.relative_to(self.dist_dir)}")
        
        # # 创建版本信息文件
        # version_file = exe_dir / "VERSION.txt"
        # with open(version_file, "w", encoding="utf-8") as f:
        #     f.write(f"{self.app_name} v{self.version}\n")
        #     f.write(f"作者: {self.author}\n")
        #     f.write(f"构建时间: {self._get_build_time()}\n")
        
        # print(f"✓ 创建版本信息: {version_file.relative_to(self.dist_dir)}")
        
        # 验证预设图片是否正确复制
        preset_dir = exe_dir / "_internal" / "assets" / "presets"
        if preset_dir.exists():
            image_files = list(preset_dir.glob("*.png"))
            print(f"✓ 预设图片验证: 共 {len(image_files)} 个文件")
            for img in image_files:
                print(f"    - {img.name}")
        else:
            print(f"⚠ 警告: 预设图片目录不存在: {preset_dir}")
        
        print("✓ 后处理完成\n")
    
    def _get_build_time(self):
        """获取构建时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def verify_version_info(self):
        """验证版本信息是否写入成功"""
        print("=" * 60)
        print("步骤 8: 验证版本信息...")
        print("=" * 60)
        
        exe_path = self.dist_dir / self.app_name / f"{self.app_name}.exe"
        
        if not exe_path.exists():
            print(f"✗ 可执行文件不存在: {exe_path}")
            return
        
        print(f"✓ 可执行文件: {exe_path}")
        print(f"\n如何查看版本信息:")
        print(f"  1. 右键点击 {self.app_name}.exe")
        print(f"  2. 选择 '属性'")
        print(f"  3. 切换到 '详细信息' 标签页")
        print(f"  4. 查看文件版本、产品名称、版权等信息")
        print(f"\n预期显示:")
        print(f"  文件描述: 希沃白板启动图片自定义工具")
        print(f"  产品名称: {self.app_name}")
        print(f"  产品版本: {self.version}")
        print(f"  版权: Copyright © {self._get_current_year()} {self.author}")
        print()
    
    def _get_current_year(self):
        """获取当前年份"""
        from datetime import datetime
        return datetime.now().year
    
    def show_result(self):
        """显示打包结果"""
        print("=" * 60)
        print("打包完成!")
        print("=" * 60)

        if self.backend == "nuitka":
            if self.nuitka_mode == "onefile":
                exe_path = self.nuitka_build_dir / f"{self.app_name}.exe"
                if exe_path.exists():
                    size_mb = exe_path.stat().st_size / (1024 * 1024)
                    print(f"\n应用信息:")
                    print(f"  名称: {self.app_name}")
                    print(f"  版本: {self.version}")
                    print(f"  作者: {self.author}")
                    print(f"  构建时间: {self._get_build_time()}")
                    print(f"\n输出信息:")
                    print(f"  可执行文件: {exe_path}")
                    print(f"  总大小: {size_mb:.2f} MB")
                else:
                    print(f"\n✗ 未找到可执行文件: {exe_path}")
            else:
                exe_dir = self.nuitka_build_dir / f"{self.app_name}.dist"
                exe_path = exe_dir / f"{self.app_name}.exe"
                if exe_path.exists():
                    total_size = sum(f.stat().st_size for f in exe_dir.rglob('*') if f.is_file())
                    size_mb = total_size / (1024 * 1024)
                    print(f"\n应用信息:")
                    print(f"  名称: {self.app_name}")
                    print(f"  版本: {self.version}")
                    print(f"  作者: {self.author}")
                    print(f"  构建时间: {self._get_build_time()}")
                    print(f"\n输出信息:")
                    print(f"  可执行文件: {exe_path}")
                    print(f"  输出目录: {exe_dir}")
                    print(f"  总大小: {size_mb:.2f} MB")
                else:
                    print(f"\n✗ 未找到可执行文件: {exe_path}")
            return

        exe_dir = self.dist_dir / self.app_name
        exe_path = exe_dir / f"{self.app_name}.exe"

        if exe_path.exists():
            # 计算整个目录的大小
            total_size = sum(f.stat().st_size for f in exe_dir.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)

            print(f"\n应用信息:")
            print(f"  名称: {self.app_name}")
            print(f"  版本: {self.version}")
            print(f"  作者: {self.author}")
            print(f"  构建时间: {self._get_build_time()}")

            print(f"\n输出信息:")
            print(f"  可执行文件: {exe_path.relative_to(self.dist_dir)}")
            print(f"  输出目录: {exe_dir}")
            print(f"  总大小: {size_mb:.2f} MB")

            # 显示目录结构
            print(f"\n目录结构:")
            print(f"{self.app_name}/")
            print(f"├── {self.app_name}.exe           # 主程序（包含版本信息）")
            # print(f"├── VERSION.txt                   # 版本信息文本")
            print(f"├── _internal/                    # 运行时依赖（不要删除）")
            print(f"│   └── assets/")
            print(f"│       └── presets/              # 预设图片（只读）")
            print(f"├── images/")
            print(f"│   └── custom/                   # 自定义图片（可写）")
            print(f"├── backups/                       # 备份目录（可写）")
            print(f"└── config.json                   # 配置文件（运行后生成）")

            print(f"\n分发说明:")
            print(f"将整个 '{self.app_name}' 目录打包分发给用户")
            print(f"  用户只需解压后运行 {self.app_name}.exe 即可")

        else:
            print(f"\n✗ 未找到可执行文件: {exe_path}")
    
    def create_zip(self, release_dir=None):
        """创建分发包"""
        print("\n" + "=" * 60)
        print("步骤 10: 创建分发包...")
        print("=" * 60)

        target_dir = Path(release_dir) if release_dir else self._get_release_dir()

        if not target_dir.exists():
            print("✗ 输出目录不存在，跳过")
            return

        try:
            # 使用版本号作为文件名
            zip_name = f"{self.app_name}_v{self.version}"
            zip_file = self.dist_dir / f"{zip_name}.zip"

            print(f"正在创建压缩包: {zip_name}.zip")
            self._zip_dir_with_empty_dirs(target_dir, zip_file)

            if zip_file.exists():
                size_mb = zip_file.stat().st_size / (1024 * 1024)
                print(f"✓ 压缩包创建成功: {zip_file}")
                print(f"  大小: {size_mb:.2f} MB")
                print(f"  版本: v{self.version}")
            
        except Exception as e:
            print(f"⚠ 创建压缩包失败: {e}")
    
    def run(self):
        """运行完整构建流程"""
        print("\n" + "=" * 60)
        print(f"开始构建: {get_version_string()}")
        print(f"作者: {self.author}")
        print(f"后端: {self.backend}")
        if self.backend == "nuitka":
            print(f"Nuitka mode: {self.nuitka_mode}")
            print(f"Nuitka jobs: {self.nuitka_jobs}")
        print("=" * 60 + "\n")
        
        try:
            self.clean()
            self.check_dependencies()
            self.create_version_file()  # 新增：生成版本信息文件
            self.build()
            if self.backend == "pyinstaller":
                self.post_build()
                self.verify_version_info()  # 新增：验证版本信息
                self.show_result()
                release_dir = self._prepare_release_bundle()
                self.create_zip(release_dir)
            else:
                self.show_result()
                release_dir = self._prepare_release_bundle()
                self.create_zip(release_dir)
            
            print("\n" + "=" * 60)
            print("构建流程全部完成! ✓")
            print("=" * 60 + "\n")
            
        except Exception as e:
            print(f"\n✗ 构建失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build SeewoSplash")
    parser.add_argument("--backend", choices=["pyinstaller", "nuitka"], default=DEFAULT_BACKEND)
    parser.add_argument("--nuitka-mode", choices=["onefile", "standalone"], default="onefile")
    parser.add_argument("--nuitka-jobs", type=int, default=2)
    parser.add_argument("--vsdevcmd", default=DEFAULT_VSDEVCMD)
    parser.add_argument("--interactive", action="store_true", help="使用中文交互模式")
    args = parser.parse_args()

    def _ask(prompt_text, default_value=None):
        if default_value is None:
            value = input(f"{prompt_text}: ").strip()
            return value
        value = input(f"{prompt_text} [{default_value}]: ").strip()
        return value if value else str(default_value)

    interactive_mode = args.interactive

    if interactive_mode:
        print("\n" + "=" * 60)
        print("SeewoSplash 构建向导（中文交互）")
        print("=" * 60)

        default_backend_choice = "1" if DEFAULT_BACKEND == "pyinstaller" else "2"
        backend_input = _ask("选择构建后端 (1=PyInstaller, 2=Nuitka)", default_backend_choice)
        backend = "nuitka" if backend_input == "2" else "pyinstaller"

        nuitka_mode = "onefile"
        nuitka_jobs = 2
        vsdevcmd = args.vsdevcmd

        if backend == "nuitka":
            mode_input = _ask("Nuitka 打包模式 (1=onefile, 2=standalone)", "1")
            nuitka_mode = "standalone" if mode_input == "2" else "onefile"

            jobs_input = _ask("Nuitka 并发 jobs", "2")
            try:
                nuitka_jobs = max(1, int(jobs_input))
            except ValueError:
                nuitka_jobs = 2

            vsdevcmd = _ask("VS 开发者命令脚本路径", args.vsdevcmd)

            print("\n提示: Python 会自动通过 cmd 调用 VsDevCmd.bat 后再运行 Nuitka。")
            print("无需手动先开 VS 开发者命令行。\n")
        else:
            print("\n将使用 PyInstaller 默认流程。\n")

        args.backend = backend
        args.nuitka_mode = nuitka_mode
        args.nuitka_jobs = nuitka_jobs
        args.vsdevcmd = vsdevcmd

    builder = Builder(
        backend=args.backend,
        nuitka_jobs=args.nuitka_jobs,
        nuitka_mode=args.nuitka_mode,
        vsdevcmd=args.vsdevcmd,
    )
    builder.run()
