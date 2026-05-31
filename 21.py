import discord
from discord.ext import commands
from discord.ui import Button, View
import os
import random
import threading
from flask import Flask

# --- Flask 伺服器 (防止休眠) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)

# --- 1. 模式選擇與遊戲開始 (StartView) ---
class StartView(View):
    def __init__(self, owner):
        super().__init__(timeout=60)
        self.owner = owner

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner

    @discord.ui.button(label="單人模式", style=discord.ButtonStyle.primary)
    async def single(self, interaction: discord.Interaction, button: Button):
        deck = [random.randint(1, 10) for _ in range(52)]
        # 單人：玩家手牌 + 莊家手牌
        view = GameView(self.owner, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()], is_multi=False)
        await interaction.response.edit_message(content='', embed=view.get_embed("單人模式開始"), view=view)

    @discord.ui.button(label="多人模式", style=discord.ButtonStyle.secondary)
    async def multi(self, interaction: discord.Interaction, button: Button):
        # 多人：初始化多人牌局，這裡可擴充加入更多玩家
        deck = [random.randint(1, 10) for _ in range(52)]
        view = GameView(self.owner, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()], is_multi=True)
        await interaction.response.edit_message(content='', embed=view.get_embed("多人模式開始 (待其他玩家點擊加入)"), view=view)

# --- 2. 多人對戰邏輯 (GameView) ---
class GameView(View):
    def __init__(self, owner, deck, user_hand, dealer_hand, is_multi):
        super().__init__(timeout=120)
        self.owner, self.deck = owner, deck
        self.user_hand, self.dealer_hand = user_hand, dealer_hand
        self.is_multi = is_multi
        self.players_stood = False # 在多人模式中，用於判斷是否全員跳過

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner

    def get_embed(self, title):
        embed = discord.Embed(title=title, color=discord.Color.green())
        embed.add_field(name="你的牌", value=f"{self.user_hand} (點數: {sum(self.user_hand)})")
        embed.add_field(name="莊家", value=f"[{self.dealer_hand[0]}, ?]")
        return embed

    @discord.ui.button(label="抽牌", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        self.user_hand.append(self.deck.pop())
        if sum(self.user_hand) > 21:
            await interaction.response.edit_message(content='', embed=self.get_embed("💥 爆掉！莊家勝"), view=ResultView(self.owner))
        else:
            await interaction.response.edit_message(content='', embed=self.get_embed("抽牌中..."), view=self)

    @discord.ui.button(label="跳過", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if not self.is_multi:
            # 單人：直接進入莊家補牌
            while sum(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())
            await self.show_result(interaction)
        else:
            # 多人：這裡可加入邏輯，檢查是否所有玩家都 stand，這裡簡化為直接開牌
            await self.show_result(interaction)

    async def show_result(self, interaction):
        u_s, d_s = sum(self.user_hand), sum(self.dealer_hand)
        res = "🎉 你贏了！" if d_s > 21 or u_s > d_s else "😭 莊家勝" if u_s < d_s else "平手！"
        embed = discord.Embed(title=f"開牌結果：{res}", color=discord.Color.gold())
        embed.add_field(name="分數", value=f"你: {u_s} / 莊家: {d_s}")
        await interaction.response.edit_message(content='', embed=embed, view=ResultView(self.owner))

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

# --- 4. 指令進入點 (更新版) ---
@bot.command(name="21")
async def start_game(ctx):
    thread = await ctx.message.create_thread(name=f"{ctx.author.name} 的牌局")
    await thread.send("請選擇遊戲模式：", view=StartView(ctx.author))

# --- 啟動 ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
