
import discord
from discord.ui import View, Button, button
import os
import re
from dotenv import load_dotenv

# --- 環境変数の読み込み ---
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
VERIFIED_ROLE_NAME = os.getenv('VERIFIED_ROLE_NAME')
ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID'))
AUTH_CHANNEL_ID = int(os.getenv('AUTH_CHANNEL_ID'))

# --- DiscordのIntents設定 ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)

# --- 承認/拒否ボタンのView ---
class AuthView(View):
    def __init__(self, target_user_id: int, x_username: str):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id
        self.x_username = x_username

    async def handle_action(self, interaction: discord.Interaction, action: str):
        target_user = await interaction.guild.fetch_member(self.target_user_id)
        if not target_user:
            await interaction.response.send_message("対象ユーザーが見つかりませんでした。", ephemeral=True)
            return

        if action == "approve":
            role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
            if not role:
                await interaction.response.send_message(f"エラー: 「{VERIFIED_ROLE_NAME}」ロールが見つかりません。", ephemeral=True)
                return
            try:
                await target_user.add_roles(role)
                status_text = f"✅ **承認済み** - {interaction.user.mention} が対応しました。"
                dm_message = f"あなたのXアカウント（`{self.x_username}`）の認証が承認されました！"
                response_message = f"{target_user.mention} を認証しました。"
            except discord.Forbidden:
                await interaction.response.send_message("エラー: ボットにロールを付与する権限がありません。", ephemeral=True)
                return
        else: # deny
            status_text = f"❌ **拒否済み** - {interaction.user.mention} が対応しました。"
            dm_message = f"申し訳ありませんが、あなたのXアカウント（`{self.x_username}`）の認証は拒否されました。"
            response_message = f"{target_user.mention} の認証を拒否しました。"

        self.clear_items()
        original_embed = interaction.message.embeds[0]
        original_embed.color = discord.Color.green() if action == "approve" else discord.Color.red()
        original_embed.description = status_text

        await interaction.message.edit(embed=original_embed, view=None)
        await interaction.response.send_message(response_message, ephemeral=True)
        try:
            await target_user.send(dm_message)
        except discord.Forbidden:
            pass # DMが送れなくてもOK

    @button(label="承認", style=discord.ButtonStyle.success, custom_id="auth_approve_new")
    async def approve(self, interaction: discord.Interaction, button: Button):
        await self.handle_action(interaction, "approve")

    @button(label="拒否", style=discord.ButtonStyle.danger, custom_id="auth_deny_new")
    async def deny(self, interaction: discord.Interaction, button: Button):
        await self.handle_action(interaction, "deny")

# --- ボットのイベントハンドラ ---
@client.event
async def on_ready():
    # ボット起動時にViewを再登録
    client.add_view(AuthView(target_user_id=0, x_username="")) 
    print(f'{client.user}としてログインしました')
    print(f"認証申請チャンネルID: {AUTH_CHANNEL_ID}")
    print(f"管理チャンネルID: {ADMIN_CHANNEL_ID}")

@client.event
async def on_message(message):
    # 指定された認証チャンネルでのみ動作 & ボット自身のメッセージは無視
    if message.channel.id != AUTH_CHANNEL_ID or message.author.bot:
        return

    # XのIDっぽいものを正規表現で探す (例: @user_name, user_name)
    match = re.match(r'^@?([a-zA-Z0-9_]{1,15})$', message.content.strip())
    if not match:
        # IDっぽくないメッセージは無視（もしくはエラー通知も可能）
        return

    x_username = match.group(1)
    admin_channel = client.get_channel(ADMIN_CHANNEL_ID)

    if not admin_channel:
        print(f"エラー: 管理チャンネルID({ADMIN_CHANNEL_ID})が見つかりません。")
        return

    # 運営チャンネルに通知を送信
    view = AuthView(target_user_id=message.author.id, x_username=x_username)
    embed = discord.Embed(
        title="認証リクエスト",
        description="以下のユーザーからXアカウントの認証リクエストが届きました。",
        color=discord.Color.blue()
    )
    embed.add_field(name="申請者", value=message.author.mention, inline=False)
    embed.add_field(name="X (Twitter) ID", value=f"[{x_username}](https://twitter.com/{x_username})", inline=False)
    
    await admin_channel.send(embed=embed, view=view)
    
    # ユーザーにDMで通知
    try:
        await message.author.send(f"Xアカウント `{x_username}` の認証リクエストを送信しました。運営が確認するまでしばらくお待ちください。")
    except discord.Forbidden:
        # DMが送れない場合は仕方ない
        pass

    # 元のメッセージを削除
    try:
        await message.delete()
    except discord.Forbidden:
        print(f"エラー: チャンネル({message.channel.name})のメッセージを削除する権限がありません。")
    except discord.NotFound:
        pass # すでに消えている場合は無視

# --- ボットの実行 ---
client.run(TOKEN)
