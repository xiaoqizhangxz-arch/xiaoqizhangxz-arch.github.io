# /workspaces/xiaoqizhangxz-arch.github.io/scripts/fetch_papers.py

import feedparser
import os
from datetime import datetime
import re
import urllib.parse

# --- 配置区 ---

# 1. 定义你的关键词（保持不变）
KEYWORDS = [
    'rural sociology', 'agroecology', 'actor-network theory', 'ANT',
    'new materialism', 'assemblage theory', 'relational sociology',
    'food sovereignty', 'agrifood', 'peasant'
]

# 2. 定义RSS源（核心改动部分）
# 我们现在使用Google Scholar的自定义搜索RSS源
# 如何创建？
# a. 在Google Scholar进行高级搜索
# b. 在搜索结果页面左下角点击“创建快讯”(Create alert)
# c. 在弹出的窗口中，将传送方式选为“Feed”，然后创建，即可获得RSS链接
# 下面是一些帮你构造好的示例查询：

# 核心理论词，用 OR 连接
theory_query = '"rural sociology" OR agroecology OR "actor-network theory" OR "new materialism" OR "assemblage theory" OR "relational sociology"'
# 领域词，用 AND 连接，确保与农业相关
domain_query = 'agriculture OR food OR rural OR peasant'

# 完整的Google Scholar搜索查询
# 查找同时包含理论词和领域词的最新文章
combined_query = f'({theory_query}) AND ({domain_query})'

RSS_FEEDS = {
    # 这个RSS源会检索所有与你理论相关的农业/农村研究论文
    'Google Scholar - Broad Search': f'https://scholar.google.com/scholar_rss?as_ylo={datetime.now().year-1}&q={urllib.parse.quote(combined_query)}&scisbd=1',
    
    # 这是一个专门查找相关书籍的例子（通过添加 "book" 关键词）
    'Google Scholar - Books': f'https://scholar.google.com/scholar_rss?as_ylo={datetime.now().year-1}&q={urllib.parse.quote(combined_query + " book")}&scisbd=1',
    
    # 你也可以添加特定出版社的RSS（如果他们提供的话），但Google Scholar通常更全面
    # 例如：Taylor & Francis 关于 "rural sociology" 的搜索结果RSS
    'Taylor & Francis - Rural Sociology': 'https://www.tandfonline.com/action/doSearch?AllField=rural+sociology&ConceptID=211&target=default&sortBy=Newest&startPage=0&pageSize=20&format=rss'
}

# 3. 定义输出路径（保持不变）
workspace_path = os.getenv('GITHUB_WORKSPACE', '/workspaces/xiaoqizhangxz-arch.github.io')
OUTPUT_DIR = os.path.join(workspace_path, 'news')

# --- 脚本主逻辑 (稍作优化，基本不变) ---

def clean_summary(summary_html):
    """清理HTML标签，并截取摘要"""
    if not summary_html:
        return "No summary available."
    clean_text = re.sub('<.*?>', '', summary_html)
    clean_text = ' '.join(clean_text.split())
    return clean_text[:350] + '...' if len(clean_text) > 350 else clean_text

def fetch_and_filter():
    """抓取并过滤论文"""
    print("Starting broad academic content fetch...")
    found_items = []
    seen_links = set()

    for feed_name, url in RSS_FEEDS.items():
        print(f"Fetching from: {feed_name}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get('title', 'No Title')
                link = entry.get('link', '')
                summary = entry.get('summary', '')

                if not link or link in seen_links:
                    continue

                # 因为查询已经在RSS源头做好了，这里的关键词过滤可以简化甚至移除
                # 但保留它可以在摘要中进行二次确认，提高相关性
                content_to_check = (title + ' ' + summary).lower()
                if any(keyword.lower() in content_to_check for keyword in KEYWORDS):
                    published_date = ""
                    if 'published' in entry:
                        published_date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d')
                    elif 'updated' in entry:
                        published_date = datetime(*entry.updated_parsed[:6]).strftime('%Y-%m-%d')
                    
                    item_info = {
                        'title': title,
                        'link': link,
                        'summary': clean_summary(summary),
                        'published': published_date,
                        'source': feed_name
                    }
                    found_items.append(item_info)
                    seen_links.add(link)
                    print(f"  - Found relevant item: {title}")

        except Exception as e:
            print(f"Error fetching or parsing {feed_name}: {e}")

    return found_items

def write_to_markdown(items):
    """将找到的文献写入Markdown文件"""
    if not items:
        print("No new relevant items found today.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    filename = os.path.join(OUTPUT_DIR, f"{today_str}.md")

    items.sort(key=lambda x: (x['published'], x['source']), reverse=True)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"---\n")
        f.write(f"title: \"Daily Academic Digest: {today_str}\"\n")
        f.write(f"date: {datetime.now().isoformat()}\n")
        f.write(f"---\n\n")
        f.write(f"# Academic Digest for {today_str}\n\n")
        f.write(f"Found {len(items)} new publications matching your interests across major publishers.\n\n")

        papers_by_source = {}
        for item in items:
            source = item['source']
            if source not in papers_by_source:
                papers_by_source[source] = []
            papers_by_source[source].append(item)

        for source, item_list in papers_by_source.items():
            f.write(f"## From: {source}\n\n")
            for item in item_list:
                f.write(f"### {item['title']}\n\n")
                if item['published']:
                    f.write(f"**Published Date:** {item['published']}\n\n")
                f.write(f"**Link:** [{item['link']}]({item['link']})\n\n")
                f.write(f"**Summary:**\n> {item['summary']}\n\n")
                f.write("---\n\n")

    print(f"Successfully wrote {len(items)} items to {filename}")

if __name__ == "__main__":
    items = fetch_and_filter()
    write_to_markdown(items)