import discord
import os
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 取得台灣時區 (UTC+8)
tz_tw = timezone(timedelta(hours=8))

# 連線到雲端 MongoDB (環境變數)
MONGO_URI = os.getenv('MONGO_URI')
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['checkin_bot_db']  # 資料庫名稱
users_col = db['users']              # 使用者打卡紀錄資料表
quotes_col = db['quotes']            # 語錄資料表

# 預設語錄庫 (如果資料庫是空的，會自動寫入)
DEFAULT_QUOTES = {
    "general": [
        "恭喜又活了一天！",
        "打卡成功，但你的代碼還是有 Bug 喔。",
        "連續打卡又有什麼用呢？人生還不是一樣難。",
        "不錯喔，竟然沒有忘記打卡，我還以為你放棄人生了。",
        "打卡成功！你的肝正在為你默哀。",
        "活著就是勝利，雖然看起來像是苟延殘喘。",
        "今天也辛苦了，明天準備繼續當社畜吧！"
    ],
    "fitness": [
        "肌肉不是一天練成的，但肥肉是。",
        "終於離開電腦桌去運動了嗎？",
        "再練下去你的鍵盤都要被你敲壞了。",
        "恭喜！希望明天的你不會全身痠痛到下不了床。",
        "不錯喔，繼續練，遲早有一天能手撕 Bug。",
        "流汗的感覺不錯吧？總比流眼淚好。",
        "今天有乖乖運動，今晚可以多吃一塊雞排了（誤）。"
    ]
}

def init_quotes():
    """初始化語錄庫，確保資料庫裡有預設句子"""
    if quotes_col.count_documents({}) == 0:
        quotes_col.insert_one(DEFAULT_QUOTES)

@client.event
async def on_ready():
    init_quotes()
    print(f'目前登入身份：{client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    msg_text = message.content

    # ==========================================
    # 1. 動態新增語錄功能
    # ==========================================
    if msg_text.startswith("新增語錄 "):
        new_quote = msg_text.replace("新增語錄 ", "").strip()
        if new_quote:
            quotes_col.update_one({}, {"$push": {"general": new_quote}})
            await message.reply(f"✅ 成功將「{new_quote}」加入一般打卡語錄庫！")
        return

    if msg_text.startswith("新增健身語錄 "):
        new_quote = msg_text.replace("新增健身語錄 ", "").strip()
        if new_quote:
            quotes_col.update_one({}, {"$push": {"fitness": new_quote}})
            await message.reply(f"✅ 成功將「{new_quote}」加入健身打卡語錄庫！")
        return

    # ==========================================
    # 2. 判斷打卡類型
    # ==========================================
    is_fitness = "打卡健身" in msg_text or "健身打卡" in msg_text
    is_general = "打卡" in msg_text and not is_fitness

    if not (is_fitness or is_general):
        return

    user_id = str(message.author.id)
    today_str = datetime.now(tz_tw).strftime('%Y-%m-%d')
    today_date = datetime.strptime(today_str, '%Y-%m-%d').date()

    # 從雲端資料庫撈取該使用者的紀錄
    user_data = users_col.find_one({"user_id": user_id})
    
    # 如果是新使用者，初始化資料
    if not user_data:
        user_data = {
            "user_id": user_id,
            "last_date": "2000-01-01", "streak": 0,
            "fitness_last_date": "2000-01-01", "fitness_streak": 0
        }
        users_col.insert_one(user_data)

    # 依照打卡類型設定變數
    db_quotes = quotes_col.find_one({}) or DEFAULT_QUOTES
    if is_fitness:
        date_key = "fitness_last_date"
        streak_key = "fitness_streak"
        talk_list = db_quotes.get("fitness", DEFAULT_QUOTES["fitness"])
        title = "🏋️ 健身打卡"
    else:
        date_key = "last_date"
        streak_key = "streak"
        talk_list = db_quotes.get("general", DEFAULT_QUOTES["general"])
        title = "📅 一般打卡"

    last_date_str = user_data[date_key]
    last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()

    if today_date == last_date:
        await message.reply(f"你今天已經完成【{title}】了，明天再來吧！")
        return

    if today_date == last_date + timedelta(days=1):
        new_streak = user_data[streak_key] + 1
    else:
        new_streak = 1

    # 更新雲端資料庫中的數據
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {date_key: today_str, streak_key: new_streak}}
    )

    # 隨機抽取一句垃圾話
    talk = random.choice(talk_list) if talk_list else "找不到語錄，但我還是恭喜你打卡。"
    
    # 回覆訊息
    reply_msg = f"{title} 確認！目前連續天數：**{new_streak}** 天\n💬 {talk}"
    await message.reply(reply_msg)

# 讀取 Discord Token 啟動
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)
else:
    print("找不到 DISCORD_TOKEN 環境變數！")