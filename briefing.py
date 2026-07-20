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
}

def fetch_news():
    """抓取新闻"""
    news = []
    for source, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                news.append({
                    "source": source,
                    "title": entry.title,
                    "link": entry.link
                })
        except Exception as e:
            print(f"抓取{source}失败: {e}")
    return news

def generate_bulletin(news_list):
    """生成简报"""
    lines = [
        f"📦 供应链物流日报 | {datetime.now().strftime('%m月%d日')}",
        "=" * 30,
        ""
    ]
    
    # 头条
    lines.append("🔴 头条要闻")
    for i, item in enumerate(news_list[:2], 1):
        lines.append(f"{i}. 【{item['source']}】{item['title']}")
        lines.append(f"   👉 {item['link']}")
        lines.append("")
    
    # AI/数字化
    ai_keywords = ['AI', '智能', '数字化', '自动化', '机器人', '无人']
    ai_news = [n for n in news_list if any(k in n['title'] for k in ai_keywords)]
    if ai_news:
        lines.append("🤖 AI与数字化")
        for item in ai_news[:2]:
            lines.append(f"• {item['title']}")
        lines.append("")
    
    # 每日一策
    lines.append("💡 每日一策")
    lines.append("👉 关注AI Agent在物流落地案例，2026年已从实验进入实战阶段，")
    lines.append("   未布局企业可能面临效率差距扩大风险。")
    lines.append("")
    lines.append(f"⏰ 更新时间: {datetime.now().strftime('%H:%M')}")
    
    return "\n".join(lines)

def push_serverchan(title, content):
    """推送到微信"""
    key = os.getenv("SERVERCHAN_KEY")
    if not key:
        print("未配置SERVERCHAN_KEY")
        return
    url = f"https://sctapi.ftqq.com/{key}.send"
    try:
        requests.post(url, data={"title": title, "desp": content}, timeout=10)
        print("✅ Server酱推送成功")
    except Exception as e:
        print(f"❌ Server酱推送失败: {e}")

def push_bark(title, content):
    """Bark推送"""
    key = os.getenv("BARK_KEY")
    if not key:
        print("未配置BARK_KEY")
        return
    url = f"https://api.day.app/{key}/{title}/{content[:500]}"
    try:
        requests.get(url, timeout=10)
        print("✅ Bark推送成功")
    except Exception as e:
        print(f"❌ Bark推送失败: {e}")

def push_dingtalk(content):
    """钉钉推送"""
    webhook = os.getenv("DINGTALK_WEBHOOK")
    if not webhook:
        print("未配置DINGTALK_WEBHOOK")
        return
    payload = {
        "msgtype": "text",
        "text": {"content": content}
    }
    try:
        requests.post(webhook, json=payload, timeout=10)
        print("✅ 钉钉推送成功")
    except Exception as e:
        print(f"❌ 钉钉推送失败: {e}")

def main():
    print(f"🤖 简报生成开始 | {datetime.now()}")
    
    news = fetch_news()
    print(f"📰 抓取到 {len(news)} 条新闻")
    
    bulletin = generate_bulletin(news)
    print("📝 简报生成完成")
    
    push_serverchan("供应链物流日报", bulletin)
    push_bark("供应链日报", bulletin)
    push_dingtalk(bulletin)
    
    print("✅ 全部完成")

if __name__ == "__main__":
    main()
