import os

build_path="build.py"
build_md_path="build.md"
app_path="mcp_server_memory.py"
app_name=os.path.basename(app_path)

prompt=f'''
为 {app_name} 创建打包命令,根据我提供的 {build_md_path} 文档和 {app_path} 文件，生成使用 {build_path} 打包 {app_path} 的命令行参数建议。

只需要输出JSON配置给我，不要输出任何其他内容。
----------
{build_md_path} 文件内容:
{open(build_md_path).read()}
----------
{app_path} 文件内容:
{open(app_path).read()}
----------
'''

print('#prompt\n',prompt)
