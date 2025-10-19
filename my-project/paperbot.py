import subprocess
import re
import os
import sys
from pathlib import Path
import google.generativeai as genai
import json

# =================== 路径配置 ===================
# 默认工作目录（可由环境变量 PAPERBOT_BASE_DIR 覆盖）
BASE_DIR = Path(os.environ.get('PAPERBOT_BASE_DIR', '/workspaces/xiaoqizhangxz-arch.github.io'))

# 三个目录
INPUT_PDF_FOLDER = BASE_DIR / 'source_pdfs'
OUTPUT_TXT_FOLDER = BASE_DIR / 'cleaned_txts'
OUTPUT_HTML_FOLDER = BASE_DIR / 'summary_htmls'

MODEL_NAME = "models/gemini-2.5-pro"

# =================== Gemini Prompts ===================

# 新增：专门用于提取元数据的Prompt
METADATA_EXTRACTION_PROMPT = """
你是一个学术文献元数据提取专家。你的任务是分析我提供的学术论文开头的文本，并以JSON格式返回其核心元数据。

分析以下文本：
---
{text_chunk}
---

请严格按照以下要求操作：
1.  精确识别文章的【完整标题】、【所有作者】的全名，以及【出版年份】。
2.  你的回答必须是且仅是一个格式正确的JSON对象。
3.  JSON对象必须包含三个键："title", "author", "year"。
4.  不要包含任何JSON之外的解释、前言或markdown标记。

示例输出：
{{
  "title": "Automating Agroecology: How to Design a Farming Robot Without a Monocultural Mindset?",
  "author": "Lenora Ditzler and Clemens Driessen",
  "year": "2022"
}}
"""

