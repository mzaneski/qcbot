import os
import asyncio
import datetime
import importlib
from types import ModuleType

import discord

from . import commands
from .bot import QuakeBot

class QuakeClient(discord.Client):
    """The client handles a few debug commands but otherwise
    passes async events (messages, reactions, etc.) from discord API
    down to the bots that do the actual work.

    self.bots (list)
        QuakeBot objects for each server the client is connected
        to. Each bot handles events that come from its own
        respective server.

    self.cmds (dict)
        commands from commands module that can be triggered
        through a discord message, the bots in self.bots reference
        this dict frequently.
    """

    @staticmethod
    def ImportCmds():
        """Reloads the commands module and naively
        any module within that starts with the word command
        """

        for attrib_name in dir(commands):
            if attrib_name.startswith('command'):
                attrib = getattr(commands, attrib_name)
                if type(attrib) is ModuleType:
                    importlib.reload(attrib)

        importlib.reload(commands)

    def __init__(self, token, creator_id):
        super().__init__(max_messages=150)
        self.token = token
        self.creator_id = creator_id

        self.meta_command_prefix = '.'
        self.meta_kill = 'kill'
        self.meta_reload = 'reload'
        self.meta_print = 'print'
        
        self.bots = []
        self.cmds = self._load_cmds()

    def _load_cmds(self):
        """Load every callable with the command decorator
        in commands module. Commands are loaded on init
        or can be hot-reloaded after calling ReloadCmds().

        returns: dict
        """

        cmds = {}
        for key, attrib in dict(commands.__dict__).items():
            if (callable(attrib)
                and not key.startswith(('_', 'command'))
                and attrib.__module__.startswith('qcbot.commands')):

                cmds[attrib.name] = attrib

        return cmds

    def _spawn(self, server):
        """Spawn a bot for a server. Each bot has their
        own configuration file, database, & directory
        in the cwd.

        args: discord.Server
        returns: QuakeBot
        """
        
        bot = QuakeBot(self, server, os.getcwd())
        self.bots.append(bot)

        return bot


    #--------------------------
    # discord.Client overrides
    #--------------------------

    def run(self):
        super().run(self.token)

    async def logout(self):
        for bot in self.bots:
            await bot.logout()

        super().logout()

    async def on_ready(self):
        cur_time = datetime.datetime.now().strftime("%H:%M %m-%d-%Y")
        print('Bot logged in successfully. ' + cur_time)
        print(self.user.name)
        print(self.user.id)

        for server in self.servers:
            bot = self._spawn(server)
            await bot.on_ready()

        await self.change_presence(game=discord.Game(name='Quake Champions'))
            
    async def on_server_join(self, server):
        self._spawn(server)

    async def on_server_remove(self, server):
        for bot in self.bots:
            if bot.server is server:
                killed = bot
                break

        self.bots.remove(killed)

    async def on_message(self, message):
        chk_meta_prefix = message.content[0] == self.meta_command_prefix
        chk_for_bot_creator = message.author.id == self.creator_id
        if chk_meta_prefix and chk_for_bot_creator:
            if message.content[1:].startswith(self.meta_kill):
                cur_time = datetime.datetime.now().strftime("%H:%M %m-%d-%Y")
                print('Logging out and closing...' + cur_time)
                await self.logout()
                await self.close()
            elif message.content[1:].startswith(self.meta_reload):
                QuakeClient.ImportCmds()
                self.cmds = self._load_cmds()
                for bot in self.bots:
                    bot.add_cmds_to_config()
            elif message.content[1:].startswith(self.meta_print):
                print(message.content)
        else:
            for bot in self.bots:
                if message.server.id == bot.server.id:
                    await bot.on_message(message)
                    break

    async def on_message_edit(self, before, after):
        for bot in self.bots:
            if before.server.id == bot.server.id:
                await bot.on_message_edit(before, after)
                break

    async def on_message_delete(self, message):
        for bot in self.bots:
            if message.server.id == bot.server.id:
                await bot.on_message_delete(message)
                break

    async def on_reaction_add(self, reaction, user):
        for bot in self.bots:
            if reaction.message.server.id == bot.server.id:
                await bot.on_reaction_add(reaction, user)
                break

    async def on_reaction_remove(self, reaction, user):
        pass
    
    async def on_reaction_clear(self, reaction, user):
        pass
    
    async def on_member_join(self, member):
        for bot in self.bots:
            if member.server.id == bot.server.id:
                await bot.on_member_join(member)
                break
    
    async def on_member_remove(self, member):
        for bot in self.bots:
            if member.server.id == bot.server.id:
                await bot.on_member_remove(member)
                break

    async def on_member_update(self, before, after):
        for bot in self.bots:
            if after.server.id == bot.server.id:
                await bot.on_member_update(after)
                break