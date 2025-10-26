import os
import pypdf  # 改为导入 pypdf
import re
from openai import OpenAI
import time
import json
from pathlib import Path

# 配置路径
SOURCE_DIR = "/workspaces/xiaoqizhangxz-arch.github.io/translator/source_pdfs"
TARGET_DIR = "/workspaces/xiaoqizhangxz-arch.github.io/translator/cleaned_txts"
TRANSLATION_DIR = "/workspaces/xiaoqizhangxz-arch.github.io/translator/translations"
LOG_DIR = "/workspaces/xiaoqizhangxz-arch.github.io/translator/logs"

# 创建必要的目录
for directory in [SOURCE_DIR, TARGET_DIR, TRANSLATION_DIR, LOG_DIR]:
    Path(directory).mkdir(parents=True, exist_ok=True)

class PDFTranslator:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.terminology_dict = {}
        self.translation_log = []
        
    def extract_pdf_text(self, pdf_path):
        """提取PDF文本内容"""
        print(f"正在提取PDF文本: {pdf_path}")
        full_text = ""
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)  # 改为使用 pypdf.PdfReader
                total_pages = len(reader.pages)
                
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    # 添加页码标记
                    full_text += f"--- Page {page_num + 1} ---\n{text}\n\n"
                    print(f"已提取第 {page_num + 1}/{total_pages} 页")
                    
        except Exception as e:
            print(f"PDF提取错误: {e}")
            raise
        
        return full_text
    
    def clean_and_chunk_text(self, text, chunk_size=1500):
        """清理文本并分块"""
        print("正在进行文本清理和分块...")
        
        # 基础清理
        text = re.sub(r'\s+', ' ', text)  # 合并多余空白字符
        text = re.sub(r'\n\s*\n', '\n\n', text)  # 规范化段落间隔
        
        # 按语义分块（句子、段落）
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # 如果当前块加上新句子不超过限制，则添加
            if len(current_chunk) + len(sentence) <= chunk_size:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                # 如果当前块已经有内容，保存它
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # 如果单个句子就超过chunk_size，强制分割
                    chunks.append(sentence[:chunk_size])
                    current_chunk = sentence[chunk_size:]
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        print(f"文本已分成 {len(chunks)} 个块")
        return chunks
    
    def save_cleaned_text(self, text, original_filename):
        """保存清理后的文本"""
        output_path = os.path.join(TARGET_DIR, f"{original_filename}_cleaned.txt")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"清理后的文本已保存: {output_path}")
        return output_path
    
    def build_system_prompt(self):
        """构建系统提示词"""
        return """你是一位专业的翻译专家，专门从事心理学和神秘学文献的翻译。请遵循以下要求：

专业术语一致性：
- 荣格心理学：集体无意识、原型、阴影、人格面具、自性化、阿尼玛、阿尼姆斯等
- 塔罗牌：大阿卡纳、小阿卡纳、愚者、魔术师、女祭司、皇后、皇帝等
- 保持学术严谨性，专业术语前后统一

翻译风格：
- 学术性但不过于晦涩
- 保持原文的哲学深度和象征意义
- 文化概念要准确传达，必要时添加简要说明
- 语言流畅自然，符合中文表达习惯

注意事项：
- 保留重要的专业术语英文原文（首次出现时用括号标注）
- 保持段落结构和逻辑连贯性
- 特别注意象征性语言和隐喻的准确传达"""
    
    def translate_text_chunks(self, chunks, book_title):
        """翻译文本块"""
        print(f"开始翻译《{book_title}》，共 {len(chunks)} 个文本块...")
        
        translations = []
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        
        for i, chunk in enumerate(chunks):
            print(f"翻译进度: {i+1}/{len(chunks)}")
            
            try:
                # 构建用户提示
                user_prompt = self.build_translation_prompt(chunk, i, len(chunks), book_title)
                messages.append({"role": "user", "content": user_prompt})
                
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=0.2,
                    max_tokens=4000
                )
                
                translation = response.choices[0].message.content
                translations.append(translation)
                
                # 记录日志
                self.translation_log.append({
                    "chunk_index": i,
                    "original_length": len(chunk),
                    "translation_length": len(translation),
                    "timestamp": time.time()
                })
                
                # 管理对话历史
                messages = self.manage_conversation_history(messages, translation)
                
                # 提取术语
                self.extract_terminology(translation)
                
                # 避免速率限制
                if (i + 1) % 10 == 0:
                    print("等待5秒避免速率限制...")
                    time.sleep(5)
                else:
                    time.sleep(1)
                    
            except Exception as e:
                print(f"第 {i+1} 块翻译失败: {e}")
                # 错误恢复
                translations.append(f"[翻译错误: {str(e)}]")
                messages = self.recover_from_error(messages)
                time.sleep(10)  # 错误后等待更长时间
                continue
        
        return translations
    
    def build_translation_prompt(self, chunk, current_index, total_chunks, book_title):
        """构建翻译提示"""
        context_info = []
        
        if current_index > 0:
            context_info.append("请基于前文内容，保持术语和风格的一致性")
        
        if current_index < total_chunks - 1:
            context_info.append("请确保本部分结尾自然衔接后续内容")
        
        context_info.append("特别注意荣格心理学和塔罗牌专业术语的准确翻译")
        
        context_str = "。".join(context_info)
        
        return f"""《{book_title}》翻译任务

{context_str}

当前翻译片段（第{current_index + 1}/{total_chunks}部分）：
{chunk}

请提供专业准确的中文翻译，保持学术严谨性和语言流畅性："""
    
    def manage_conversation_history(self, messages, new_translation, max_history=3):
        """管理对话历史以控制token数量"""
        # 总是保留系统消息
        managed_messages = [messages[0]]
        
        # 如果历史太长，只保留最近的几轮
        if len(messages) > max_history * 2 + 1:
            # 保留系统消息和最近的对话
            recent_messages = messages[-(max_history * 2):]
            managed_messages.extend(recent_messages)
        else:
            managed_messages.extend(messages[1:])
        
        # 添加新的助手回复
        managed_messages.append({"role": "assistant", "content": new_translation})
        
        return managed_messages
    
    def recover_from_error(self, messages):
        """从错误中恢复"""
        # 保留系统消息和最近一轮用户消息
        if len(messages) >= 3:
            return [messages[0], messages[-2], messages[-1]]
        else:
            return messages
    
    def extract_terminology(self, translation):
        """从翻译中提取可能的专业术语"""
        # 简单的术语识别模式
        terminology_patterns = [
            r'[「《]([^」》]+)[」》]\s*（([^）]+)）',  # 中文术语（英文原文）
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*（([^）]+)）',  # 英文术语（中文解释）
        ]
        
        for pattern in terminology_patterns:
            matches = re.findall(pattern, translation)
            for match in matches:
                if len(match) == 2:
                    term, explanation = match
                    if term not in self.terminology_dict:
                        self.terminology_dict[term] = explanation
                        print(f"发现新术语: {term} -> {explanation}")
    
    def save_translation(self, translations, original_filename, book_title):
        """保存翻译结果"""
        # 保存完整翻译
        output_path = os.path.join(TRANSLATION_DIR, f"{original_filename}_translated.txt")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"《{book_title}》中文翻译\n")
            f.write("=" * 50 + "\n\n")
            
            for i, translation in enumerate(translations):
                f.write(f"【第{i+1}部分】\n")
                f.write(translation)
                f.write("\n\n" + "-" * 40 + "\n\n")
        
        print(f"完整翻译已保存: {output_path}")
        
        # 保存术语表
        if self.terminology_dict:
            terminology_path = os.path.join(TRANSLATION_DIR, f"{original_filename}_terminology.json")
            with open(terminology_path, 'w', encoding='utf-8') as f:
                json.dump(self.terminology_dict, f, ensure_ascii=False, indent=2)
            print(f"术语表已保存: {terminology_path}")
        
        # 保存日志
        log_path = os.path.join(LOG_DIR, f"{original_filename}_translation_log.json")
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(self.translation_log, f, ensure_ascii=False, indent=2)
        print(f"翻译日志已保存: {log_path}")
        
        return output_path
    
    def process_pdf_file(self, pdf_filename, book_title=None):
        """处理单个PDF文件"""
        pdf_path = os.path.join(SOURCE_DIR, pdf_filename)
        
        if not os.path.exists(pdf_path):
            print(f"文件不存在: {pdf_path}")
            return
        
        # 提取原始文件名（不含扩展名）
        original_name = os.path.splitext(pdf_filename)[0]
        
        if book_title is None:
            book_title = original_name
        
        print(f"开始处理: {book_title}")
        
        try:
            # 步骤1: 提取PDF文本
            raw_text = self.extract_pdf_text(pdf_path)
            
            # 步骤2: 保存清理后的文本
            cleaned_path = self.save_cleaned_text(raw_text, original_name)
            
            # 步骤3: 分块
            chunks = self.clean_and_chunk_text(raw_text)
            
            # 步骤4: 翻译
            translations = self.translate_text_chunks(chunks, book_title)
            
            # 步骤5: 保存结果
            final_path = self.save_translation(translations, original_name, book_title)
            
            print(f"处理完成: {book_title}")
            print(f"清理文本: {cleaned_path}")
            print(f"翻译结果: {final_path}")
            
            return final_path
            
        except Exception as e:
            print(f"处理失败 {pdf_filename}: {e}")
            return None
    
    def batch_process_pdfs(self):
        """批量处理SOURCE_DIR中的所有PDF文件"""
        pdf_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print(f"在 {SOURCE_DIR} 中没有找到PDF文件")
            return
        
        print(f"找到 {len(pdf_files)} 个PDF文件:")
        for i, pdf_file in enumerate(pdf_files):
            print(f"{i+1}. {pdf_file}")
        
        for pdf_file in pdf_files:
            print(f"\n{'='*50}")
            print(f"处理文件: {pdf_file}")
            print('='*50)
            
            self.process_pdf_file(pdf_file)
            
            print(f"完成: {pdf_file}")
            print("等待10秒后处理下一个文件...")
            time.sleep(10)

def main():
    # 从环境变量获取API密钥
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    if not api_key:
        print("请设置 DEEPSEEK_API_KEY 环境变量")
        return
    
    # 创建翻译器实例
    translator = PDFTranslator(api_key)
    
    # 选择处理模式
    print("选择处理模式:")
    print("1. 处理单个PDF文件")
    print("2. 批量处理所有PDF文件")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        # 单个文件处理
        pdf_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print(f"在 {SOURCE_DIR} 中没有找到PDF文件")
            return
        
        print("可用的PDF文件:")
        for i, pdf_file in enumerate(pdf_files):
            print(f"{i+1}. {pdf_file}")
        
        try:
            file_choice = int(input("请选择文件编号: ")) - 1
            if 0 <= file_choice < len(pdf_files):
                selected_file = pdf_files[file_choice]
                book_title = input("请输入书籍标题 (直接回车使用文件名): ").strip()
                if not book_title:
                    book_title = None
                translator.process_pdf_file(selected_file, book_title)
            else:
                print("无效的选择")
        except ValueError:
            print("请输入有效的数字")
    
    elif choice == "2":
        # 批量处理
        translator.batch_process_pdfs()
    
    else:
        print("无效的选择")

if __name__ == "__main__":
    main()