# 您的主分析Prompt
PAPERBOT_PROMPT_TEMPLATE = """
你将扮演一个多阶段的学术分析专家。你的任务是接收我粘贴的学术文章全文，并严格按照以下两个阶段来完成任务。

## 第一阶段：内部流程：初步分析与专家角色设定
在生成任何输出之前，你必须首先执行以下内部步骤：
1.  **识别学术领域**: 基于文章内容、关键词、理论框架及参考文献，精确确定其核心学术领域和具体子方向（例如：“农村社会学（侧重于行动者网络理论）”）。
2.  **扮演领域专家**: 立即转变为该领域的顶尖教授和资深专家。后续所有分析、总结和评论都必须基于此专家视角，运用最精准的专业术语，展现对相关理论和学者的深度了解，并提供批判性、富有洞察力的分析。

## 第二阶段：输出格式：生成单一、完整的HTML深度分析报告
在你成功设定并进入专家角色后，开始撰写一份单一、完整的HTML分析报告。报告必须严格遵循以下结构和格式：
报告的总体格式：
报告的顶层标题 <h1> 必须是所分析文章的完整标题。
在 <h1> 标题下方，必须紧跟一个 <p class="author"> 标签，用以显示文章的作者。
报告的第一部分：全文概要总结 以你作为该领域专家的身份，按照“论点-论据-论证过程-方法-案例”的结构，对整篇文章进行全面、深刻的总结。
<h2>全文概要总结</h2>
<h3>1. 论点 (Argument)</h3>
<h3>2. 论据 (Evidence)</h3>
<h3>3. 论证过程 (Reasoning Process)</h3>
<h3>4. 方法 (Method)</h3>
<h3>5. 案例 (Case/Example)</h3>
报告的第二部分：分章节表格化细部分析 将原文按照章节标题进行拆解。
为每一个章节，都必须生成一个独立的HTML表格。
每个表格都必须严格遵循以下两列结构：
- **第一列标题**：“大意、细节与原文引用 (Main Idea, Details & Original Quotes)”
- **第二列标题**：“引用的文献 (按论点主题分类) (Cited Literature (Categorized by Argument Theme))”
- **严禁**创建任何形式的第三列。所有原文引用都必须通过 `<blockquote>` 标签，严格地放置在第一列的 `<li>` 元素内部。

**结构示例**：你的表格行 `<tr>` 必须是这样的结构，有且仅有两个 `<td>` 元素：
```html
<tr>
  <td>
    <ul>
      <li>
        这里是观点的总结...
        <blockquote>这里是原文引用...</blockquote>
      </li>
    </ul>
  </td>
  <td>
    </td>
</tr>
表格内容填充规则：
大意、细节与原文引用 (Main Idea, Details & Original Quotes): 这是第一列，必须做到详尽无遗。
首先，用一个简短的段落概括本章节的核心大意。
然后，紧接着使用一个无序列表 (<ul>)。
核心规则： 你必须为本章节原文中出现的每一个引用创建一个对应的 <li> 列表项。每个 <li> 列表项必须包含：
对作者在该引用处所阐述的具体观点或论据的详细总结。
紧随其后，必须包含一个 <blockquote> 标签，其中引用一句能够代表该论点的、包含或紧邻该引用的原文，并在引用末尾附上完整的引用标注。
引用的文献 (按论点主题分类) (Cited Literature (Categorized by Argument Theme)): 这是第二列，是对本章知识谱系的重构。你必须： a. 识别论点主题 (Argument Themes): 仔细分析第一列的内容，识别出作者在本章节中提出的几个核心的、不同的论点或议题。 b. 创建主题标题: 为每一个识别出的论点主题，创建一个简明扼要的标题，并使用 <h4 class="argument-theme"> 标签包裹。例如：<h4 class="argument-theme">批判“理性经济人”的农民形象</h4>。 c. 归类参考文献: 在每个主题标题下方，使用一个无序列表 (<ul>)，列出所有被作者用来支撑该特定论点主题的参考文献。 d. 文献格式: 每个 <li> 元素的格式必须为：<li><strong>作者 (年份)</strong>, <a href="[北大图书馆搜索链接]" target="_blank"><em>[文献完整标题]</em>, p. [页码]</a></li>。其中，北大图书馆搜索链接的URL构建规则为：https://pku.summon.serialssolutions.com/#!/search?ho=t&l=zh-cn&q=[经过URL编码的文章标题+作者]。如果原文未提供页码，则省略 , p. [页码] 部分。 e. 排序规则: 主题标题的出现顺序应大致遵循其在章节中的逻辑顺序。每个主题标题下的文献列表，也应按照它们在原文中首次出现的顺序排列。

最终检查指令：在你生成所有HTML内容后，请进行最后一次自我检查：确保每一个 <table> 中的每一个 <tr> 都严格只有两个 <td> 元素。如果有多余的列，必须修正你的输出。

<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>学术文章深度分析报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", "Arial", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "SimHei", "SimSun", sans-serif; line-height: 1.8; margin: 2em; color: #333; background-color: #fdfdfd; }}
        .container {{ max-width: 1200px; margin: auto; }}
        h1 {{ font-size: 2.2em; text-align: center; color: #333; margin-bottom: 0.2em; }}
        .author {{ text-align: center; font-size: 1.2em; color: #666; margin-top: 0; margin-bottom: 2em; border-bottom: 3px solid #005A9C; padding-bottom: 1em; }}
        h2 {{ font-size: 2em; margin-top: 2.5em; color: #005A9C; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }}
        h3 {{ font-size: 1.5em; margin-top: 1.5em; color: #005A9C; border-bottom: 1px solid #e0e0e0; }}
        h4.argument-theme {{ font-size: 1.1em; color: #333; margin-top: 1.2em; margin-bottom: 0.5em; border-left: 4px solid #005A9C; padding-left: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); table-layout: fixed; }}
        th, td {{ padding: 12px 15px; text-align: left; border: 1px solid #ddd; vertical-align: top; word-wrap: break-word; }}
        thead {{ background-color: #005A9C; color: white; }}
        tbody tr:nth-child(even) {{ background-color: #f7f9fc; }}
        tbody tr:hover {{ background-color: #eef4ff; }}
        a {{ text-decoration: none; color: #007BFF; font-weight: 500; }}
        a:hover {{ text-decoration: underline; color: #0056b3; }}
        ul {{ padding-left: 20px; margin: 0; }}
        li {{ margin-bottom: 10px; }}
        td ul {{ padding-left: 0; list-style-type: none; }}
        td ul li:last-child {{ margin-bottom: 0; }}
        blockquote {{ font-size: 0.9em; color: #555; border-left: 3px solid #ccc; padding-left: 10px; margin: 8px 0 0 0; font-style: italic; }}
        .summary-section p {{ text-indent: 2em; }}
        .reference-column {{ font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        </div>
</body>
</html>

以下是我要分析的文章全文：
---
{article_text}
---
"""

