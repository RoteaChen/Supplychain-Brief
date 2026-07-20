# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import re
from datetime import datetime

# ========== RSS配置 ==========
RSS_SOURCES = {
    "Talking Logistics": "https://talkinglogistics.com/feed/",
    "Supply Chain Dive": "https://www.supplychaindive.com/feeds/news/",
    "FreightWaves": "https://www.freightwaves.com/feed",
    "36氪": "https://36kr.com/feed",
    "TechCrunch": "https://techcrunch.com/feed/",
}

# ========== 爬虫配置（国内网站） ==========
CRAWL_SOURCES = {
    "罗戈网": {
        "url": "https://www.logclub.com",
        "title_pattern": r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        "link_pattern": r'<a[^>]*href="(/news/\d+)"[^>]*>',
        "base_url": "https://www.logclub.com"
    },
    "物流指闻": {
        "url": "https://www.wuliuzhixun.com",
        "title_pattern": r'<h2[^>]*>(.*?)</h2>',
        "link_pattern": r'<a[^>]*href="(/article/\d+)"[^>]*>',
        "base_url": "https://www.wuliuzhixun.com"
    },
    "亿邦动力": {
        "url": "https://www.ebrun.com",
        "title_pattern": r'<h4[^>]*>(.*?)</h4>',
        "link_pattern": r'<a[^>]*href="(/202\d+/\d+/\d+/\d+\.shtml)"[^>]*>',
        "base_url": "https://www.ebrun.com"
    },
}

def clean_html(text):
    """清理HTML标签"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()
    return text

def fetch_rss(url):
    """解析RSS"""
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
                title = clean_html(title_elem.text) if title_elem is not None else ""
                
                link = item.find('link')
                link_text = clean_html(link.text) if link is not None else ""
                
                if title and link_text:
                    items.append({"title": title, "link": link_text})
            
            return items[:3]
    except Exception as e:
        print("RSS失败: %s" % str(e))
        return []

def crawl_website(source_name, config):
    """爬取网站"""
    try:
        print("正在爬取: %s" % source_name)
        req = urllib.request.Request(config["url"], headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            titles = re.findall(config["title_pattern"], html, re.DOTALL)
            titles = [clean_html(t) for t in titles if clean_html(t)]
            
            links = re.findall(config["link_pattern"], html)
            links = [config["base_url"] + l if not l.startswith('http') else l for l in links]
            
            items = []
            for i in range(min(3, len(titles), len(links))):
                items.append({
                    "title": titles[i],
                    "link": links[i]
                })
            
            print("✅ %s: %d条" % (source_name, len(items)))
            return items
            
    except Exception as e:
        print(" %s: 失败 - %s" % (source_name, str(e)))
        return []

def fetch_news():
    """抓取所有新闻"""
    news = []
    
    for source, url in RSS_SOURCES.items():
        items = fetch_rss(url)
        for item in items:
            news.append({
                "source": source,
                "title": item["title"],
                "link": item["link"]
            })
    
    for source, config in CRAWL_SOURCES.items():
        items = crawl_website(source, config)
        for item in items:
            news.append({
                "source": source,
                "title": item["title"],
                "link": item["link"]
            })
    
    return news

def generate_bulletin(news_list):
    """生成简报"""
    lines = [
        " 供应链物流日报 | %s" % datetime.now().strftime("%m月%d日"),
        "=" * 30,
        ""
    ]
    
    if not news_list:
        lines.append(" 未抓取成功")
        lines.append("")
        lines.append(" 更新时间: %s" % datetime.now().strftime("%H:%M"))
        return "\n".join(lines)
    
    # 物流头条
    logistics_sources = ["Talking Logistics", "Supply Chain Dive", "FreightWaves", "罗戈网", "物流指闻"]
    logistics_news = [n for n in news_list if n["source"] in logistics_sources]
    
    if logistics_news:
        lines.append(" 物流头条")
        for i, item in enumerate(logistics_news[:2], 1):
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("    %s" % item["link"])
            lines.append("")
    
    # 国内科技
    china_sources = ["36氪", "亿邦动力"]
    china_news = [n for n in news_list if n["source"] in china_sources]
    
    if china_news:
        lines.append(" 国内科技")
        for i, item in enumerate(china_news[:2], 1):
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("    %s" % item["link"])
            lines.append("")
    
    # 国际电商
    tech_sources = ["TechCrunch"]
    tech_news = [n for n in news_list if n["source"] in tech_sources]
    
    if tech_news:
        lines.append("🛒 国际电商")
        for i, item in enumerate(tech_news[:2], 1):
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("    %s" % item["link"])
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
    
    news = fetch_news()
    print("\n 总共抓取到 %d 条新闻" % len(news))
    
    bulletin = generate_bulletin(news)
    push_serverchan("供应链物流日报", bulletin)
    
    print("\n" + "=" * 50)
    print("✅ 全部完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
