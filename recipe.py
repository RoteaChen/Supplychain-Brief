import requests
import os
import random
from datetime import datetime

# ========== 减脂食谱库 ==========
LOW_CALORIE_RECIPES = [
    {
        "name": "鸡胸肉西兰花",
        "calories": "320卡",
        "ingredients": "鸡胸肉150g、西兰花200g、橄榄油5g、黑胡椒",
        "method": "鸡胸肉切块腌制，西兰花焯水，少油翻炒，撒黑胡椒"
    },
    {
        "name": "番茄虾仁意面",
        "calories": "380卡",
        "ingredients": "全麦意面60g、虾仁100g、番茄2个、洋葱少许",
        "method": "意面煮熟，番茄炒出汁，加入虾仁和意面拌匀"
    },
    {
        "name": "凉拌黄瓜鸡丝",
        "calories": "280卡",
        "ingredients": "鸡胸肉120g、黄瓜1根、蒜末、生抽、醋",
        "method": "鸡胸肉煮熟撕丝，黄瓜拍碎切段，加调料拌匀"
    },
    {
        "name": "蒸蛋豆腐羹",
        "calories": "250卡",
        "ingredients": "嫩豆腐150g、鸡蛋2个、温水、葱花",
        "method": "豆腐切块铺底，蛋液加温水搅匀倒入，蒸10分钟"
    },
    {
        "name": "香煎三文鱼配芦笋",
        "calories": "420卡",
        "ingredients": "三文鱼100g、芦笋150g、柠檬、橄榄油3g",
        "method": "三文鱼两面煎熟，芦笋焯水后少油煎，挤柠檬汁"
    },
    {
        "name": "杂粮蔬菜饭团",
        "calories": "350卡",
        "ingredients": "糙米50g、胡萝卜、黄瓜、海苔、少许盐",
        "method": "糙米煮熟，蔬菜切丁拌匀，捏成饭团包海苔"
    },
    {
        "name": "冬瓜虾仁汤",
        "calories": "180卡",
        "ingredients": "冬瓜300g、虾仁80g、姜丝、盐",
        "method": "冬瓜切块煮软，加入虾仁煮熟，调味即可"
    },
    {
        "name": "烤蔬菜鸡胸肉碗",
        "calories": "400卡",
        "ingredients": "鸡胸肉120g、南瓜、彩椒、洋葱、橄榄油5g",
        "method": "所有食材切块，刷橄榄油，烤箱200度烤25分钟"
    },
    {
        "name": "凉拌木耳鸡丝",
        "calories": "260卡",
        "ingredients": "鸡胸肉100g、木耳50g、黄瓜、蒜末、醋",
        "method": "鸡胸肉煮熟撕丝，木耳泡发焯水，黄瓜切丝，加调料拌匀"
    },
    {
        "name": "紫菜蛋花汤配全麦面包",
        "calories": "300卡",
        "ingredients": "紫菜10g、鸡蛋1个、全麦面包1片、葱花",
        "method": "水烧开，紫菜撕碎放入，倒入蛋液搅散，配全麦面包"
    },
]

def generate_recipe():
    """生成今日减脂食谱"""
    recipe = random.choice(LOW_CALORIE_RECIPES)
    
    lines = [
        f"🥗 今日减脂食谱 | {datetime.now().strftime('%m月%d日')}",
        "=" * 30,
        "",
        f"📌 {recipe['name']}",
        f" 热量: {recipe['calories']}",
        "",
        " 食材:",
        f"   {recipe['ingredients']}",
        "",
        "‍ 做法:",
        f"   {recipe['method']}",
        "",
        " 小贴士:",
        "   • 少油少盐，控制钠摄入",
        "   • 搭配适量运动效果更佳",
        "   • 晚餐建议在19:00前吃完",
        "",
        f" 更新时间: {datetime.now().strftime('%H:%M')}"
    ]
    
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
    print(f"🥗 减脂食谱开始 | {datetime.now()}")
    recipe = generate_recipe()
    push_serverchan("今日减脂食谱", recipe)
    print("✅ 减脂食谱完成")

if __name__ == "__main__":
    main()
