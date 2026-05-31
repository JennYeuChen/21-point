import discord
from discord.ext import commands
from discord.ui import Button, View
import os
import random
import threading
from flask import Flask

app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"

# --- 遊戲邏輯 ---
def get_deck():
    # 這裡直接用數字列表，不再處理花色，確保顯示乾淨
    deck = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10] * 2
    random.shuffle(deck)
    return deck

def calculate_score(hand):
    score = sum(hand)
    aces = hand.count(1)
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score

class BlackjackView(View):
    def __init__(self, owner, deck, user_hand, dealer_hand):
        super().__init__(timeout=60)
        self.owner = owner
        self.deck = deck
        self.user_hand = user_hand
        self.dealer_hand = dealer_hand

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner

    def get_embed(self, title):
        embed = discord.Embed(title=title, color=discord.Color.blue())
        embed.add_field(name="你的手牌", value=f"{self.user_hand} (總分: {calculate_score(self.user_hand)})", inline=False)
        embed.add_field(name="莊家手牌", value=f"[{self.dealer_hand[0]}, ?]", inline=False)
        return embed

    @discord.ui.button(label="抽牌", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        self.user_hand.append(self.deck.pop())
        if calculate_score(self.user_hand) > 21:
            await interaction.response.edit_message(embed=self.get_embed("💥 爆掉！莊家獲勝"), view=None)
            self.stop()
        else:
            await interaction.response.edit_message(embed=self.get_embed("進行中..."), view=self)

    @discord.ui.button(label="跳過", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        while calculate_score(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        u_s, d_s = calculate_score(self.user_hand), calculate_score(self.dealer_hand)
        
        if u_s > 21: res = "💥 爆掉！莊家獲勝"
        elif d_s > 21 or u_s > d_s: res = "🎉 你贏了！"
        elif u_s == d_s: res = "平手！"
        else: res = "😭 莊家獲勝"
        
        embed = discord.Embed(title=f"結果：{res}", color=discord.Color.gold())
        embed.add_field(name="你的最終點數", value=str(u_s))
        embed.add_field(name="莊家最終點數", value=str(d_s))
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

# --- Bot 設定 ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name="21")
async def bj(ctx):
    thread = await ctx.message.create_thread(name=f"{ctx.author.name} 的 21 點")
    deck = get_deck()
    view = BlackjackView(ctx.author, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()])
    await thread.send(embed=view.get_embed("遊戲開始"), view=view)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
