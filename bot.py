import os
import asyncio
import traceback
import discord
from discord.ext import commands
from dotenv import load_dotenv  # عشان نقرأ .env

# نحمّل القيم من ملف .env
load_dotenv()

# ====== CONFIG ======
TOKEN = os.getenv("DISCORD_TOKEN")              # يجي من .env
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))    # يجي من .env
GAME_NAME = "Generals Zero Hour"

SMALL_IMAGE = "https://media.discordapp.net/attachments/1394027766638444554/1434619377424142439/ASDTSWZUHDFT.png?format=webp&quality=lossless"
LARGE_IMAGE = "https://media.discordapp.net/attachments/1394027766638444554/1434619377826791524/cropped-image.png?format=webp&quality=lossless"

DELETE_AFTER_SECONDS = 15 * 60
PANEL_TITLE = "Generals Control Panel"
# =====================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

panel_message_id: int | None = None


# =================================================================
# 1) رسالة اللعبة + الأزرار
# =================================================================
class LFGView(discord.ui.View):
    def __init__(self, host_id: int, host_name: str, game_type: str, radmin_vbn: str, max_players: int):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.game_type = game_type
        self.radmin_vbn = radmin_vbn
        self.max_players = max_players
        self.members: dict[int, str] = {host_id: host_name}
        self.closed = False
        self._refresh_buttons()

    def _slots_left(self) -> int:
        return max(0, self.max_players - len(self.members))

    def _players_list_green(self) -> str:
        if not self.members:
            return "```diff\n- No players yet.\n```"
        lines = "\n".join(f"+ {name}" for name in self.members.values())
        return f"```diff\n{lines}\n```"

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="**GENERALS ZERO HOUR CREATE GAME**",
            color=0xff0000,
        )
        embed.set_thumbnail(url=SMALL_IMAGE)

        table_text = (
            "```diff\n"
            f"- GAME    | {self.game_type}\n"
            f"- RADMIN  | {self.radmin_vbn}\n"
            f"- SLOTS   | {self._slots_left()}\n"
            "```"
        )
        embed.description = "**MATCH INFO**\n" + table_text

        embed.add_field(
            name="**PLAYERS**",
            value=self._players_list_green(),
            inline=False
        )

        embed.set_image(url=LARGE_IMAGE)
        return embed

    def _refresh_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "join":
                    child.disabled = self.closed or len(self.members) >= self.max_players
                elif child.custom_id in ("leave", "close"):
                    child.disabled = self.closed

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("This game is closed.", ephemeral=True)

        uid = interaction.user.id
        if uid in self.members:
            return await interaction.response.send_message("You are already in the list.", ephemeral=True)

        if len(self.members) >= self.max_players:
            return await interaction.response.send_message("Lobby is full.", ephemeral=True)

        self.members[uid] = interaction.user.display_name
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, custom_id="leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            return await interaction.response.send_message("This game is closed.", ephemeral=True)

        uid = interaction.user.id
        if uid not in self.members:
            return await interaction.response.send_message("You are not in the list.", ephemeral=True)

        if uid == self.host_id:
            return await interaction.response.send_message("Host cannot leave. You can close the game.", ephemeral=True)

        del self.members[uid]
        self._refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            return await interaction.response.send_message("Only the host can close this game.", ephemeral=True)

        try:
            await interaction.message.delete()
            return
        except (discord.Forbidden, discord.NotFound):
            self.closed = True
            self._refresh_buttons()
            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self
            )


# =================================================================
# 2) المودال
# =================================================================
class CreateGameModal(discord.ui.Modal, title="Create Generals Game | إنشاء لعبة جنرال"):
    game_type = discord.ui.TextInput(
        label="GAME TYPE | نوع اللعبة",
        placeholder="3v3 / 2v2 / 1v1 / FFA",
        required=True,
        max_length=50,
    )
    radmin_vbn = discord.ui.TextInput(
        label="RADMIN VBN | الرادمن",
        placeholder="-WF| 123456",
        required=True,
        max_length=100,
    )
    players_count = discord.ui.TextInput(
        label="PLAYERS COUNT | عدد اللاعبين",
        placeholder="3",
        required=True,
        max_length=2,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            try:
                needed = int(self.players_count.value)
                max_players = needed + 1
            except ValueError:
                max_players = 4

            view = LFGView(
                host_id=interaction.user.id,
                host_name=interaction.user.display_name,
                game_type=self.game_type.value,
                radmin_vbn=self.radmin_vbn.value,
                max_players=max_players,
            )
            embed = view.build_embed()

            try:
                await interaction.response.send_message(
                    content="@everyone",
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    embed=embed,
                    view=view,
                )

        except Exception as e:
            print("Modal error:", e)
            traceback.print_exc()
            if interaction.response.is_done():
                await interaction.followup.send("Something went wrong while creating the game.", ephemeral=True)
            else:
                await interaction.response.send_message("Something went wrong while creating the game.", ephemeral=True)


# =================================================================
# 3) لوحة التحكم
# =================================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Game", style=discord.ButtonStyle.primary, custom_id="create_game_btn")
    async def create_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(CreateGameModal())
        except Exception as e:
            print("Button error:", e)
            traceback.print_exc()
            if interaction.response.is_done():
                await interaction.followup.send("I couldn't open the form.", ephemeral=True)
            else:
                await interaction.response.send_message("I couldn't open the form.", ephemeral=True)


# =================================================================
# 4) on_ready → إرسال اللوحة
# =================================================================
@bot.event
async def on_ready():
    global panel_message_id
    print(f"✅ Logged in as {bot.user}")

    # عشان الأزرار تبقى شغّالة بعد الريستارت
    bot.add_view(PanelView())

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("⚠️ Channel not found. Check CHANNEL_ID")
        return

    # نحذف اللوحات القديمة
    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.embeds and msg.embeds[0].title == PANEL_TITLE:
            try:
                await msg.delete()
            except:
                pass

    embed = discord.Embed(
        title=PANEL_TITLE,
        description="Click the button below to create a game.",
        color=0x000000,
    )
    embed.set_image(url=LARGE_IMAGE)
    embed.set_thumbnail(url=SMALL_IMAGE)

    msg = await channel.send(embed=embed, view=PanelView())
    panel_message_id = msg.id


# =================================================================
# 5) حذف الرسائل بعد 15 دقيقة
# =================================================================
@bot.event
async def on_message(message: discord.Message):
    if message.id == panel_message_id:
        return
    asyncio.create_task(delete_after_delay(message))
    await bot.process_commands(message)


async def delete_after_delay(message: discord.Message):
    await asyncio.sleep(DELETE_AFTER_SECONDS)
    if message.id == panel_message_id or message.pinned:
        return
    try:
        await message.delete()
    except:
        pass


# =================================================================
# تشغيل البوت
# =================================================================
bot.run(TOKEN)
