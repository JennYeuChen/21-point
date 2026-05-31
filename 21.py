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

# --- 1. 遊戲入口 (StartView) ---
class StartView(View):
    def __init__(self, owner):
        super().__init__(timeout=60)
        self.owner = owner

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.owner

    @discord.ui.button(label="單人模式", style=discord.ButtonStyle.primary)
    async def single(self, interaction: discord.Interaction, button: Button):
        deck = [random.randint(1, 10) for _ in range(52)]
        view = GameView(self.owner, None, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()], False)
        await interaction.response.edit_message(content='', embed=view.get_embed("單人對局中"), view=view)

    @discord.ui.button(label="多人模式", style=discord.ButtonStyle.secondary)
    async def multi(self, interaction: discord.Interaction, button: Button):
        # 建立一個新訊息讓第二個人加入
        await interaction.response.send_message("等待第二位玩家加入...", view=JoinView(self.owner))

# --- 2. 加入遊戲 (JoinView) ---
class JoinView(View):
    def __init__(self, p1):
        super().__init__(timeout=60)
        self.p1 = p1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    @discord.ui.button(label="點我加入遊戲", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: Button):
        if interaction.user == self.p1:
            return await interaction.response.send_message("不能自己跟自己玩！", ephemeral=True)
        deck = [random.randint(1, 10) for _ in range(52)]
        view = GameView(self.p1, interaction.user, deck, [deck.pop(), deck.pop()], [deck.pop(), deck.pop()], True)
        await interaction.response.edit_message(content="遊戲開始！", embed=view.get_embed("多人回合"), view=view)

