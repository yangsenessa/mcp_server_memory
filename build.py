import os
import sys
import subprocess
import platform
import json

def parse_input():
    # 从标准输入读取JSON字符串
    print("请输入JSON配置字符串:")
    
    # 读取所有输入行并合并
    json_lines = []
    for line in sys.stdin:
        json_lines.append(line)
    json_str = ''.join(json_lines).strip()
    
    try:
        # 检查输入是否为空
        if not json_str:
            print("错误：输入为空，请提供有效的JSON配置")
            sys.exit(1)
            
        # 尝试不同的编码方式解析JSON
        try:
            # 首先尝试直接解析
            config = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # 尝试处理UTF-8 BOM
                config = json.loads(json_str.encode('utf-8').decode('utf-8-sig'))
            except:
                # 尝试修复常见的JSON格式问题
                json_str = json_str.replace("'", '"')  # 将单引号替换为双引号
                config = json.loads(json_str)
        
        # 设置默认值
        args = {
            'main_file': config.get('main_file', ''),
            'packages': config.get('packages', ['pyinstaller', 'openai']),
            'pyinstaller_args': config.get('pyinstaller_args', ['--onefile', '--hidden-import=openai']),
            'binary_dir': config.get('binary_dir', 'bin'),
            'data_paths': config.get('data_paths', [])
        }
        
        # 验证必要参数
        if not args['main_file']:
            raise ValueError("必须提供main_file参数")
            
        # 处理pyinstaller_args中的引号
        if args['pyinstaller_args']:
            args['pyinstaller_args'] = [arg.strip('"').strip("'") for arg in args['pyinstaller_args']]
        
        return args
    except json.JSONDecodeError as e:
        print(f"错误：{str(e)}")
        print(f"接收到的输入内容：\n{json_str[:100]}...")  # 打印部分输入内容以便调试
        sys.exit(1)
    except ValueError as e:
        print(f"错误：{str(e)}")
        sys.exit(1)

def create_venv(args):
    # 使用主文件名（不含扩展名）作为虚拟环境名称前缀
    venv_name = f"venv_{os.path.splitext(args['main_file'])[0]}"
    
    # 检查是否已存在虚拟环境
    if not os.path.exists(venv_name):
        print(f"正在创建虚拟环境 {venv_name}...")
        subprocess.check_call([sys.executable, '-m', 'venv', venv_name])
    
    # 根据操作系统确定Python解释器路径
    if platform.system() == 'Windows':
        python_path = os.path.join(venv_name, 'Scripts', 'python.exe')
        pip_path = os.path.join(venv_name, 'Scripts', 'pip.exe')
    else:
        python_path = os.path.join(venv_name, 'bin', 'python')
        pip_path = os.path.join(venv_name, 'bin', 'pip')

    # 安装必要的包
    print("正在安装必要的包...")
    tsinghua_mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
   
    # 安装所有必需的包
    for package in args['packages']:
        subprocess.check_call([pip_path, 'install', package, '-i', tsinghua_mirror])

    print("环境设置完成！")
    print(f"开始打包{args['main_file']}...")
    
    # 执行PyInstaller打包命令
    try:
        
        # 准备PyInstaller命令参数
        pyinstaller_args = [
            python_path, 
            '-m', 
            'PyInstaller',
            f'--name={os.path.splitext(args["main_file"])[0]}',
            *args['pyinstaller_args'],
        ]
        
        # 添加用户指定的数据路径
        for data_path in args['data_paths']:
            pyinstaller_args.append(f'--add-data={data_path}')
            
        # 添加主程序文件
        pyinstaller_args.append(args['main_file'])
        
        # 执行PyInstaller命令
        subprocess.check_call(pyinstaller_args)
        print(f"打包完成！请查看dist目录下的{os.path.splitext(args['main_file'])[0]}可执行文件。")
    except subprocess.CalledProcessError as e:
        print(f"打包过程中出现错误：{e}")
    except ImportError as e:
        print(f"无法导入模块，请确保它已正确安装: {e}")

if __name__ == '__main__':
    args = parse_input()
    create_venv(args)
