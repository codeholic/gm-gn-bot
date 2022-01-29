import asyncio
import configparser
import discord
import re
from datetime import datetime, timedelta, timezone

config = configparser.ConfigParser()
with open('bot.ini', 'r') as file:
    config.read_file(file)

channel_id = int(config.get('bot', 'channel_id'))
reaction_emojis = dict([word, config.get('bot', word)] for word in ['gm', 'gn'])
ocean_emoji = config.get('bot', 'ocean')

class Player(object):
    def __init__(self, id):
        self.id = id
        self.initialized_at = datetime.now(tz = timezone.utc)
        self.score = 0
        self.sleeping = False

leaderboard = {}

def leaderboard_purge():
    global leaderboard

    for player_id in list(leaderboard.keys()):
        player = leaderboard.get(player_id, None)
        if player and player.initialized_at + timedelta(days = 1) < datetime.now(tz = timezone.utc):
            leaderboard.pop(player_id, None)

def message_includes(message, word):
    return re.search(rf'\b{word}\b', message.content, flags=re.IGNORECASE)

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents = intents)

@client.event
async def on_message(message):
    global channel_id, config, leaderboard, ocean_emoji, reaction_emojis

    if message.channel.id != channel_id:
        return

    reactions = []

    for word, emoji in reaction_emojis.items():
        if message_includes(message, word):
            reactions.append(message.add_reaction(emoji))

    if len(reactions) > 0:
        reactions.append(message.add_reaction(ocean_emoji))

    leaderboard_purge()

    player_id = message.author.id

    if message_includes(message, 'gm'):
        leaderboard[player_id] = Player(player_id)

    if message_includes(message, 'gn'):
        player = leaderboard.get(player_id, None)
        if player:
            max_score = max(player.score for player in leaderboard.values())
            if player.score == max_score:
                reactions.append(message.add_reaction(config.get('bot', 'crown')))
            player.sleeping = True

    await asyncio.gather(*reactions)

async def check_reaction(reaction, user):
    global channel_id, leaderboard

    message = reaction.message

    if user.id == client.user.id:
        return

    if message.channel.id != channel_id:
        return

    player = leaderboard.get(user.id, None)
    if not player or player.sleeping or message.created_at.astimezone(timezone.utc) < player.initialized_at:
       return

    async for other_user in reaction.users():
        if other_user.id == client.user.id:
            break
    else:
        return

    return player

@client.event
async def on_reaction_add(reaction, user):
    player = await check_reaction(reaction, user)
    if not player:
        return

    player.score += 1
    print(f'id: {player.id} score: {player.score}')

@client.event
async def on_reaction_remove(reaction, user):
    player = await check_reaction(reaction, user)
    if not player:
        return

    player.score -= 1
    print(f'<id: {player.id} score: {player.score}')

@client.event
async def on_ready():
    permissions = discord.Permissions(manage_roles = True, read_message_history = True, add_reactions = True)
    print(f'Add bot to server: https://discordapp.com/oauth2/authorize/?permissions={permissions.value}&scope=bot&client_id={client.user.id}')

client.run(config.get('bot', 'token'))
