import asyncio
import configparser
import discord
from discord.ext import tasks
import re
from datetime import datetime, timedelta, timezone
from itertools import chain
from more_itertools import chunked
from random import randint
import functools

MINUTES_IN_DAY = 24 * 60

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
    def __init__(self, guild_id, member_id):
        global db

        self.guild_id = str(guild_id)
        self.member_id = str(member_id)
        self.initialized_at = datetime.utcnow()
        self.score = 0
        self.slept_at = None
        self.gn_message_id = None

    def read(self):
        doc = self.ref().get()
        if not doc.exists:
            raise PlayerNotFoundError(self)

        self.__dict__.update(doc.to_dict())

    def reset(self):
        self.__init__(self.guild_id, self.member_id)
        self.ref().set(self.__dict__)

    def ref(self):
        return db.collection('players').document(f'{self.guild_id}:{self.member_id}')

    def sleep(self, message):
        self.ref().update({ 'slept_at': datetime.now(timezone.utc), 'gn_message_id': message.id })

    def change_score(self, value):
        self.score += value
        self.ref().update({ 'score': firestore.Increment(value) })

class Guild(object):
    def __init__(self, id):
        global db

        self.id = str(id)
        self.celebrate_at = None
        self.channel_id = None
        self.cheater_emoji = None
        self.display_score = False
        self.guild_emoji = None

    def read(self):
        doc = self.ref().get()
        if not doc.exists:
            raise GuildNotFoundError(self)

        self.read_from(doc)

    def read_from(self, doc):
        self.__dict__.update(doc.to_dict())

    def schedule_celebration(self):
        offset = MINUTES_IN_DAY + randint(0, MINUTES_IN_DAY - 1)
        self.celebrate_at = self.celebrate_at.replace(hour=0, minute=0, second=0) + timedelta(minutes=offset)
        self.ref().update({ 'celebrate_at': self.celebrate_at })

    def ref(self):
        return db.collection('guilds').document(self.id)

def leaderboard_purge(guild_id):
    global db

    expiration_threshold = datetime.utcnow() - timedelta(days = 1)
    base_query = db.collection('players').where('guild_id', '==', str(guild_id))
    query_stream = chain(
        base_query.where('slept_at', '==', None).where('initialized_at', '<', expiration_threshold).stream(),
        base_query.where('slept_at', '<', expiration_threshold).stream(),
    )

    for chunk in chunked(query_stream, 500):
        batch = db.batch()
        for doc in chunk:
            batch.delete(doc.reference)
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

@tasks.loop(minutes=1)
async def celebrate():
    global db

    query_ref = db.collection('guilds').where('celebrate_at', '<', datetime.utcnow())

    for doc in query_ref.stream():
        config = Guild(doc.id)
        config.read_from(doc)

        guild = discord.utils.get(client.guilds, id=int(config.id))
        if not guild:
            continue

        channel = discord.utils.get(guild.text_channels, id=int(config.channel_id))
        role = discord.utils.get(guild.roles, id=int(config.role_id))
        if not channel or not role or not role.members:
            continue

        winner = role.members[0]
        await channel.send(f'Congrats <@{winner.id}> {config.role_emoji} <@&{config.role_id}>!')

        config.schedule_celebration()

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
        config.read()

        if config.channel_id and message.channel.id != int(config.channel_id):
            return

        reaction_emojis = {
            'gm': config.gm_emoji,
            'gn': config.gn_emoji,
        }

        for word, emoji in reaction_emojis.items():
            if greetings.get(word, False):
                reactions.append(message.add_reaction(emoji))

        if config.guild_emoji:
            reactions.append(message.add_reaction(config.guild_emoji))

        member_id = message.author.id

        player = Player(guild.id, member_id)

        if greetings.get('gm', False):
            try:
                player.read()
                if player.slept_at and player.slept_at > datetime.now(timezone.utc) - timedelta(hours = 1) and config.cheater_emoji:
                    reactions.append(message.add_reaction(config.cheater_emoji))
            except PlayerNotFoundError:
                pass
            player.reset()

        if greetings.get('gn', False):
            leaderboard_purge(guild.id)

            try:
                player.read()
                if player.slept_at:
                    if player.slept_at > datetime.now(timezone.utc) - timedelta(hours = 1) and config.cheater_emoji:
                        reactions.append(message.add_reaction(config.cheater_emoji))
                else:
                    max_score = leaderboard_max_score(guild.id)
                    if player.score == max_score:
                        reactions.append(message.add_reaction(config.role_emoji))

                        role = guild.get_role(int(config.role_id))
                        for user in role.members:
                            reactions.append(user.remove_roles(role))

                        reactions.append(message.author.add_roles(role))

                    if config.display_score:
                        reactions.append(message.channel.send(f'<@{member_id}> Your score is {player.score}. See you tomorrow! 👋'))

                    player.sleep(message)
            except PlayerNotFoundError:
                pass
    except GuildNotFoundError as err:
        print(err)

    await asyncio.gather(*reactions)

async def check_reaction(reaction, user):
    message = reaction.message

    if user.id == client.user.id:
        return

    if message.created_at < datetime.utcnow() - timedelta(hours = 1):
        return

    async for other_user in reaction.users():
        if other_user.id == client.user.id:
            break
    else:
        return

    if message.author.id == user.id:
        try:
            config = Guild(message.guild.id)
            config.read()
            if config.cheater_emoji:
                await message.add_reaction(config.cheater_emoji)
        except GuildNotFoundError as err:
            print(err)
        return

    player = Player(message.guild.id, user.id)
    try:
        player.read()
    except PlayerNotFoundError:
        return

    if player.slept_at:
        try:
            if player.gn_message_id:
                gn_message = await message.channel.fetch_message(player.gn_message_id)

                config = Guild(message.guild.id)
                config.read()
                if config.cheater_emoji:
                    await gn_message.add_reaction(config.cheater_emoji)
        except discord.HTTPException:
            pass
        except GuildNotFoundError as err:
            print(err)
        return

    return player

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
    permissions = discord.Permissions(manage_roles=True, read_message_history=True, send_messages=True, add_reactions=True)
    celebrate.start()
    print(f'Add bot to server: https://discordapp.com/oauth2/authorize/?permissions={permissions.value}&scope=bot&client_id={client.user.id}')

client.run(config.get('bot', 'token'))