# =================== 功能函数 ===================

def extract_metadata_with_gemini(raw_text_chunk):
    """使用Gemini API从原始文本块中智能提取元数据。"""
    print("   -> 正在使用Gemini提取元数据...")
    try:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print("      [错误] Gemini API 密钥未设置。")
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        prompt = METADATA_EXTRACTION_PROMPT.format(text_chunk=raw_text_chunk)
        response = model.generate_content(prompt, request_options={'timeout': 120})
        
        json_text = extract_gemini_content(response).strip()
        json_text = re.sub(r'^```json\n', '', json_text)
        json_text = re.sub(r'\n```$', '', json_text)
        
        metadata = json.loads(json_text)
        # 即使元数据不完整，也返回，让主函数处理
        return metadata

    except Exception as e:
        print(f"      [错误] 使用Gemini提取元数据时出错: {e}")
        return None

def get_author_lastname_for_filename(author_full_name):
    """从作者全名字符串中解析出第一作者姓氏 + et al."""
    if not author_full_name: return "__" # 使用占位符
    
    authors = re.split(r',\s*|\s+and\s+|·', author_full_name, flags=re.IGNORECASE)
    first_author = authors[0].strip()
    
    name_parts = first_author.split()
    last_name = name_parts[-1] if name_parts else first_author
    
    if len(authors) > 1:
        return f"{last_name} et al."
    else:
        return last_name

def sanitize_filename(name):
    """移除文件名中的非法字符，并截断过长的文件名。"""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    max_len = 250
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len].rsplit(' ', 1)[0]
    return sanitized.strip()

def extract_text_with_pdftotext(pdf_path):
    """使用pdftotext从PDF中提取高质量的、保持布局的文本。"""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', '-enc', 'UTF-8', str(pdf_path), '-'],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        return result.stdout
    except FileNotFoundError:
        print("\n[错误] 未找到 'pdftotext' 命令。请先安装 poppler-utils。")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n[警告] 使用pdftotext处理文件 '{pdf_path.name}' 时出错: {e.stderr}")
        return None

def clean_hss_paper_text(raw_text):
    """针对人文社科论文的文本进行精细化清理。"""
    if not raw_text: return ""
    text = raw_text.replace('\f', '')
    text = re.sub(r'-\s*\n\s*', '', text)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    patterns_to_remove = [
        re.compile(r'^\s*Journal of .*', re.IGNORECASE), re.compile(r'^\s*ORIGINAL PAPER\s*$', re.IGNORECASE),
        re.compile(r'.*Page \d+ of \d+.*'), re.compile(r'^\s*https://doi\.org/.*'),
        re.compile(r'^\s*(Accepted:|Published online:).*', re.IGNORECASE), re.compile(r'^\s*© The Author\(s\)\s\d{4}'),
        re.compile(r'^\s*Vol\.:\(\d+\)\s*$'), re.compile(r'^\s*\* .*@.*\..*'),
        re.compile(r'^\s*Extended author information available.*'), re.compile(r'^\s*Publisher’s Note Springer Nature remains neutral.*'),
        re.compile(r'^Authors and Affiliations.*', re.IGNORECASE)
    ]
    lines = text.split('\n')
    cleaned_lines = [ line for line in lines if line.strip() and len(line.strip()) >= 3 and not line.strip().isdigit() and not any(p.match(line.strip()) for p in patterns_to_remove) ]
    final_text = '\n'.join(cleaned_lines)
    final_text = re.sub(r'^\s*\[\d+\]\s*', '', final_text, flags=re.MULTILINE)
    final_text = re.sub(r'^\s*\d+\.\s+', '', final_text, flags=re.MULTILINE)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    return final_text.strip()