# --- 3. 回合制操作介面 (GameView) ---
class GameView(View):
    def __init__(self, p1, p2, deck, p1_hand, p2_hand, is_multi):
        super().__init__(timeout=120)
        self.p1, self.p2 = p1, p2
        self.deck, self.is_multi = deck, is_multi
        self.p1_hand, self.p2_hand = p1_hand, p2_hand
        self.p1_stood, self.p2_stood = False, False
        self.turn = p1 # 當前回合玩家

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 如果是單人模式，只有 p1 能操作
        if not self.is_multi:
            if interaction.user != self.p1:
                await interaction.response.send_message("這是你的單人遊戲！", ephemeral=True)
                return False
            return True
        
        # 多人模式：確保只有當前回合的人能動
        if interaction.user != self.turn:
            await interaction.response.send_message("現在不是你的回合！", ephemeral=True)
            return False
        return True

    def get_embed(self, title):
        embed = discord.Embed(title=title, color=discord.Color.dark_purple())
        p1_status = " (已跳過)" if self.p1_stood else ""
        p2_status = " (已跳過)" if self.p2_stood else ""
        embed.add_field(name=f"{self.p1.name} (玩家1)", value=f"{self.p1_hand} (點數: {sum(self.p1_hand)}){p1_status}", inline=False)
        embed.add_field(name=f"{self.p2.name if self.p2 else '電腦'} (玩家2)", value=f"{self.p2_hand} (點數: {sum(self.p2_hand)}){p2_status}", inline=False)
        embed.add_field(name="當前回合", value=f"{self.turn.name if self.turn else '等待中'}", inline=False)
        return embed

    def get_current_hand(self):
        if self.turn == self.p1:
            return self.p1_hand
        else:
            return self.p2_hand

    def set_current_stood(self):
        if self.turn == self.p1:
            self.p1_stood = True
        else:
            self.p2_stood = True

    def switch_turn(self):
        if self.turn == self.p1:
            self.turn = self.p2
        else:
            self.turn = self.p1

    async def check_game_end(self, interaction):
        # 檢查是否雙方都跳過或爆掉
        p1_bust = sum(self.p1_hand) > 21
        p2_bust = sum(self.p2_hand) > 21
        
        if (self.p1_stood and self.p2_stood) or p1_bust or p2_bust:
            # 遊戲結束
            await self.show_result(interaction)
            return True
        return False

    @discord.ui.button(label="抽牌", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        # 依照玩家身份存牌
        if self.is_multi:
            if self.turn == self.p1:
                self.p1_hand.append(self.deck.pop())
                if sum(self.p1_hand) > 21:
                    self.p1_stood = True
            else:
                self.p2_hand.append(self.deck.pop())
                if sum(self.p2_hand) > 21:
                    self.p2_stood = True
        else:
            # 單人模式
            self.p1_hand.append(self.deck.pop())
            if sum(self.p1_hand) > 21:
                self.p1_stood = True
        
        # 檢查遊戲是否結束
        if await self.check_game_end(interaction):
            return
        
        if self.is_multi:
            # 多人模式：換人
            self.switch_turn()
            await interaction.response.edit_message(content='', embed=self.get_embed("回合更新"), view=self)
        else:
            # 單人模式：電腦回合
            await interaction.response.edit_message(content='', embed=self.get_embed("電腦思考中..."), view=None)
            await self.ai_turn(interaction)

    @discord.ui.button(label="跳過", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        # 紀錄此玩家已跳過
        if self.is_multi:
            self.set_current_stood()
        else:
            self.p1_stood = True
        
        # 檢查是否雙方都跳過
        if await self.check_game_end(interaction):
            return
        
        if self.is_multi:
            # 多人模式：換人
            self.switch_turn()
            await interaction.response.edit_message(content='', embed=self.get_embed("回合更新"), view=self)
        else:
            # 單人模式：電腦回合
            await interaction.response.edit_message(content='', embed=self.get_embed("電腦思考中..."), view=None)
            await self.ai_turn(interaction)

    async def ai_turn(self, interaction):
        # 電腦自動決策：點數小於17就抽牌
        await asyncio.sleep(1)
        while sum(self.p2_hand) < 17:
            self.p2_hand.append(self.deck.pop())
            await asyncio.sleep(1)
            await interaction.edit_original_response(content='', embed=self.get_embed("電腦回合中..."))
        
        self.p2_stood = True
        
        # 檢查遊戲是否結束
        if not await self.check_game_end_ai(interaction):
            self.turn = self.p1
            await interaction.edit_original_response(content='', embed=self.get_embed("輪到你了"), view=self)

    async def check_game_end_ai(self, interaction):
        # 檢查是否雙方都跳過或爆掉
        p1_bust = sum(self.p1_hand) > 21
        p2_bust = sum(self.p2_hand) > 21
        
        if (self.p1_stood and self.p2_stood) or p1_bust or p2_bust:
            # 遊戲結束
            await self.show_result_ai(interaction)
            return True
        return False

    async def show_result_ai(self, interaction):
        p1_score = sum(self.p1_hand)
        p2_score = sum(self.p2_hand)
        
        # 判斷結果
        if p1_score > 21 and p2_score > 21:
            res = "雙方都爆掉！平手！"
        elif p1_score > 21:
            res = f"🎉 電腦贏了！"
        elif p2_score > 21:
            res = f"🎉 {self.p1.name} 贏了！"
        elif p1_score > p2_score:
            res = f"🎉 {self.p1.name} 贏了！"
        elif p2_score > p1_score:
            res = f"🎉 電腦贏了！"
        else:
            res = "平手！"
        
        final_embed = discord.Embed(title=f"遊戲結束！", color=discord.Color.gold())
        final_embed.add_field(name="結果", value=res, inline=False)
        final_embed.add_field(name=f"{self.p1.name}", value=f"{self.p1_hand} ({p1_score} 點)", inline=True)
        final_embed.add_field(name="電腦", value=f"{self.p2_hand} ({p2_score} 點)", inline=True)
        
        await interaction.edit_original_response(content='', embed=final_embed, view=ResultView(self.p1, self.p2))

    async def show_result(self, interaction):
        p1_score = sum(self.p1_hand)
        p2_score = sum(self.p2_hand)
        
        # 判斷結果
        if p1_score > 21 and p2_score > 21:
            res = "雙方都爆掉！平手！"
        elif p1_score > 21:
            res = f"🎉 {self.p2.name} 贏了！"
        elif p2_score > 21:
            res = f"🎉 {self.p1.name} 贏了！"
        elif p1_score > p2_score:
            res = f"🎉 {self.p1.name} 贏了！"
        elif p2_score > p1_score:
            res = f"🎉 {self.p2.name} 贏了！"
        else:
            res = "平手！"
        
        final_embed = discord.Embed(title=f"遊戲結束！", color=discord.Color.gold())
        final_embed.add_field(name="結果", value=res, inline=False)
        final_embed.add_field(name=f"{self.p1.name}", value=f"{self.p1_hand} ({p1_score} 點)", inline=True)
        final_embed.add_field(name=f"{self.p2.name if self.p2 else '電腦'}", value=f"{self.p2_hand} ({p2_score} 點)", inline=True)
        
        await interaction.response.edit_message(content='', embed=final_embed, view=ResultView(self.p1, self.p2))

# --- 4. 重賽功能 (ResultView) ---
class ResultView(View):
    def __init__(self, p1, p2):
        super().__init__(timeout=60)
        self.p1, self.p2 = p1, p2
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.p1 or (self.p2 and interaction.user == self.p2)
    
    @discord.ui.button(label="重賽", style=discord.ButtonStyle.success)
    async def restart(self, interaction: discord.Interaction, button: Button):
        # 回到模式選擇介面
        await interaction.response.edit_message(content='', embed=discord.Embed(title="選擇遊戲模式", color=discord.Color.blue()), view=StartView(self.p1))

# --- 機器人設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"機器人已啟動: {bot.user}")

# --- 5. 指令進入點 ---
@bot.command(name="21")
async def start_game(ctx):
    thread = await ctx.message.create_thread(name=f"🃏 {ctx.author.name} 的賭局")
    await thread.send("請選擇遊戲模式：", view=StartView(ctx.author))

# --- 啟動 ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
