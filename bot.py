import base64
import json
import discord
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

support_roles = {}

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

def parse_color(color_name: str) -> discord.Color:
    if not color_name:
        return discord.Color.blue()
    
    c = color_name.strip().lower()
    if "אדום" in c:
        return discord.Color.red()
    elif "ירוק" in c:
        return discord.Color.green()
    elif "זהב" in c or "צהוב" in c:
        return discord.Color.gold()
    elif "סגול" in c:
        return discord.Color.purple()
    elif "שחור" in c:
        return discord.Color.dark_theme()
    elif "כתום" in c:
        return discord.Color.orange()
    elif "ורוד" in c:
        return discord.Color.magenta()
    else:
        return discord.Color.blue()


class TicketControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    def can_manage(self, user: discord.Member) -> bool:
        if user.guild_permissions.administrator:
            return True
        role_id = support_roles.get(self.guild_id)
        if role_id and any(r.id == role_id for r in user.roles):
            return True
        return False

    @discord.ui.button(label="סגור טיקט", style=discord.ButtonStyle.danger, custom_id="close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.can_manage(interaction.user):
            await interaction.response.send_message("❌ רק צוות ההנהלה או תפקיד התמיכה יכולים להשתמש בכפתור זה!", ephemeral=True)
            return
        
        await interaction.response.send_message("🔒 הטיקט ייסגר עוד מספר שניות...", ephemeral=True)
        await interaction.channel.delete(reason=f"Closed by {interaction.user}")

    @discord.ui.button(label="קח טיקט", style=discord.ButtonStyle.secondary, custom_id="claim_ticket", emoji="📜")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.can_manage(interaction.user):
            await interaction.response.send_message("❌ רק צוות ההנהלה או תפקיד התמיכה יכולים להשתמש בכפתור זה!", ephemeral=True)
            return
        
        button.disabled = True
        button.label = f"נלקח על ידי {interaction.user.display_name}"
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"✅ הטיקט נלקח על ידי {interaction.user.mention}", ephemeral=False)


