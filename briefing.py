# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import re
from datetime import datetime

# ========== 配置 ==========
RSS_SOURCES = {
    # 供应链物流（国际源）
    "Talking Logistics": "https://talkinglogistics.com/feed/",
    "Supply Chain Dive": "https://www.supplychaindive.com/feeds/news/",
    "FreightWaves": "https://www.freightwaves.com/feed",
    "Journal of Commerce": "https://www.joc.com/rss.xml",
    
    # 国内科技
    "36氪": "https://36kr.com/feed",
    "雷锋网": "https://www.leiphone.com/feed",
    
    # 国际科技/电商
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Digital Commerce 360": "https://www.digitalcommerce360.com/feed/",
    "Retail Dive": "https://www.retaildive.com/feeds/news/",
}

def clean_cdata(text):
    """清理CDATA标记"""
    if text is None:
        return ""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()
    return text

def extract_link(item):
    """从item中提取链接"""
    link = item.find('link')
    if link is not None and link.text:
        return clean_cdata(link.text)
    
    guid = item.find('guid')
    if guid is not None and guid.text:
        return clean_cdata(guid.text)
    
    desc = item.find('description')
    if desc is not None and desc.text:
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', desc.text)
        if urls:
            return urls[0]
    
    return ""

def fetch_rss(url):
    """解析RSS，支持CDATA和多种格式"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            
            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                text = data.decode('utf-8', errors='ignore')
                text = re.sub(r'encoding="[^"]*"', '', text)
                root = ET.fromstring(text)
            
            items = []
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                title = clean_cdata(title_elem.text) if title_elem is not None else ""
                link = extract_link(item)
                
                if title and link:
                    items.append({
                        "title": title,
                        "link": link
                    })
            
            return items[:3]
    except Exception as e:
        print("RSS失败: %s" % str(e))
        return []

def fetch_news():
    """抓取新闻"""
    news = []
    for source, url in RSS_SOURCES.items():
        try:
            print("正在抓取: %s" % source)
            items = fetch_rss(url)
            for item in items:
                news.append({
                    "source": source,
                    "title": item["title"],
                    "link": item["link"]
                })
            print("✅ %s: %d条" % (source, len(items)))
        except Exception as e:
            print(" %s: 失败 - %s" % (source, str(e)))
    return news

def generate_bulletin(news_list):
    """生成行业简报"""
    lines = [
        " 供应链物流日报 | %s" % datetime.now().strftime("%m月%d日"),
        "=" * 30,
        ""
    ]
    
    if not news_list:
        lines.append(" 未抓取成功")
        lines.append("")
        lines.append("请检查RSS源是否可用")
        lines.append("")
        lines.append(" 更新时间: %s" % datetime.now().strftime("%H:%M"))
        return "\n".join(lines)
    
    # 物流头条
    logistics_sources = ["Talking Logistics", "Supply Chain Dive", "FreightWaves", "Journal of Commerce"]
    logistics_news = [n for n in news_list if n["source"] in logistics_sources]
    
    if logistics_news:
        lines.append(" 物流头条")
        for i, item in enumerate(logistics_news[:2], 1):
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("    %s" % item["link"])
            lines.append("")
    
    # 国内科技
    china_sources = ["36氪", "雷锋网"]
    china_news = [n for n in news_list if n["source"] in china_sources]
    
    if china_news:
        lines.append(" 国内科技")
        for i, item in enumerate(china_news[:2], 1):
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("    %s" % item["link"])
            lines.append("")
    
    # 国际电商
    tech_sources = ["TechCrunch", "The Verge", "Digital Commerce 360", "Retail Dive"]
    tech_news = [n for n in news_list if n["source"] in tech_sources]
    
    if tech_news:
        lines.append("🛒 国际电商")
        for i, item in enumerate(tech_news[:2], 1):
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("    %s" % item["link"])
            lines.append("")
    
    # AI与数字化
    ai_keywords = ["AI", "智能", "数字化", "自动化", "机器人", "无人", "artificial intelligence", "machine learning"]
    ai_news = [n for n in news_list if any(k.lower() in n["title"].lower() for k in ai_keywords)]
    if ai_news:
        lines.append("🤖 AI与数字化")
        for item in ai_news[:2]:
            lines.append("• %s" % item["title"])
        lines.append("")
    
    # 每日一策
    lines.append(" 每日一策")
    lines.append(" 关注AI Agent在物流与电商的落地案例，2026年已从实验进入实战阶段。")
    lines.append("")
    lines.append(" 更新时间: %s" % datetime.now().strftime("%H:%M"))
    
    return "\n".join(lines)

def push_serverchan(title, content):
    """推送到微信"""
    key = os.getenv("SERVERCHAN_KEY", "")
    if not key:
        print("未配置SERVERCHAN_KEY")
        return False
    
    url = "https://sctapi.ftqq.com/%s.send" % key
    data = urllib.parse.urlencode({
        "title": title,
        "desp": content
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode('utf-8')
            print("✅ 推送成功: %s" % title)
            return True
    except Exception as e:
        print(" 推送失败: %s" % str(e))
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("🤖 任务开始 | %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    
    # 抓取新闻
    print("\n📰 开始抓取新闻...")
    news = fetch_news()
    print("\n 总共抓取到 %d 条新闻" % len(news))
    
    # 生成并推送简报
    print("\n 生成供应链简报...")
    bulletin = generate_bulletin(news)
    push_serverchan("供应链物流日报", bulletin)
    
    print("\n" + "=" * 50)
    print("✅ 全部完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
