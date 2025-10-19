# generate_index.py
import os
import re

# --- 配置 ---
# 1. 存放 summary html 文件的目录
summary_dir = "summary_htmls"

# 2. 生成的 index.html 的完整路径
output_file = "index.html"

# 3. HTML 页面标题和头部
page_title = "文档索引 | Xiaoqi's Archive"
page_header = "文档索引"


# --- 脚本主体 ---
def parse_filename(filename):
    """
    解析 "作者 (年份) 标题.html" 格式的文件名。
    返回一个包含 (作者, 年份, 标题) 的元组，如果格式不匹配则返回 None。
    """
    # 去掉 .html 后缀
    base_name = os.path.splitext(filename)[0]
    
    # 使用正则表达式来匹配 "作者 (年份) 标题"
    # - (.*?)       -> 非贪婪匹配作者部分
    # - \s*\(       -> 匹配年份前的空格和左括号
    # - (\d{4})     -> 匹配四位数的年份
    # - \)\s* -> 匹配右括号和后面的空格
    # - (.*)        -> 匹配剩余的所有字符作为标题
    match = re.match(r'(.*?)\s*\((\d{4})\)\s*(.*)', base_name)
    
    if match:
        author = match.group(1).strip()
        year = match.group(2).strip()
        title = match.group(3).strip()
        return author, year, title
    else:
        # 如果不匹配，返回 None
        return None

def generate_index_page():
    """
    扫描 summary_htmls 文件夹并生成一个带链接的 index.html。
    """
    # 目标文件夹的完整路径
    summary_path = os.path.join(os.getcwd(), summary_dir)

    # 检查文件夹是否存在
    if not os.path.isdir(summary_path):
        print(f"错误：找不到目录 '{summary_path}'。请确保脚本在正确的路径下运行，并且 '{summary_dir}' 文件夹存在。")
        return

    # 获取目标文件夹下所有的 html 文件并按字母顺序排序
    try:
        files = sorted([f for f in os.listdir(summary_path) if f.endswith('.html')])
    except FileNotFoundError:
        print(f"错误：扫描目录 '{summary_path}' 时出错。")
        return

    list_items = []
    print(f"在 '{summary_dir}' 文件夹中找到 {len(files)} 个 HTML 文件，开始处理...")

    for filename in files:
        parsed_info = parse_filename(filename)
        
        if parsed_info:
            author, year, title = parsed_info
            
            # 格式化显示的文本
            display_text = f"{author} ({year}) {title}"
            
            # 构建超链接的相对路径
            # index.html 在根目录，所以链接路径是 "summary_htmls/文件名.html"
            href = os.path.join(summary_dir, filename)
            
            # 生成 HTML 列表项
            list_items.append(f'<li><a href="{href}">{display_text}</a></li>')
            print(f"  -> 已处理: {filename}")
        else:
            print(f"  -> 跳过格式不正确的文件: {filename}")

    # --- 生成完整的 HTML 内容 ---
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            margin: 0 auto;
            max-width: 800px;
            padding: 2em;
            color: #333;
            background-color: #fdfdfd;
        }}
        h1 {{
            text-align: center;
            color: #2c3e50;
            border-bottom: 2px solid #eaecef;
            padding-bottom: 0.5em;
        }}
        ul {{
            list-style-type: none;
            padding: 0;
        }}
        li {{
            margin-bottom: 0.9em;
            border-left: 3px solid #3498db;
            padding-left: 1.2em;
            transition: background-color 0.2s ease-in-out, border-left-color 0.2s ease-in-out;
        }}
        li:hover {{
             background-color: #f4f6f7;
             border-left-color: #e74c3c;
        }}
        a {{
            text-decoration: none;
            color: #2980b9;
            font-size: 1.1em;
            font-weight: 500;
        }}
        a:hover {{
            text-decoration: underline;
            color: #c0392b;
        }}
    </style>
</head>
<body>

    <h1>{page_header}</h1>

    <ul>
        {"\n        ".join(list_items)}
    </ul>

</body>
</html>
"""

    # 将生成的 HTML 内容写入文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\n成功！index.html 已生成于: {os.path.abspath(output_file)}")
    except IOError as e:
        print(f"\n错误：无法写入文件 '{output_file}'。错误信息: {e}")

if __name__ == "__main__":
    generate_index_page()