def extract_gemini_content(response):
    """兼容不同API响应格式，提取文本内容。"""
    if hasattr(response, 'text'): return response.text
    if hasattr(response, 'candidates') and response.candidates:
        if hasattr(response.candidates[0], 'content') and response.candidates[0].content.parts:
            return response.candidates[0].content.parts[0].text
    return str(response)

def generate_html_report(cleaned_text):
    """调用Gemini API生成HTML报告。"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("\n[错误] Gemini API 密钥未在环境变量 GEMINI_API_KEY 中设置。")
        return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    full_prompt = PAPERBOT_PROMPT_TEMPLATE.format(article_text=cleaned_text)
    try:
        print("   -> 正在发送主分析请求，等待Gemini生成HTML...(可能需要几分钟)")
        response = model.generate_content(full_prompt, request_options={'timeout': 600})
        html_content = extract_gemini_content(response)
        html_content = re.sub(r'^```html\n', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'\n```$', '', html_content)
        return html_content.strip()
    except Exception as e:
        print(f"\n[错误] Gemini API 主分析阶段出错: {e}")
        return None

# =================== 主流程 (MODIFIED LOGIC) ===================
def main():
    INPUT_PDF_FOLDER.mkdir(exist_ok=True)
    OUTPUT_TXT_FOLDER.mkdir(exist_ok=True)
    OUTPUT_HTML_FOLDER.mkdir(exist_ok=True)

    pdf_files = [f for f in INPUT_PDF_FOLDER.iterdir() if f.suffix.lower() == '.pdf' and not f.name.startswith('._')]
    if not pdf_files:
        print(f"[信息] 在 '{INPUT_PDF_FOLDER}' 中没有找到PDF文件。")
        return
    
    total_files = len(pdf_files)
    print(f"找到 {total_files} 个PDF文件，开始批量处理...")

    for i, pdf_path in enumerate(pdf_files):
        print(f"\n--- [{i+1}/{total_files}] 处理: {pdf_path.name} ---")
        
        raw_text = extract_text_with_pdftotext(pdf_path)
        if not raw_text:
            print(f"   跳过，文本提取失败。")
            continue

        # --- 新的、更健壮的文件名生成逻辑 ---
        sanitized_base_name = pdf_path.stem
        print("1. 智能提取元数据...")
        metadata = extract_metadata_with_gemini(raw_text[:4000])
        
        if metadata:
            # 即使元数据不完整，也尝试构建文件名
            author_str = metadata.get('author')
            year_str = metadata.get('year', '__') # 如果年份找不到，用'__'替代
            title_str = metadata.get('title', pdf_path.stem) # 如果标题找不到，用原文件名替代

            author_filename_part = get_author_lastname_for_filename(author_str)
            
            new_filename_base = f"{author_filename_part} ({year_str}) {title_str}"
            sanitized_base_name = sanitize_filename(new_filename_base)
            print(f"   元数据已部分或全部提取。新文件名基础: {sanitized_base_name}")
        else:
            print(f"   [警告] 未能自动提取元数据。将使用原始文件名: {sanitized_base_name}")

        txt_path = OUTPUT_TXT_FOLDER / f"{sanitized_base_name}.txt"
        html_path = OUTPUT_HTML_FOLDER / f"{sanitized_base_name}.html"
        
        # --- 后续流程不变 ---
        print("2. 正在清理全文...")
        cleaned_text = clean_hss_paper_text(raw_text)
        txt_path.write_text(cleaned_text, encoding='utf-8')
        print(f"   清理后的TXT已保存: {txt_path.name}")

        print("3. 正在生成HTML报告...")
        html_content = generate_html_report(cleaned_text)
        if html_content:
            html_path.write_text(html_content, encoding='utf-8')
            print(f"   ✅ HTML报告已保存: {html_path.name}")
        else:
            print(f"   ❌ 未能为 {pdf_path.name} 生成HTML报告。")

    print(f"\n--- 所有任务完成 ---")
    print(f"TXT目录: {OUTPUT_TXT_FOLDER}")
    print(f"HTML目录: {OUTPUT_HTML_FOLDER}")

if __name__ == '__main__':
    main()