class TicketSelect(discord.ui.Select):
    def __init__(self, options_data):
        discord_options = []
        for opt in options_data:
            if opt and opt.get("label"):
                discord_options.append(
                    discord.SelectOption(
                        label=opt["label"], 
                        description=opt.get("description")[:100] if opt.get("description") else None,
                        emoji=opt.get("safe_emoji") # משתמש באימוג'י הבטוח שכבר נבדק
                    )
                )
        super().__init__(placeholder="בחר אפשרות לפתיחת טיקט...", min_values=1, max_values=1, options=discord_options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = interaction.channel.category
        selected_option = self.values[0]
        
        support_role_id = support_roles.get(guild.id)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        if support_role_id:
            support_role = guild.get_role(support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        welcome_message = (
            f"**__ {interaction.user.name} יצר טיקט חדש על {selected_option}. __**\n\n"
            f"שלום {interaction.user.mention} ברוך הבא לטיקט שלך!\n"
            f"עוד מעט צוות השרת יענה לך!"
        )
        
        await ticket_channel.send(welcome_message, view=TicketControlView(guild.id))
        await interaction.followup.send(f"✅ הטיקט שלך נוצר בהצלחה כאן: {ticket_channel.mention}", ephemeral=True)


class TicketSelectView(discord.ui.View):
    def __init__(self, options_data):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(options_data))


class TicketButtonView(discord.ui.View):
    def __init__(self, button_name, button_emoji, title_topic):
        super().__init__(timeout=None)
        self.title_topic = title_topic
        
        safe_emoji = button_emoji if button_emoji and len(button_emoji.strip()) <= 8 else "👑"

        btn = discord.ui.Button(label=button_name, style=discord.ButtonStyle.success, emoji=safe_emoji, custom_id="open_ticket_btn")
        btn.callback = self.button_callback
        self.add_item(btn)

    async def button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = interaction.channel.category
        support_role_id = support_roles.get(guild.id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        if support_role_id:
            support_role = guild.get_role(support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        welcome_message = (
            f"**__ {interaction.user.name} יצר טיקט חדש על {self.title_topic}. __**\n\n"
            f"שלום {interaction.user.mention} ברוך הבא לטיקט שלך!\n"
            f"עוד מעט צוות השרת יענה לך!"
        )

        await ticket_channel.send(welcome_message, view=TicketControlView(guild.id))
        await interaction.followup.send(f"✅ הטיקט שלך נוצר בהצלחה כאן: {ticket_channel.mention}", ephemeral=True)


@bot.event
async def on_ready():
    print(f"הבוט התחבר בהצלחה בתור: {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"סונכרנו {len(synced)} פקודות Slash.")
    except Exception as e:
        print(e)


@bot.tree.command(name="set-support-role", description="הגדרת תפקיד תמיכה שיוכל לראות, לסגור ולקחת טיקטים")
@app_commands.check(is_admin)
@app_commands.describe(role="בחר את תפקיד התמיכה בשרת")
async def set_support_role(interaction: discord.Interaction, role: discord.Role):
    support_roles[interaction.guild.id] = role.id
    await interaction.response.send_message(f"✅ תפקיד התמיכה הוגדר בהצלחה ל-{role.mention}!", ephemeral=True)


@bot.tree.command(name="ticket-menu", description="יצירת פאנל טיקטים עם תפריט בחירה ואימוג'ים")
@app_commands.check(is_admin)
@app_commands.describe(
    title="כותרת ההודעה",
    description="תיאור ההודעה",
    footer="טקסט למטה",
    color="צבע ההודעה",
    opt1_name="שם אפשרות 1", opt1_desc="תיאור 1", opt1_emoji="אימוג'י 1 (למשל 🎫)",
    opt2_name="שם אפשרות 2", opt2_desc="תיאור 2", opt2_emoji="אימוג'י 2",
    opt3_name="שם אפשרות 3", opt3_desc="תיאור 3", opt3_emoji="אימוג'י 3",
    opt4_name="שם אפשרות 4", opt4_desc="תיאור 4", opt4_emoji="אימוג'י 4",
    opt5_name="שם אפשרות 5", opt5_desc="תיאור 5", opt5_emoji="אימוג'י 5",
)
async def ticket_menu(
    interaction: discord.Interaction,
    title: str,
    description: str,
    footer: str,
    color: str = None,
    opt1_name: str = None, opt1_desc: str = None, opt1_emoji: str = None,
    opt2_name: str = None, opt2_desc: str = None, opt2_emoji: str = None,
    opt3_name: str = None, opt3_desc: str = None, opt3_emoji: str = None,
    opt4_name: str = None, opt4_desc: str = None, opt4_emoji: str = None,
    opt5_name: str = None, opt5_desc: str = None, opt5_emoji: str = None,
):
    if not opt1_name:
        await interaction.response.send_message("❌ חובה למלא לפחות את אפשרות מספר 1!", ephemeral=True)
        return

    raw_options = [
        {"name": "אפשרות 1", "label": opt1_name, "desc": opt1_desc, "emoji": opt1_emoji},
        {"name": "אפשרות 2", "label": opt2_name, "desc": opt2_desc, "emoji": opt2_emoji},
        {"name": "אפשרות 3", "label": opt3_name, "desc": opt3_desc, "emoji": opt3_emoji},
        {"name": "אפשרות 4", "label": opt4_name, "desc": opt4_desc, "emoji": opt4_emoji},
        {"name": "אפשרות 5", "label": opt5_name, "desc": opt5_desc, "emoji": opt5_emoji},
    ]
    
    processed_options = []
    for opt in raw_options:
        if opt["label"] is not None:
            emoji_val = opt["emoji"]
            safe_emoji = None
            
            if emoji_val:
                # בדיקה האם האימוג'י תקין (אורך הגיוני ולא ארוך מדי)
                if len(emoji_val.strip()) <= 8:
                    safe_emoji = emoji_val.strip()
                else:
                    # אם האימוג'י לא תקין, הבוט ישלח הודעה מיד למשתמש
                    await interaction.response.send_message(f"האימוג'ים [{emoji_val}] לא תקין!", ephemeral=True)
                    return

            processed_options.append({
                "label": opt["label"],
                "description": opt["desc"],
                "safe_emoji": safe_emoji
            })

    data = {
        "type": "menu",
        "title": title,
        "description": description,
        "footer": footer,
        "color": color,
        "options": processed_options
    }

    encoded_data = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
    
    await interaction.response.send_message(
        f"✅ פקודת הטיקט שלך מוכנה! העתק ושלח את הפקודה הבאה בערוץ שתרצה:\n`!tickets {encoded_data}`",
        ephemeral=True
    )


@bot.tree.command(name="ticket-button", description="יצירת פאנל טיקטים עם כפתור")
@app_commands.check(is_admin)
@app_commands.describe(
    title="כותרת ההודעה",
    description="תיאור ההודעה",
    footer="טקסט למטה",
    button_name="שם הכפתור",
    color="צבע ההודעה",
    button_emoji="אימוג'י לכפתור (אופציונלי)"
)
async def ticket_button(
    interaction: discord.Interaction,
    title: str,
    description: str,
    footer: str,
    button_name: str,
    color: str = None,
    button_emoji: str = None
):
    if button_emoji:
        if len(button_emoji.strip()) > 8:
            await interaction.response.send_message(f"האימוג'ים [{button_emoji}] לא תקין!", ephemeral=True)
            return

    data = {
        "type": "button",
        "title": title,
        "description": description,
        "footer": footer,
        "color": color,
        "button_name": button_name,
        "button_emoji": button_emoji
    }

    encoded_data = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
    
    await interaction.response.send_message(
        f"✅ פקודת הטיקט שלך מוכנה! העתק ושלח את הפקודה הבאה בערוץ שתרצה:\n`!tickets {encoded_data}`",
        ephemeral=True
    )


@bot.command(name="tickets")
async def send_tickets_panel(ctx, encoded_data: str = None):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ רק מנהלים יכולים להשתמש בפקודה זו.")
        return

    if not encoded_data:
        await ctx.send("❌ יש לספק את הקוד המוצפן שקיבלת מהבוט.")
        return

    try:
        decoded_bytes = base64.b64decode(encoded_data.encode('utf-8'))
        data = json.loads(decoded_bytes.decode('utf-8'))
    except Exception:
        await ctx.send("❌ קוד לא תקין.")
        return

    embed_color = parse_color(data.get("color"))
    embed = discord.Embed(title=data["title"], description=data["description"], color=embed_color)
    embed.set_footer(text=data["footer"])

    if data["type"] == "menu":
        view = TicketSelectView(data["options"])
        await ctx.send(embed=embed, view=view)
    elif data["type"] == "button":
        view = TicketButtonView(data["button_name"], data.get("button_emoji"), data["title"])
        await ctx.send(embed=embed, view=view)
    
    try:
        await ctx.message.delete()
    except:
        pass

bot.runimport os
bot.run(os.environ.get("DISCORD_TOKEN")
