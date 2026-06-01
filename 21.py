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
        # 使用標準 52 張牌牌組
        deck = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10] * 4
        random.shuffle(deck)
        # 發初始牌（只抽一張）
        p1_hand = [deck.pop()]
        p2_hand = [deck.pop()]
        view = GameView(self.owner, None, deck, p1_hand, p2_hand, False)
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
        # 使用標準 52 張牌牌組
        deck = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10] * 4
        random.shuffle(deck)
        # 發初始牌（只抽一張）
        p1_hand = [deck.pop()]
        p2_hand = [deck.pop()]
        view = GameView(self.p1, interaction.user, deck, p1_hand, p2_hand, True)
        await interaction.response.edit_message(content="遊戲開始！", embed=view.get_embed("多人回合"), view=view)

# --- 3. 回合制操作介面 (GameView) ---
class GameView(View):
    def __init__(self, p1, p2, deck, p1_hand, p2_hand, is_multi):
        super().__init__(timeout=120)
        self.p1, self.p2 = p1, p2
        self.deck, self.is_multi = deck, is_multi
        self.p1_hand, self.p2_hand = p1_hand, p2_hand
        self.p1_stood, self.p2_stood = False, False
        self.turn = p1 # 當前回合玩家（多人模式）
        self.is_player_turn = True # 單人模式：True=玩家回合，False=電腦回合

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

    def get_embed(self, title, log_text=""):
        embed = discord.Embed(title=title, color=discord.Color.dark_purple())
        game_ended = (self.p1_stood and self.p2_stood)

        # 👤 玩家視角：看到自己的牌，看不到電腦的
        p1_display = f"{self.p1_hand} (總分: {sum(self.p1_hand)})"
        p1_status = " (已跳過)" if self.p1_stood else ""
        embed.add_field(name=f"👤 {self.p1.name}", value=p1_display + p1_status, inline=False)
        
        # 🤖 電腦視角：對手看到的只有隱藏的牌
        if game_ended:
            p2_display = f"{self.p2_hand} (總分: {sum(self.p2_hand)})"
        else:
            # 這裡把 [self.p2_hand[0], ?] 改成全隱藏或數量提示
            # 只告知對方有幾張牌，但完全不透漏牌值
            hidden_count = len(self.p2_hand)
            p2_display = f"🤖 電腦目前手上有 {hidden_count} 張牌 (皆為隱藏)"
            
        p2_status = " (已跳過)" if self.p2_stood else ""
        p2_title = f"👤 {self.p2.name}" if self.p2 else "🤖 電腦"
        embed.add_field(name=p2_title, value=p2_display + p2_status, inline=False)
        
        if log_text:
            embed.add_field(name="📜 戰況紀錄", value=log_text, inline=False)
        return embed

    def switch_turn(self):
        if self.is_multi:
            # 多人模式：正常切換
            if self.turn == self.p1:
                self.turn = self.p2
            else:
                self.turn = self.p1

    @discord.ui.button(label="抽牌", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: Button):
        # 1. 抽牌
        if self.is_multi:
            if self.turn == self.p1:
                self.p1_hand.append(self.deck.pop())
                log = f"🃏 {self.turn.name} 選擇了【抽牌】。"
            else:
                self.p2_hand.append(self.deck.pop())
                log = f"🃏 {self.turn.name} 選擇了【抽牌】。"
        else:
            self.p1_hand.append(self.deck.pop())
            log = f"🃏 {self.p1.name} 選擇了【抽牌】。"
        
        # 2. 換回合
        if self.is_multi:
            self.switch_turn()
            await interaction.response.edit_message(content='', embed=self.get_embed("回合更新", log), view=self)
        else:
            self.is_player_turn = False
            await interaction.response.edit_message(content='', embed=self.get_embed("處理中...", log), view=None)
            await self.computer_decision(interaction, log)

    @discord.ui.button(label="跳過", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: Button):
        # 記錄此玩家已跳過
        if self.is_multi:
            if self.turn == self.p1:
                self.p1_stood = True
                log = f"🃏 {self.turn.name} 選擇了【跳過】。"
            else:
                self.p2_stood = True
                log = f"🃏 {self.turn.name} 選擇了【跳過】。"
        else:
            self.p1_stood = True
            log = f"🃏 {self.p1.name} 選擇了【跳過】。"
        
        # 先回應交互
        await interaction.response.edit_message(content='', embed=self.get_embed("處理中...", log), view=None)
        
        # 檢查是否雙方都跳過
        if self.p1_stood and self.p2_stood:
            await self.show_result(interaction)
        elif self.is_multi:
            # 換回合
            self.switch_turn()
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                content='',
                embed=self.get_embed("換你了", log),
                view=self
            )
        else:
            # 單人模式：玩家跳過，輪到電腦
            self.is_player_turn = False
            await self.computer_decision(interaction, log)

    async def computer_decision(self, interaction, log):
        # 電腦算計玩家：根據玩家已抽牌數推測點數
        # 初始一張牌平均點數約 6，每多抽一張牌，電腦評估對手變大的機率
        my_total = sum(self.p2_hand)
        player_cards_count = len(self.p1_hand)
        
        # 智慧決策：如果對手抽牌越少，代表對手越可能拿到大牌或好牌
        # 電腦傾向於將自己的點數維持在 16~18 之間
        if my_total < 16:
            decision = "抽牌"
        elif my_total <= 18 and player_cards_count < 2:
            decision = "抽牌"  # 對手抽很少，電腦不敢賭，選擇搏一下
        else:
            decision = "跳過"

        await asyncio.sleep(1.2)
        
        if decision == "抽牌":
            new_card = self.deck.pop()
            self.p2_hand.append(new_card)
            log += f"\n🤖 電腦根據你的行為，決定【抽牌】。"
            self.is_player_turn = True  # 換回玩家
            await interaction.edit_original_response(embed=self.get_embed("電腦回合", log), view=self)
        else:
            self.p2_stood = True
            log += "\n🤖 電腦決定【跳過】。"
            if self.p1_stood:
                await self.show_result(interaction)
            else:
                self.is_player_turn = True
                await interaction.edit_original_response(embed=self.get_embed("輪到你了", log), view=self)

    async def show_result(self, interaction):
        p1_score = sum(self.p1_hand)
        p2_score = sum(self.p2_hand)
        
        # 判定勝負規則：超過 21 點者直接判輸，否則比大小
        if p1_score > 21 and p2_score > 21:
            res = "💥 雙方都爆掉，平手！"
        elif p1_score > 21:
            if self.p2:
                res = f"💥 你爆掉了，{self.p2.name} 獲勝！"
            else:
                res = "💥 你爆掉了，電腦獲勝！"
        elif p2_score > 21:
            res = f"🎉 電腦爆掉了，你獲勝！"
        elif p1_score > p2_score:
            res = f"🎉 你贏了！({p1_score} vs {p2_score})"
        elif p2_score > p1_score:
            if self.p2:
                res = f"😭 {self.p2.name} 獲勝！({p1_score} vs {p2_score})"
            else:
                res = f"😭 電腦獲勝！({p1_score} vs {p2_score})"
        else:
            res = "🤝 平手！"

        final_embed = discord.Embed(title=f"開牌結果：{res}", color=discord.Color.gold())
        final_embed.add_field(name=f"👤 {self.p1.name}", value=f"{self.p1_hand} ({p1_score} 點)", inline=False)
        p2_name = self.p2.name if self.p2 else "🤖 電腦"
        final_embed.add_field(name=p2_name, value=f"{self.p2_hand} ({p2_score} 點)", inline=False)
        
        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            content='',
            embed=final_embed,
            view=ResultView(self.p1, self.p2)
        )

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
