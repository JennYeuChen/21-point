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

# --- 第一區塊：核心遊戲介面 (GameView) ---
class GameView(View):
    def __init__(self, owner, deck, user_hand, dealer_hand):
        super().__init__(timeout=60)
        self.owner, self.deck = owner, deck
        self.user_hand, self.dealer_hand = user_hand, dealer_hand

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner

    def get_embed(self, title):
        score = sum(self.user_hand)
        embed = discord.Embed(title=title, color=discord.Color.blue())
        embed.add_field(name="你的牌", value=f"{self.user_hand} (點數: {score})", inline=False)
        embed.add_field(name="莊家", value=f"[{self.dealer_hand[0]}, ?]", inline=False)
        return embed

    @discord.ui.button(label="抽牌", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        self.user_hand.append(self.deck.pop())
        if sum(self.user_hand) > 21:
            await interaction.response.edit_message(content='', embed=self.get_embed("💥 爆掉！莊家勝"), view=ResultView(self.owner))
        else:
            await interaction.response.edit_message(content='', embed=self.get_embed("進行中..."), view=self)

    @discord.ui.button(label="跳過", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        while sum(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        u_s, d_s = sum(self.user_hand), sum(self.dealer_hand)
        res = "🎉 你贏了！" if d_s > 21 or u_s > d_s else "😭 莊家勝"
        embed = discord.Embed(title=f"結果：{res}", color=discord.Color.gold())
        embed.add_field(name="分數", value=f"你: {u_s} / 莊家: {d_s}")
        await interaction.response.edit_message(content='', embed=embed, view=ResultView(self.owner))

# --- 第二區塊：重賽功能 (ResultView) ---
class ResultView(View):
    def __init__(self, owner):
        super().__init__(timeout=60)
        self.owner = owner
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner
    
    @discord.ui.button(label="重賽", style=discord.ButtonStyle.success)
    async def restart(self, interaction: discord.Interaction, button: Button):
        deck = [random.randint(1, 10) for _ in range(52)]
        view = GameView(self.owner, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()])
        await interaction.response.edit_message(content='', embed=view.get_embed("新局開始"), view=view)

# --- 機器人設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"機器人已啟動: {bot.user}")

# --- 第三區塊：指令啟動邏輯 (Command) ---
@bot.command(name="21")
async def start_game(ctx):
    thread = await ctx.message.create_thread(name=f"{ctx.author.name} 的 21 點")
    deck = [random.randint(1, 10) for _ in range(52)]
    view = GameView(ctx.author, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()])
    await thread.send(content='', embed=view.get_embed("遊戲開始"), view=view)

# --- 啟動 ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
