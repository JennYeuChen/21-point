import discord
from discord.ext import commands
from discord.ui import Button, View
import os
import random
import asyncio
import threading
from flask import Flask

# --- Flask 伺服器 (防止休眠) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)

# --- 1. 遊戲入口與多人等待室 (StartView) ---
class StartView(View):
    def __init__(self, owner):
        super().__init__(timeout=60)
        self.owner = owner
        self.players = [owner] # 紀錄玩家名單

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True # 所有人都可以點擊加入按鈕

    @discord.ui.button(label="單人模式", style=discord.ButtonStyle.primary)
    async def single(self, interaction: discord.Interaction, button: Button):
        deck = [random.randint(1, 10) for _ in range(52)]
        view = GameView(self.owner, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()], False)
        await interaction.response.edit_message(content='', embed=view.get_embed("🎮 單人模式進行中"), view=view)

    @discord.ui.button(label="多人模式 (加入遊戲)", style=discord.ButtonStyle.secondary)
    async def multi(self, interaction: discord.Interaction, button: Button):
        if interaction.user not in self.players:
            self.players.append(interaction.user)
            await interaction.response.edit_message(content=f"已加入玩家: {', '.join([p.name for p in self.players])}", view=self)
        
        if len(self.players) >= 2:
            deck = [random.randint(1, 10) for _ in range(52)]
            view = GameView(self.owner, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()], True)
            await interaction.edit_original_response(content='', embed=view.get_embed("多人對決開始"), view=view)

# --- 2. 視覺化莊家過場 (GameView) ---
class GameView(View):
    def __init__(self, owner, deck, user_hand, dealer_hand, is_multi):
        super().__init__(timeout=120)
        self.owner, self.deck = owner, deck
        self.user_hand, self.dealer_hand = user_hand, dealer_hand
        self.is_multi = is_multi

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner

    def get_embed(self, title, status="等待中"):
        embed = discord.Embed(title=title, color=discord.Color.dark_teal())
        embed.add_field(name="🃏 你的手牌", value=f"**{self.user_hand}** | 點數: {sum(self.user_hand)}", inline=False)
        embed.add_field(name="🤖 莊家狀態", value=f"[{self.dealer_hand[0]}, ?] | {status}", inline=False)
        return embed

    @discord.ui.button(label="抽牌", style=discord.ButtonStyle.blurple)
    async def hit(self, interaction: discord.Interaction, button: Button):
        self.user_hand.append(self.deck.pop())
        if sum(self.user_hand) > 21:
            await interaction.response.edit_message(content='', embed=self.get_embed("💥 爆掉啦！", "莊家獲勝"), view=ResultView(self.owner))
        else:
            await interaction.response.edit_message(content='', embed=self.get_embed("遊戲進行中...", "等待中"), view=self)

    @discord.ui.button(label="跳過 (開牌)", style=discord.ButtonStyle.gray)
    async def stand(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content='', embed=self.get_embed("結算中...", "莊家思考中..."), view=None)
        
        # 模擬莊家動作的過場
        while sum(self.dealer_hand) < 17:
            await asyncio.sleep(1) # 讓玩家看到莊家思考的過場
            self.dealer_hand.append(self.deck.pop())
            await interaction.edit_original_response(content='', embed=self.get_embed("結算中...", f"莊家抽牌: {self.dealer_hand}"))
        
        u_s, d_s = sum(self.user_hand), sum(self.dealer_hand)
        res = "🎉 你贏了！" if d_s > 21 or u_s > d_s else "😭 莊家勝" if u_s < d_s else "平手！"
        final_embed = discord.Embed(title=f"最終開牌結果：{res}", color=discord.Color.gold())
        final_embed.add_field(name="你的分數", value=str(u_s))
        final_embed.add_field(name="莊家分數", value=str(d_s))
        await interaction.edit_original_response(content='', embed=final_embed, view=ResultView(self.owner))

# --- 3. 重賽功能 (ResultView) ---
class ResultView(View):
    def __init__(self, owner):
        super().__init__(timeout=60)
        self.owner = owner
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner
    
    @discord.ui.button(label="重賽", style=discord.ButtonStyle.success)
    async def restart(self, interaction: discord.Interaction, button: Button):
        # 回到模式選擇介面
        await interaction.response.edit_message(content='', embed=discord.Embed(title="選擇遊戲模式", color=discord.Color.blue()), view=StartView(self.owner))

# --- 機器人設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"機器人已啟動: {bot.user}")

# --- 4. 指令進入點 ---
@bot.command(name="21")
async def start_game(ctx):
    thread = await ctx.message.create_thread(name=f"🃏 {ctx.author.name} 的賭局")
    # 這裡的 start_view 會處理單人/多人邏輯
    await thread.send("請選擇遊戲模式：", view=StartView(ctx.author))

# --- 啟動 ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
