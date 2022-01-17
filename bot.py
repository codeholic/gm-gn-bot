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

    reactions = []

    for word in ['gm', 'gn']:
        if re.search(rf'\b{word}\b', message.content, flags=re.IGNORECASE):
            reactions.append(message.add_reaction(config.get('bot', word)))

    if len(reactions) > 0:
        reactions.append(message.add_reaction(config.get('bot', 'ocean')))

    await asyncio.gather(*reactions)

client.run(config.get('bot', 'token'))
