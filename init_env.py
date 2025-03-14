import os
import subprocess
import sys
import venv
from pathlib import Path

def create_venv(venv_path: str = ".venv"):
    """
    创建虚拟环境
    
    Args:
        venv_path (str): 虚拟环境路径
    """
    print(f"正在创建虚拟环境在: {venv_path}")
    venv.create(venv_path, with_pip=True)

def get_python_executable(venv_path: str = ".venv"):
    """
    获取虚拟环境中的Python可执行文件路径
    """
    if sys.platform == "win32":
        python_path = os.path.join(venv_path, "Scripts", "python.exe")
    else:
        python_path = os.path.join(venv_path, "bin", "python")
    return python_path

def install_requirements(python_path: str):
    """
    安装所需的依赖包
    """
    requirements = [
        "mcp",
    ]
    
    print("正在安装依赖包...")
    for package in requirements:
        print(f"安装 {package}...")
        subprocess.run([
            python_path, 
            "-m", 
            "pip", 
            "install", 
            package,
            "-i", 
            "https://pypi.tuna.tsinghua.edu.cn/simple"
        ])

def main():
    """
    主函数：创建虚拟环境并安装依赖
    """
    # 检查Python版本
    if sys.version_info < (3, 10):
        print("错误：需要Python 3.10或更高版本")
        print(f"当前Python版本: {sys.version.split()[0]}")
        return
        
    venv_path = ".venv"
    
    # 检查虚拟环境是否已存在
    if Path(venv_path).exists():
        print("虚拟环境已存在。是否要删除并重新创建？(y/n)")
        response = input().lower()
        if response == 'y':
            import shutil
            shutil.rmtree(venv_path)
        else:
            print("使用现有虚拟环境...")
            return

    # 创建虚拟环境
    create_venv(venv_path)
    
    # 获取Python可执行文件路径
    python_path = get_python_executable(venv_path)
    
    # 安装依赖包
    install_requirements(python_path)
    
    print("\n环境设置完成！")
    print(f"要激活虚拟环境，请运行：")
    if sys.platform == "win32":
        print(f"    {venv_path}\\Scripts\\activate")
    else:
        print(f"    source {venv_path}/bin/activate")

if __name__ == "__main__":
    main() 