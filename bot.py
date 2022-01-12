import asyncio
import configparser
import discord
import re

config = configparser.ConfigParser()
with open('bot.ini', 'r') as file:
    config.read_file(file)

client = discord.Client()

@client.event
async def on_message(message):
    if message.channel.id != int(config.get('bot', 'channel_id')):
        return

    gm = re.search(r'\bgm\b', message.content, flags=re.IGNORECASE)
    gn = re.search(r'\bgn\b', message.content, flags=re.IGNORECASE)

    reactions = []

    if gm:
        reactions.append(message.add_reaction(config.get('bot', 'gm')))

    if gn:
        reactions.append(message.add_reaction(config.get('bot', 'gn')))

    if gm or gn:
        reactions.append(message.add_reaction(config.get('bot', 'ocean')))

    await asyncio.gather(*reactions)

client.run(config.get('bot', 'token'))
