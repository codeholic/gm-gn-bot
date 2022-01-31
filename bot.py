import asyncio
import configparser
import discord
import re
from datetime import datetime, timedelta
from more_itertools import chunked
import functools

config = configparser.ConfigParser()
with open('bot.ini', 'r') as file:
    config.read_file(file)

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

cred = credentials.Certificate('firebase.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

class Error(Exception):
    pass

class GuildNotFoundError(Error):
    def __init__(self, guild):
        self.message = f'Guild {guild.id} not found'
        super().__init__(self.message)

class PlayerNotFoundError(Error):
    def __init__(self, player):
        self.message = f'Player {player.guild_id} {player.member_id} not found'
        super().__init__(self.message)

class Player(object):
    def __init__(self, guild_id, member_id, initialize = False):
        global db

        self.guild_id = str(guild_id)
        self.member_id = str(member_id)
        self.initialized_at = datetime.utcnow()
        self.score = 0
        self.sleeping = False

        if initialize:
            self.ref().set(self.__dict__)
            return

        doc = self.ref().get()
        if not doc.exists:
            raise PlayerNotFoundError(self)

        self.__dict__.update(doc.to_dict())

    def ref(self):
        return db.collection('players').document(f'{self.guild_id}:{self.member_id}')

    def sleep(self):
        self.ref().update({ 'sleeping': True })

    def change_score(self, value):
        self.score += value
        self.ref().update({ 'score': firestore.Increment(value) })

class Guild(object):
    def __init__(self, id):
        global db

        self.id = str(id)
        self.channel_id = None

        doc = db.collection('guilds').document(self.id).get()
        if not doc.exists:
            raise GuildNotFoundError(self)

        self.__dict__.update(doc.to_dict())

def leaderboard_purge(guild_id):
    global db

    expiration_threshold = datetime.utcnow() - timedelta(days = 1)
    query_ref = db.collection('players').where('guild_id', '==', str(guild_id)).where('initialized_at', '<', expiration_threshold)

    for chunk in chunked(query_ref.stream(), 500):
        batch = db.batch()
        for doc in chunk:
            batch.delete(doc.ref)
        batch.commit()

def leaderboard_max_score(guild_id):
    global db

    query_ref = db.collection('players').where('guild_id', '==', str(guild_id)).order_by('score', direction=firestore.Query.DESCENDING).limit(1)

    try:
        doc = next(query_ref.stream())
        return doc.to_dict()['score']
    except StopIteration:
        return 0

def message_includes(message, word):
    return re.search(rf'\b{word}\b', message.content, flags=re.IGNORECASE)

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents = intents)

@client.event
async def on_message(message):
    greetings = {}
    for word in ['gm', 'gn']:
        if message_includes(message, word):
            greetings[word] = True

    if len(greetings) == 0:
        return

    reactions = []

    try:
        guild = message.guild
        config = Guild(guild.id)

        if config.channel_id and message.channel.id != int(config.channel_id):
            return

        reaction_emojis = {
            'gm': config.gm_emoji,
            'gn': config.gn_emoji,
        }

        for word, emoji in reaction_emojis.items():
            if greetings.get(word, False):
                reactions.append(message.add_reaction(emoji))

        reactions.append(message.add_reaction(config.guild_emoji))

        member_id = message.author.id

        if greetings.get('gm', False):
            Player(guild.id, member_id, initialize = True)

        if greetings.get('gn', False):
            leaderboard_purge(guild.id)

            player = Player(guild.id, member_id)

            max_score = leaderboard_max_score(guild.id)
            if player.score == max_score:
                reactions.append(message.add_reaction(config.role_emoji))

                role = guild.get_role(int(config.role_id))
                for user in role.members:
                    reactions.append(user.remove_roles(role))

                reactions.append(message.author.add_roles(role))

            player.sleep()
    except GuildNotFoundError as err:
        print(err)
    except PlayerNotFoundError:
        pass

    await asyncio.gather(*reactions)

async def check_reaction(reaction, user):
    message = reaction.message

    try:
        if user.id == client.user.id or message.author.id == user.id:
            return

        async for other_user in reaction.users():
            if other_user.id == client.user.id:
                break
        else:
            return

        player = Player(message.guild.id, user.id)
        expiration_threshold = datetime.utcnow() - timedelta(hours = 1)
        if player.sleeping or message.created_at < expiration_threshold:
           return

        return player
    except PlayerNotFoundError:
        pass

@client.event
async def on_reaction_add(reaction, user):
    player = await check_reaction(reaction, user)
    if not player:
        return

    player.change_score(1)
    print(f'guild_id: {player.guild_id} member_id: {player.member_id} score: {player.score}')

@client.event
async def on_reaction_remove(reaction, user):
    player = await check_reaction(reaction, user)
    if not player:
        return

    player.change_score(-1)
    print(f'guild_id: {player.guild_id} member_id: {player.member_id} score: {player.score}')

@client.event
async def on_ready():
    permissions = discord.Permissions(manage_roles = True, read_message_history = True, add_reactions = True)
    print(f'Add bot to server: https://discordapp.com/oauth2/authorize/?permissions={permissions.value}&scope=bot&client_id={client.user.id}')

client.run(config.get('bot', 'token'))
