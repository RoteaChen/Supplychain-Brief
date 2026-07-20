import feedparser
import requests
import os
from datetime import datetime

# ========== 配置 ==========
RSS_SOURCES = {
    "罗戈网": "https://www.logclub.com/feed",
    "物流指闻": "https://www.wuliuzhixun.com/feed",
    "Talking Logistics": "https://talkinglogistics.com/feed/",
    "Supply Chain Dive": "https://www.supplychaindive.com/feeds/news/",
    "36氪": "https://36kr.com/feed",
    "虎嗅": "https://www.huxiu.com/rss",
    "亿邦动力": "https://www.ebrun.com/feed",
    "电商报": "https://www.dsb.cn/feed",
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Information": "https://www.theinformation.com/feed",
}

def fetch_news():
    """抓取新闻"""
    news = []
    for source, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url, request_headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if not feed.entries:
                print(f"{source}: 无数据")
                continue
            for entry in feed.entries[:3]:
                news.append({
                    "source": source,
                    "title": entry.title,
                    "link": entry.link
                })
            print(f"✅ {source}: 抓取成功")
        except Exception as e:
            print(f" {source}: 抓取失败 - {e}")
    return news

def generate_bulletin(news_list):
    """生成行业简报"""
    lines = [
        f" 供应链物流日报 | {datetime.now().strftime('%m月%d日')}",
        "=" * 30,
        ""
    ]
    
    logistics_sources = ["罗戈网", "物流指闻", "Talking Logistics", "Supply Chain Dive"]
    logistics_news = [n for n in news_list if n['source'] in logistics_sources]
    
    if logistics_news:
        lines.append(" 物流头条")
        for i, item in enumerate(logistics_news[:2], 1):
            lines.append(f"{i}. 【{item['source']}】{item['title']}")
            lines.append(f"    {item['link']}")
            lines.append("")
    
    ecommerce_sources = ["36氪", "虎嗅", "亿邦动力", "电商报", "TechCrunch", "The Information"]
    ecommerce_news = [n for n in news_list if n['source'] in ecommerce_sources]
    
    if ecommerce_news:
        lines.append("🛒 电商动态")
        for i, item in enumerate(ecommerce_news[:2], 1):
            lines.append(f"{i}. 【{item['source']}】{item['title']}")
            lines.append(f"    {item['link']}")
            lines.append("")
    
    ai_keywords = ['AI', '智能', '数字化', '自动化', '机器人', '无人']
    ai_news = [n for n in news_list if any(k in n['title'] for k in ai_keywords)]
    if ai_news:
        lines.append("🤖 AI与数字化")
        for item in ai_news[:2]:
            lines.append(f"• {item['title']}")
        lines.append("")
    
    lines.append(" 每日一策")
    lines.append(" 关注AI Agent在物流与电商的落地案例，2026年已从实验进入实战阶段。")
    lines.append("")
    lines.append(f" 更新时间: {datetime.now().strftime('%H:%M')}")
    
    return "\n".join(lines)

def push_serverchan(title, content):
    """推送到微信"""
    key = os.getenv("SERVERCHAN_KEY")
    if not key:
        print("未配置SERVERCHAN_KEY")
        return False
    url = f"https://sctapi.ftqq.com/{key}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=10)
        result = resp.json()
        if result.get("code") == 0:
            print(f"✅ Server酱推送成功: {title}")
            return True
        else:
            print(f" Server酱推送失败: {result}")
            return False
    except Exception as e:
        print(f" Server酱推送失败: {e}")
        return False

def main():
    print(f"🤖 供应链日报开始 | {datetime.now()}")
    news = fetch_news()
    print(f"📰 抓取到 {len(news)} 条新闻")
    bulletin = generate_bulletin(news)
    push_serverchan("供应链物流日报", bulletin)
    print("✅ 供应链日报完成")

if __name__ == "__main__":
    main()
