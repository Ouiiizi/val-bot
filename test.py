from dotenv import load_dotenv
import os

load_dotenv()  # This must be called before you try to get the token

token = os.getenv("DISCORD_BOT_TOKEN")
print("token:", token)