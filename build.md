# Python 程序打包工具

这是一个简单的 Python 程序打包工具，可以帮助您将 Python 程序打包成独立的可执行文件。该工具使用 PyInstaller 进行打包，并自动创建虚拟环境以确保依赖项的隔离。

## 功能特点

- 自动创建虚拟环境
- 自动安装所需依赖包
- 使用 PyInstaller 打包成独立可执行文件
- 支持添加额外数据文件
- 支持自定义 PyInstaller 参数

## 使用方法

### 基本用法

```bash
cat memory_mcp.json | python build.py
```

### 高级用法

```json
{
  "main_file": "your_main_file.py",
  "packages": ["pyinstaller", "openai", "package1", "package2"],
  "pyinstaller_args": ["--onefile", "--windowed"],
  "data_paths": ["source_path:dest_path"]
}
```

### 参数说明

main_file：要打包的主程序文件名（必需）
packages：要安装的包列表（默认包含 pyinstaller、openai）
pyinstaller_args：传递给 PyInstaller 的参数
默认参数：--onefile、--hidden-import=openai
binary_dir：可执行文件的目标目录路径（默认为 bin）
data_paths：要添加的数据文件路径，格式为 源路径:目标路径

### 打包带有额外依赖的程序

```json 
{
  "main_file": "app.py",
  "packages": ["pyinstaller", "openai", "numpy", "pandas", "matplotlib"],
  "data_paths": ["data/config.json:.", "resources/:resources"]
}
```

### 自定义 PyInstaller 参数
```json
{
  "main_file": "app.py",
  "pyinstaller_args": ["--onefile", "--windowed", "--icon=app_icon.ico"]
}
```

## 注意事项

- 该工具默认使用清华大学镜像源安装 Python 包
- 打包完成后的可执行文件将位于 `dist` 目录下
- 虚拟环境将以 `venv_[主文件名]` 的形式创建在当前目录下
- 打包后的程序名称将与主文件名相同（不含扩展名）

## 系统要求

- Python 3.6 或更高版本
- 支持 Windows、macOS 和 Linux 系统

