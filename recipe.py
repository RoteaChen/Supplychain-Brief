import requests
import os
import random
from datetime import datetime

# ========== Spoonacular API配置 ==========
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY", "")
SPOONACULAR_URL = "https://api.spoonacular.com/recipes/complexSearch"

# 如果API未配置，使用备用本地库
LOCAL_RECIPES = [
    {
        "name": "鸡胸肉西兰花",
        "calories": 320,
        "protein": "35g",
        "fat": "8g",
        "carbs": "25g",
        "ingredients": "鸡胸肉150g、西兰花200g、橄榄油5g",
        "method": "鸡胸肉切块腌制，西兰花焯水，少油翻炒"
    },
    # ... 其他本地食谱
]

def fetch_api_recipe():
    """从Spoonacular API获取减脂食谱"""
    if not SPOONACULAR_API_KEY:
        return None
    
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "diet": "low-carb",  # 低碳水
        "maxCalories": 500,
        "number": 10,
        "addRecipeInformation": True,
        "fillIngredients": True
    }
    
    try:
        resp = requests.get(SPOONACULAR_URL, params=params, timeout=15)
        data = resp.json()
        recipes = data.get("results", [])
        if not recipes:
            return None
        
        recipe = random.choice(recipes)
        return {
            "name": recipe.get("title", "未知食谱"),
            "calories": recipe.get("calories", "未知"),
            "protein": f"{recipe.get('protein', '?')}g",
            "fat": f"{recipe.get('fat', '?')}g",
            "carbs": f"{recipe.get('carbs', '?')}g",
            "ingredients": "、".join([i["name"] for i in recipe.get("usedIngredients", [])[:5]]),
            "method": "详见：" + recipe.get("sourceUrl", "")
        }
    except Exception as e:
        print(f"API抓取失败: {e}")
        return None

def generate_recipe():
    """生成今日减脂食谱"""
    # 先尝试API
    recipe = fetch_api_recipe()
    
    # API失败则用本地库
    if not recipe:
        print("使用本地食谱库")
        recipe = random.choice(LOCAL_RECIPES)
    
    lines = [
        f"🥗 今日减脂食谱 | {datetime.now().strftime('%m月%d日')}",
        "=" * 30,
        "",
        f"📌 {recipe['name']}",
        f" 热量: {recipe['calories']}卡",
        f"🥩 蛋白质: {recipe['protein']} | 🧈 脂肪: {recipe['fat']} |  碳水: {recipe['carbs']}",
        "",
        " 食材:",
        f"   {recipe['ingredients']}",
        "",
        "‍ 做法:",
        f"   {recipe['method']}",
        "",
        " 小贴士: 少油少盐，搭配运动效果更佳！",
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
            print(f"✅ 推送成功: {title}")
            return True
        else:
            print(f" 推送失败: {result}")
            return False
    except Exception as e:
        print(f" 推送失败: {e}")
        return False

def main():
    print(f"🥗 减脂食谱开始 | {datetime.now()}")
    recipe = generate_recipe()
    push_serverchan("今日减脂食谱", recipe)
    print("✅ 完成")

if __name__ == "__main__":
    main()
