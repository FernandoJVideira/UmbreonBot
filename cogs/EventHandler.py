import os
import random
import discord
import requests
from twitchAPI.twitch import Twitch
from discord.ext import commands, tasks
import sqlite3

database = sqlite3.connect("bot.db")
cursor = database.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS levels (level INT, xp INT, user INT, guild INT)")
cursor.execute("CREATE TABLE IF NOT EXISTS roles (level INT, role_name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS twitch (twitch_user TEXT, guild_id INT)")
cursor.execute("INSERT INTO roles VALUES (?,?)", (5, "Level 5"))
cursor.execute("INSERT INTO roles VALUES (?,?)", (10, "Level 10"))
cursor.execute("INSERT INTO roles VALUES (?,?)", (20, "Level 20"))
cursor.execute("INSERT INTO roles VALUES (?,?)", (30, "Level 30"))
database.commit()


#* Authentication with Twitch API. 
client_id = os.getenv("TWITCH_CLIENT_ID")
client_secret = os.getenv("TWITCH_CLIENT_SECRET")
twitch = Twitch(client_id, client_secret)
TWITCH_STREAM_API_ENDPOINT = "https://api.twitch.tv/helix/streams?user_id={}"
API_HEADERS = {
    'Authorization': 'Bearer ' + os.getenv("TWITCH_AUTH_TOKEN"),
    'Client-ID': client_id,
}

class eventHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Ready for action!")
        await twitch.authenticate_app([])
        self.live_notifs_loop.start()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        guildchannelID = cursor.execute("SELECT welcome_channel_id FROM welcome WHERE guild_id = ?", (guild.id,)).fetchone()
        guildchannel = guild.get_channel(guildchannelID[0])

        dmchannel = await member.create_dm()
        await dmchannel.send(f"Welcome to **{guild.name}**! Have fun!")

        if guildchannel is not None:
            # Welcome Embed
            MyEmbed = discord.Embed(
                title="👋 Welcomeee!", description=f"{member.mention}! Welcome to the Shit Showww!", color=discord.Colour.orange())
            MyEmbed.set_author(
                name=f"{member.name} #{member.discriminator}", icon_url=member.display_avatar.url)
            MyEmbed.set_thumbnail(url=member.display_avatar.url)
            MyEmbed.set_image(
                url="https://media.giphy.com/media/61XS37iBats8J3QLwF/giphy.gif")
            MyEmbed.set_footer(text=f"ID: {member.id}")

            await guildchannel.send(member.mention, embed=MyEmbed)

    @commands.Cog.listener()
    async def on_message(self, message):
        
        if message.author.bot:
            return
        author = message.author
        guild = message.guild

        levelupChannelID = cursor.execute("SELECT levelup_channel_id FROM levelup WHERE guild_id = ?", (guild.id,)).fetchone()
        
        if levelupChannelID is not None:
            levelupChannel = guild.get_channel(levelupChannelID[0])
        
        xp = cursor.execute("SELECT xp FROM levels WHERE user = ? AND guild = ?", (author.id, guild.id)).fetchone()
        level = cursor.execute("SELECT level FROM levels WHERE user = ? AND guild = ?", (author.id, guild.id)).fetchone()

        if not xp or not level:
            cursor.execute("INSERT INTO levels (level, xp, user, guild) VALUES (?,?,?,?)", (0,0,author.id, guild.id))
            database.commit()
        try:
            xp = xp[0]
            level = level[0]
        except TypeError:
            xp = 0
            level = 0

        if level < 5:
            xp += random.randint(1, 3)
            cursor.execute("UPDATE levels SET xp = ? WHERE user = ? AND guild = ?", (xp, author.id, guild.id))
            database.commit()
        else:
            rand = random.randint(1, (level//4))
            if rand == 1:
                xp += random.randint(1, 3)
                cursor.execute("UPDATE levels SET xp = ? WHERE user = ? AND guild = ?", (xp, author.id, guild.id))
                database.commit()
        if xp >= 100:
            level += 1
            cursor.execute("UPDATE levels SET level = ? WHERE user = ? AND guild = ?", (level, author.id, guild.id))
            cursor.execute("UPDATE levels SET xp = ? WHERE user = ? AND guild = ?", (0, author.id, guild.id))
            database.commit()

            if level == 5 or level == 10 or level == 20 or level == 30:
                await setLevelRole(guild, author, level)

            if levelupChannelID is not None:
                await levelupChannel.send(f"{author.mention} has leveled up to level **{level}**!")
            else:
                await message.channel.send(f"{author.mention} has leveled up to level **{level}**!")
        await self.bot.process_commands(message)


    @tasks.loop(seconds=30)
    async def live_notifs_loop(self):
        guilds = cursor.execute("SELECT guild_id FROM twitch").fetchall()
        if guilds is not None:
            for guild_id in guilds:
                # Gets the guild, 'twitch streams' channel
                channel = cursor.execute("SELECT twitch_channel_id FROM twitch_config WHERE guild_id = ?", (guild_id[0],)).fetchone()
                channel = self.bot.get_channel(channel[0])

                twitch_users = cursor.execute("SELECT twitch_user FROM twitch WHERE guild_id = ?", (guild_id[0],)).fetchall()

                for twitch_user in twitch_users:
                    status = await checkuser(twitch_user[0])
                    print(status)
                    if status is True:
                        async for message in channel.history(limit=200):
                            sent_notification = False
                            if str(twitch_user[0]) in message.content and "is now streaming" in message.content:
                                print(f"{twitch_user} is already streaming. Not sending a notification.")
                                sent_notification = True
                                break
                        if not sent_notification:
                            await channel.send(
                                f":red_circle: **LIVE**\n @everyone is now streaming on Twitch!"
                                f"\nhttps://www.twitch.tv/{twitch_user[0]}")
                            print(f"{twitch_user} started streaming. Sending a notification.")                    

async def setup(bot):
    await bot.add_cog(eventHandler(bot))

async def setLevelRole(guild, author, level):
        role_name = cursor.execute("SELECT role_name FROM roles WHERE level = ?", (level,)).fetchone()
        if role_name is not None:
            if discord.utils.get(guild.roles,name=role_name[0]) is None:
                roles = cursor.execute("SELECT role_name FROM roles",).fetchall()
                for role in roles:
                    if discord.utils.get(guild.roles,name=role[0]) is None:
                        await guild.create_role(name=role[0], mentionable=False)
                role = discord.utils.get(guild.roles,name=role_name[0])
            else:
                role = discord.utils.get(guild.roles,name=role_name[0])
            
            if role is not None:
                if any(role.name == "Level 5" for role in author.roles):
                    await author.remove_roles(discord.utils.get(guild.roles,name="Level 5"))
                if any(role.name == f"Level {level-10}" for role in author.roles):
                    await author.remove_roles(discord.utils.get(guild.roles,name=f"Level {level-10}"))

                await author.add_roles(role)
                return

#*Returns true if online, false if not.
async def checkuser(user):
    try:
        twitch_user_generator = twitch.get_users(logins=[user])
        twitch_user = await twitch_user_generator.__anext__()
        userid = twitch_user.id
        url = TWITCH_STREAM_API_ENDPOINT.format(userid)
        try:
            req = requests.Session().get(url, headers= API_HEADERS)
            print(url)
            jsondata = req.json()
            if jsondata['data'][0]['type'] == "live":
                return True
            else:
                return False
        except Exception as e:
            print("Error checking user: ", e)
            return False
    except StopAsyncIteration:
        return False