import os
import discord
import requests
from discord.ext import commands

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
BASE_URL = 'https://memes-9qcu.onrender.com'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} ha iniciado sesión en Discord!')

@bot.command()
async def bg(ctx, profile_url: str, badge: str):
    valid_badges = ['staff', 'suscriptor', 'vip']
    
    if badge not in valid_badges:
        await ctx.send(f'Insignia no válida. Insignias válidas: {", ".join(valid_badges)}')
        return

    try:
        # Extraer el user_id de la URL
        user_id = profile_url.split('/')[-1]

        # Hacer una solicitud POST al servidor Flask para otorgar la insignia
        response = requests.post(f'{BASE_URL}/give_badge', json={'user_id': user_id, 'badge_name': badge})

        if response.status_code == 200:
            await ctx.send(f'Insignia "{badge}" otorgada al usuario {user_id} exitosamente.')
        else:
            await ctx.send(f'Error al otorgar la insignia: {response.text}')
    except Exception as e:
        await ctx.send(f'Ocurrió un error: {str(e)}')

bot.run(TOKEN)
