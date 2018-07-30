import os
import asyncio
import json

import discord

from .database import QCDB
from .match import Match
from .pug import Pug
from .conf import Config
from .exceptions import MatchError

class QuakeBot:
    """Holds objects and data and handles events detected
    by the client for the server it belongs to.

    self.conf (qcbot.conf.Config)
        settings object that holds server-specific settings
        for the bot like command prefix and PUG configuration

    self.pug (qcbot.pug.Pug)
        does the heavy lifting for PUG lobby operations and
        database interactions (e.g. players joining/leaving
        lobbies, reporting match wins, etc.)

    self.db (qcbot.database.QCDB)
        has API functions to interact with the sqlite3
        database that holds PUG tables like players, matches, etc.

    self.shortcuts (dict, key: str, val: discord.Emoji or str)
        holds reactions that serve as shortcuts for typed commands.
        since discord reactions can be unicode strings or
        discord.Emoji objects, this dict can hold either types
        because a call to add_reaction() accepts both

    to-do:
        add status checking so a broken bot will correctly report
        its broken state (like if the pug channel gets deleted)
        and shut down
    """

    def __init__(self, client, server, path):
        self.client = client
        self.server = server
        self.server_directory = path + '/s_{}'.format(server.id)

        # load config settings
        settings = Config.SERIALIZED_DEFAULTS.copy()
        settings_path = self.server_directory + '/settings.json'
        try:
            if not os.path.exists(self.server_directory):
                os.makedirs(self.server_directory)

            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except IOError:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        except Exception as e:
            print('Error loading settings {}'.format(e.args))
            raise

        self.conf = Config(settings)
        self.add_cmds_to_config()

        # load the player/match database
        self.db = QCDB(self.server_directory + '/{}.db'.format(server.id))
        self.db.setup(path + '/db/qcbot.sql')

        # create pug functionality
        self.pug = Pug(self.conf.generate_maplist())

        # load the shortcuts
        self.shortcuts = {}
        for conf_emoji in self.conf.emojis:
            for server_emoji in server.emojis:
                if self.conf.emojis[conf_emoji] == server_emoji.id:
                    self.shortcuts[conf_emoji] = server_emoji
                    break
            else:
                self.shortcuts[conf_emoji] = self.conf.emojis[conf_emoji]

    def add_cmds_to_config(self):
        """Adds every currently loaded command in the client
        to the config file for the bot. This is for saving attributes
        like a whitelist for each command when they are created/loaded.
        """

        for cmd in self.client.cmds:
            if not cmd in self.conf.whitelist:
                self.conf.whitelist[cmd] = []
        else:
            self.dump_config()        

    def dump_config(self):
        conf_dir = self.server_directory + '/settings.json'
        with open(conf_dir, 'w', encoding='utf-8') as f:
            json.dump(self.conf.serial(), f)

    async def broadcast(self, priority, content):
        if priority <= self.conf.verbosity:
            if self.conf.brd_chan:
                await self.client.send_message(self.conf.brd_chan, content)


    #---------------------------------------
    # discord events passed from the client
    #---------------------------------------

    async def logout(self):
        self.dump_config()

    async def on_ready(self):
        await self.client.purge_from(self.conf.pug_chan)
        await self.pug.on_ready(self)

    async def on_message(self, message):
        if message.content.startswith(self.conf.prefix):
            content = message.content.split(' ')
            if content[0][1:] in self.client.cmds:
                await self.client.cmds[content[0][1:]](self, message, split_text=content)

        #automatically delete any message sent in the pug channel
        #that isn't from the bot or doesn't start with #
        chk1 = message.channel.id == self.conf.pug_chan.id
        chk2 = message.author is not self.server.me
        chk3 = not message.content.startswith('#')
        if chk1 and (chk2 or chk3):
            await asyncio.sleep(0.5)
            await self.client.delete_message(message)

    async def on_message_edit(self, before, after):
        pass

    async def on_message_delete(self, message):
        pass

    async def on_reaction_add(self, reaction, user):
        chk1 = reaction.message.channel.id == self.conf.pug_chan.id
        chk2 = user is not reaction.message.server.me
        if chk1 and chk2:
            for m_id, match in self.pug.m_cache.items():
                if match['message'].id == reaction.message.id:
                    try:
                        await self._handle_reaction(reaction, user, m_id, match)
                    except MatchError:
                        pass
                    finally:
                        break
            try:
                await self.client.remove_reaction(reaction.message, reaction.emoji, user)
            except discord.errors.NotFound:
                pass

    async def on_reaction_remove(self, reaction, user):
        pass
    
    async def on_reaction_clear(self, reaction, user):
        pass

    async def on_member_join(self, member):
        pass

    async def on_member_remove(self, member):
        pass

    async def on_member_update(self, after):
        if after.status.value in ('idle', 'offline'):
            for m_id, match in self.pug.m_cache.items():
                if after.id in match['players']:
                    if self.conf.auto_kick and match['status'] == Match.LOBBY:
                        reason = 'Went offline.' if after.status.value == 'offline' else 'Went AFK.'
                        try:
                            await self.pug._kick_player(self, self.server.me.id,
                                                        m_id, match,
                                                        match['players'].index(after.id),
                                                        reason=reason)
                        except MatchError:
                            pass
                    else:
                        await self.pug.unready(self, after.id, after.display_name, m_id, match)
                    break

    #---------------------------------------
    #---------------------------------------

    async def _handle_reaction(self, reaction, user, match_id, match):
        status = match['status']

        if reaction.emoji == self.shortcuts['join_blue'] and status == Match.LOBBY:
            await self.pug.join_match_direct(self, user.id, user.display_name, match_id, team='team1')
        elif reaction.emoji == self.shortcuts['join_red'] and status == Match.LOBBY:    
            await self.pug.join_match_direct(self, user.id, user.display_name, match_id, team='team2')
        elif reaction.emoji == self.shortcuts['end_blue'] and status == Match.LIVE:
            await self.pug.end_match_direct(self, user.id, match_id, 'team1')
        elif reaction.emoji == self.shortcuts['end_red'] and status == Match.LIVE:
            await self.pug.end_match_direct(self, user.id, match_id, 'team2')
        elif reaction.emoji == self.shortcuts['ready'] and status == Match.LOBBY:
            if match['host'] == user.id:
                await self.pug.start_match_direct(self, user.id, match_id)
            else:
                await self.pug.ready_direct(self, user.id, user.display_name, match_id, user.status.value)
        elif reaction.emoji == self.shortcuts['cancel'] and status == Match.LIVE:
            await self.pug.cancel_match_direct(self, user.id, match_id)
        elif reaction.emoji == self.shortcuts['leave'] and status < Match.W_TOP:
            await self.pug.leave_match_direct(self, user.id, user.display_name, match_id)