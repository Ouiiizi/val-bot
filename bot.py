import os
import json
import discord
import requests
import asyncio
import schedule
import time
from dotenv import load_dotenv
from discord.ext import commands, tasks

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
USERS_FILE = "users.json"

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Initialize bot
bot = commands.Bot(command_prefix="!", intents=intents)

def load_users():
    try:
        if not os.path.exists(USERS_FILE):
            return {}
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving users: {e}")


def authenticate(username, password, twofactor_code=None, session=None):
    try:
        if session is None:
            session = requests.Session()
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            'client_id': 'play-valorant-web-prod',
            'nonce': '1',
            'redirect_uri': 'https://playvalorant.com/opt_in',
            'response_type': 'token id_token',
            'scope': 'account openid',
        }
        session.post("https://auth.riotgames.com/api/v1/authorization", json=data, headers=headers)
        auth_data = {
            "type": "auth",
            "username": username,
            "password": password
        }
        auth_response = session.put("https://auth.riotgames.com/api/v1/authorization", json=auth_data, headers=headers).json()
        print("[DEBUG] Riot initial response:", auth_response)  # Debug print

        # Handle 2FA required
        if auth_response.get('type') == 'multifactor':
            if twofactor_code:
                mfa_data = {
                    "type": "multifactor",
                    "code": twofactor_code,
                    "rememberDevice": True
                }
                mfa_response = session.put("https://auth.riotgames.com/api/v1/authorization", json=mfa_data, headers=headers).json()
                print("[DEBUG] Riot 2FA response:", mfa_response)  # Debug print
                if mfa_response.get('type') == 'response' and "response" in mfa_response:
                    access_token = mfa_response['response']['parameters']['uri'].split('access_token=')[1].split('&')[0]
                    return access_token
                elif mfa_response.get('error') == 'multifactor_attempt_failed':
                    return {'error': 'Invalid 2FA code'}
                else:
                    return {'error': 'Unknown 2FA error', 'details': mfa_response}
            else:
                return {'2fa_required': True, 'session': session}

        # Handle bad credentials
        if auth_response.get('error') == 'auth_failure':
            return {'error': 'Invalid username or password'}

        # Handle successful login
        if auth_response.get('type') == 'response' and "response" in auth_response:
            access_token = auth_response['response']['parameters']['uri'].split('access_token=')[1].split('&')[0]
            return access_token

        # Unknown error
        return {'error': 'Unknown error', 'details': auth_response}
    except Exception as e:
        print(f"Authentication error: {e}")
        return {'error': str(e)}

def get_store_data(token):
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Riot-Entitlements-JWT': token,
        }
        userinfo = requests.get("https://auth.riotgames.com/userinfo", headers=headers).json()
        puuid = userinfo["sub"]

        store_resp = requests.get(
            f"https://pd.na.a.pvp.net/store/v2/storefront/{puuid}",
            headers=headers
        ).json()
        return store_resp.get("SkinsPanelLayout", {}).get("SingleItemOffers", [])
    except Exception as e:
        print(f"Error getting store data: {e}")
        return []

def get_skin_info(skin_ids):
    try:
        response = requests.get("https://valorant-api.com/v1/weapons/skinlevels").json()
        skins_info = response["data"]
        skin_lookup = {skin["uuid"]: skin for skin in skins_info}

        embeds = []
        for skin_id in skin_ids:
            skin = skin_lookup.get(skin_id)
            if skin:
                embed = discord.Embed(title=skin["displayName"], color=discord.Color.red())
                embed.set_image(url=skin["displayIcon"])
                embeds.append(embed)
        return embeds
    except Exception as e:
        print(f"Error getting skin info: {e}")
        return []

# ------------------- Commands -------------------
@bot.command(name="login")
async def login(ctx):
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.author.send("Please use this command in DM for privacy.")
        return

    login_url = f"http://localhost:5000/login?discord_id={ctx.author.id}"
    await ctx.send(f"To log in, please use this link: {login_url}\nAfter logging in, return here and use !shop.")

@bot.command(name="shop")
async def shop(ctx):
    user_id = str(ctx.author.id)
    users = load_users()
    if user_id not in users:
        return await ctx.send(" You haven't logged in yet. Use `/login` via DM.")

    await ctx.defer()
    creds = users[user_id]
    token = authenticate(creds["username"], creds["password"])
    if not token:
        return await ctx.send(" Login failed. Stored credentials might be wrong.")

    skins = get_store_data(token)
    embeds = get_skin_info(skins)

    if not embeds:
        await ctx.send(" No skins found in your shop.")
        return

    await ctx.send(f" Here's your Valorant shop, <@{ctx.author.id}>:")
    for embed in embeds:
        await ctx.send(embed=embed)

@tasks.loop(minutes=1)
async def check_schedule():
    schedule.run_pending()

def daily_shop_task():
    async def send_daily():
        users = load_users()
        for uid, creds in users.items():
            try:
                user = await bot.fetch_user(int(uid))
                token = authenticate(creds["username"], creds["password"])
                if not token:
                    await user.send(" Couldn't fetch your shop (login failed). Try `/login` again.")
                    continue
                skins = get_store_data(token)
                embeds = get_skin_info(skins)
                if embeds:
                    await user.send("🎯 Here's your daily Valorant shop:")
                    for embed in embeds:
                        await user.send(embed=embed)
            except Exception as e:
                print(f"Error sending to user {uid}: {e}")

    bot.loop.create_task(send_daily())

@bot.event
async def on_ready():
    print(f" Logged in as {bot.user}")
    print(f" Bot is in {len(bot.guilds)} servers")
    schedule.every().day.at("08:00").do(daily_shop_task)
    check_schedule.start()

def run_bot():
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")

if __name__ == "__main__":
    run_bot()
