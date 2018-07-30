import asyncio
import random

import discord

from .match import Match
from .exceptions import MatchError
from .database import QCDB

class Pug:
    """Mostly functions that control the flow and status of matches. Does
    most of the heavy lifting for the bot and communication with the database.

    Many of the operations have different possible entry points. Like when
    the user types !leave with no context and we have to find what match they're in
        1. the base function that does the work on the Match object (private)
        2. "*_search" function for example when a user types !leave with no
            context so we have to find what match they're in to remove them
        3. "*_direct" for when the match is known, like when the user uses
            a reaction shortcut on a lobby message which is directly tied
            to a match in the cache

    self.m_cache (dict, key: int, val: qcbot.match.Match)
        stores qcbot.match.Match objects which are cached representations
        of active matches in the database that act as a buffer between
        the database and output to discord.

    self.banned (dict, key: str, val: (int, str))
        dict of banned users containing a tuple which has the reason for
        and a length of the ban. these bans are temporary and are lost if
        the bot goes down. for permabanning the server admins should strip
        the target player of their PUG role.

    self.maplist (dict, key: str, val: list [str])
        contains appropriate gamemodes for each map in QC.

    todo:
        make bans stay after the bot goes down. right now the only way to
        permaban someone is by removing their PUG role
    """
    
    def __init__(self, maplist):
        self.m_cache = {}
        self.banned = {}
        self.maplist = maplist

    class _check:
        """Decorators for checking appropriate role,
        player bans, and player presence in the database
        before doing certain operations.
        """

        @classmethod
        def role(cls, func):
            async def deco(pug, bot, user_id, *args, **kwargs):
                if bot.conf.pug_role.id == bot.server.id:
                    await func(pug, bot, user_id, *args, **kwargs)
                else:
                    member = discord.utils.get(bot.server.members, id=user_id)
                    if member:
                        for role in member.roles:
                            if role.id == bot.conf.pug_role.id:
                                await func(pug, bot, user_id, *args, **kwargs)
                                break
            return deco

        @classmethod
        def ban(cls, func):
            async def deco(pug, bot, user_id, *args, **kwargs):
                if user_id in pug.banned:
                    fmt = (pug.banned[user_id][1], pug.banned[user_id][0])
                    errmsg = 'User is on cooldown. Reason: \"{}\" Duration: {} min'.format(*fmt)
                    raise MatchError(errmsg)
                    
                await func(pug, bot, user_id, *args, **kwargs)
            return deco

        @classmethod
        def dbentry(cls, func):
            async def deco(pug, bot, user_id, *args, **kwargs):
                if not bot.db.get_player_record(user_id):
                    bot.db.add_player(user_id, 'UNK')

                await func(pug, bot, user_id, *args, **kwargs)
            return deco

    def ban(self, loop, user_id, minutes, reason):
        if user_id not in self.banned:
            self.banned[user_id] = (minutes, reason)
            loop.create_task(self.unban(user_id, minutes))

    async def unban(self, user_id, minutes):
        await asyncio.sleep(minutes * 60)
        del self.banned[user_id]
        
    async def on_ready(self, bot):
        pug_help = (
            '#**REACTION SHORTCUTS**\n'
            '{1}  {0}join <lobby> blue\n'
            '{2}  {0}join <lobby> red\n'
            '{3}  {0}end blue    (if the pug is live)\n'
            '{4}  {0}end red      (if the pug is live)\n'
            '{5}  {0}ready OR {0}start (depending on if you are a player or the host)\n'
            '{6}  {0}cancel\n'
            '{7}  {0}leave (this will incur a loss if the pug is live)\n'
        ).format(bot.conf.prefix,
                bot.shortcuts['join_blue'],
                bot.shortcuts['join_red'],
                bot.shortcuts['end_blue'],
                bot.shortcuts['end_red'],
                bot.shortcuts['ready'],
                bot.shortcuts['cancel'],
                bot.shortcuts['leave'])

        await bot.client.send_message(bot.conf.pug_chan, pug_help)

        matches = bot.db.get_active_matches()
        for match in matches:
            await asyncio.sleep(1)

            players = bot.db.get_all_players_in_match(match[0])
            self.m_cache[match[0]] = Match(bot.conf, match[0], match[1],
                                           match[2], players=players, status=match[3])
            
            msg = await bot.client.send_message(bot.conf.pug_chan, str(self.m_cache[match[0]]))
            self.m_cache[match[0]]['message'] = msg

            if match[3] == Match.LOBBY:
                await asyncio.sleep(1)
                await bot.client.add_reaction(msg, bot.shortcuts['join_blue'])
                await asyncio.sleep(1)
                await bot.client.add_reaction(msg, bot.shortcuts['join_red'])
                await asyncio.sleep(1)
                await bot.client.add_reaction(msg, bot.shortcuts['ready'])
            elif match[3] == Match.LIVE:
                await asyncio.sleep(1)
                await bot.client.add_reaction(msg, bot.shortcuts['end_blue'])
                await asyncio.sleep(1)
                await bot.client.add_reaction(msg, bot.shortcuts['end_red'])
                await asyncio.sleep(1)
                await bot.client.add_reaction(msg, bot.shortcuts['cancel'])

            await asyncio.sleep(1)
            await bot.client.add_reaction(msg, bot.shortcuts['leave'])

    def __offset_slot(self, max_players_team, slot):
        """Helper for translating a match lobby slot (1-8) to
        the actual index of the player list. This is for commands like
        !kick and !swap

            Players see the playerlist in lobbies as:
            Team 1
                1. dude
                2.
            Team 2
                3. guy
                4. person

            But internally this is stored in a list as:
            [dude, None, None, None, guy, person, None, None]

            So "!kick 3" would be for 'guy' who is in slot 3 but actual index
            in the list is 4
        """

        #clamp slot number to min or max of the gamemode
        if slot < 0:
            ind = 0
        elif slot > (max_players_team * 2) - 1:
            ind = (max_players_team * 2) - 1
        else:
            ind = slot

        #if the slot is on team2, offset it to find the real position in playerlist
        if slot >= max_players_team:
            ind += QCDB.MAX_SLOTS - max_players_team

        #return real index in playerlist
        return ind


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~create
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    @_check.role
    @_check.ban
    @_check.dbentry
    async def create_match(self, bot, user_id, user_name, mode, note):
        for m_id in self.m_cache:
            if user_id in self.m_cache[m_id]['players']:
                raise MatchError('You cannot be in more than one lobby at a time.')

        #create match in database
        match_id = bot.db.create_match(user_id, mode)
        match = bot.db.get_match(match_id)
        players = bot.db.get_all_players_in_match(match_id)

        #add match to active matches cache
        self.m_cache[match_id] = Match(bot.conf, match_id, match[1], match[2],
                                       players=players, note=note)

        #send message to pug channel with new lobby
        msg = await bot.client.send_message(bot.conf.pug_chan, str(self.m_cache[match_id]))
        self.m_cache[match_id]['message'] = msg

        brd_fmt = (user_name, mode, match_id, bot.conf.pug_chan.id, bot.conf.prefix, match_id)
        brd_msg = '**{}** created **{}** lobby #{} in <#{}> `\"{}join {}\" to play.`'.format(*brd_fmt)
        await bot.broadcast(1, brd_msg)
        
        await asyncio.sleep(1)
        await bot.client.add_reaction(msg, bot.shortcuts['join_blue'])
        await asyncio.sleep(1)
        await bot.client.add_reaction(msg, bot.shortcuts['join_red'])
        await asyncio.sleep(1)
        await bot.client.add_reaction(msg, bot.shortcuts['ready'])
        await asyncio.sleep(1)
        await bot.client.add_reaction(msg, bot.shortcuts['leave'])


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~join
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _join_match(self, bot, user_id, user_name, match_id, match, team=''):
        team1_players = [ p for p in bot.db.get_players_on_team(match_id, 'team1') if p ]
        team2_players = [ p for p in bot.db.get_players_on_team(match_id, 'team2') if p ]
        team1_num_players = len(team1_players)
        team2_num_players = len(team2_players)
        num_players = team1_num_players + team2_num_players + 1
        max_players = bot.conf.modes[match['mode']] * 2

        #if no team was provided, join team with less players
        if not team:
            t = 'team2' if team1_num_players > team2_num_players else 'team1'
        else:
            t = team
                
        #add player to the match in database
        slot = bot.db.add_player_to_match(match_id, user_id, t, bot.conf.modes[match['mode']])
        if slot == -1:
            raise MatchError('That team or lobby is full.')

        #add player to the match in cache
        if t == 'team2':
            slot += QCDB.MAX_SLOTS
        match['players'][slot] = user_id

        if num_players == max_players:
            hint = ' `\"{}start\" to go live.`'.format(bot.conf.prefix)
        else:
            hint = ''
        
        brd_fmt = (user_name, match['mode'], match_id, num_players, max_players)
        brd_msg = '**{}** joined **{}** lobby #{} **[{}/{}]**'.format(*brd_fmt)
        await bot.broadcast(2, brd_msg + hint)

        await bot.client.edit_message(match['message'], str(match))

    @_check.role
    @_check.ban
    @_check.dbentry
    async def join_match_direct(self, bot, user_id, user_name, match_id, team=''):
        for m_id in self.m_cache:
            if m_id != match_id and user_id in self.m_cache[m_id]['players']:
                raise MatchError('You cannot be in more than one lobby at a time.')

        match = self.m_cache.get(match_id)
        if match:
            if match['status'] != Match.LOBBY:
                raise MatchError('That game has already started.')

            if user_id in match['players']:
                await self._swap_player_to_team(bot, match_id, match, match['players'].index(user_id), team)
            else:
                await self._join_match(bot, user_id, user_name, match_id, match, team)
        else:
            raise MatchError('Lobby not found.')


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~leave
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _leave_match(self, bot, user_id, user_name, match_id, match):
        #remove player from m_cache and database
        if user_id in match['ready']:
            match['ready'].remove(user_id)
        if user_id in match['mutinies']:
            match['mutinies'].remove(user_id)

        bot.db.remove_player_from_match(match_id, user_id)
        ind = match['players'].index(user_id)
        match['players'][ind] = None

        #if leaver is host: find new host or cancel if the lobby becomes empty
        if user_id == match['host']:
            for player in match['players']:
                if player:
                    match['host'] = player
                    if player in match['ready']:
                        match['ready'].remove(player)
                    bot.db.change_host(match_id, match['host'])
                    break
            else:
                await self._cancel_match(bot, match_id)
                return

        if match['status'] == Match.LIVE:
            self.ban(bot.client.loop, user_id, 5, 'Abandoned a live match.')
            bot.db.report_ruined_match(user_id)
        else:
            num_players = len([p for p in match['players'] if p])
            max_players = bot.conf.modes[match['mode']] * 2

            brd_fmt = (user_name, match['mode'], match_id, num_players, max_players)
            brd_msg = '**{}** left **{}** lobby #{} **[{}/{}]**'.format(*brd_fmt)
            await bot.broadcast(2, brd_msg)

        await bot.client.edit_message(match['message'], str(match))
        
    async def leave_match_direct(self, bot, user_id, user_name, match_id):
        match = self.m_cache.get(match_id)
        if match:
            if user_id in match['players']:
                await self._leave_match(bot, user_id, user_name, match_id, match)

    async def leave_match_search(self, bot, user_id, user_name):
        for m_id, match in self.m_cache.items():
            if user_id in match['players']:
                await self._leave_match(bot, user_id, user_name, m_id, match)
                break


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~cancel
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _cancel_match(self, bot, match_id):
        match = self.m_cache[match_id]

        bot.db.remove_match(match_id)
        del self.m_cache[match_id]

        await bot.broadcast(3, '**{}** lobby #{} was cancelled.'.format(match['mode'], match_id))

        await bot.client.edit_message(match['message'], str(match))
        await bot.client.clear_reactions(match['message'])
        await asyncio.sleep(5)
        await bot.client.delete_message(match['message'])

    async def _mutiny(self, bot, user_id, match_id, match):
        if user_id in match['mutinies']:
            match['mutinies'].remove(user_id)
        else:
            match['mutinies'].append(user_id)

        #cancel match if mutiny votes exceeds half of num_players + 1
        num_players = len([p for p in match['players'] if p])
        if len(match['mutinies']) >= (num_players // 2) + 1:
            await self._cancel_match(bot, match_id)
        else:
            await bot.client.edit_message(match['message'], str(match))

    async def cancel_match_direct(self, bot, user_id, match_id):
        match = self.m_cache.get(match_id)
        if match:
            if match['status'] == Match.LIVE and user_id in match['players']:
                await self._mutiny(bot, user_id, match_id, match)
     
    async def cancel_match_search(self, bot, user_id):
        for m_id, match in self.m_cache.items():
            if user_id in match['players']:
                if match['status'] == Match.LIVE:
                    await self._mutiny(bot, user_id, m_id, match)
                break


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~start
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _start_match(self, bot, match_id, match):
        if match['status'] != Match.LOBBY:
            raise MatchError('Match has already started.')

        if not match['map']:
            random.seed()
            num_maps = len(self.maplist[match['mode']])
            match['map'] = self.maplist[match['mode']][random.randrange(num_maps)]

        match['ready'].clear()
        match['status'] = Match.LIVE

        bot.db.update_match(match_id, match['status'])

        await bot.client.edit_message(match['message'], str(match))
        await bot.client.clear_reactions(match['message'])
        await asyncio.sleep(0.25)

        #notify everyone in the match that their game has started
        notifies = '\n'
        for player in match['players']:
            if player:
                notifies += '<@' + player + '> '
                pname = bot.db.get_player_name(player)
                if pname != 'UNK':
                    notifies += '(' + pname + ') '

        brd_fmt = (match['mode'], match_id, bot.conf.teams['team1'][1],
                   bot.conf.teams['team2'][1], notifies)
        brd_msg = ('**{}** lobby #{} is now LIVE! `\"!end {}\" '
                   'or \"!end {}\" to report a winner.`{}')
        await bot.broadcast(1, brd_msg.format(*brd_fmt))

        await asyncio.sleep(1)
        await bot.client.add_reaction(match['message'], bot.shortcuts['end_blue'])
        await asyncio.sleep(1)
        await bot.client.add_reaction(match['message'], bot.shortcuts['end_red'])
        await asyncio.sleep(1)
        await bot.client.add_reaction(match['message'], bot.shortcuts['cancel'])
        await asyncio.sleep(1)
        await bot.client.add_reaction(match['message'], bot.shortcuts['leave'])
    
    async def start_match_direct(self, bot, user_id, match_id):
        match = self.m_cache.get(match_id)
        if match and user_id == match['host']:
            num_players = (QCDB.MAX_SLOTS * 2) - match['players'].count(None)
            if num_players != bot.conf.modes[match['mode']] * 2:
                raise MatchError('Not enough players to start the match.')
            
            chk = len(match['ready']) + 1 != bot.conf.modes[match['mode']] * 2
            if bot.conf.require_ready and chk:
                raise MatchError('All players must be ready before starting the match.')

            await self._start_match(bot, match_id, match)

    async def start_match_search(self, bot, user_id):
        for m_id, match in self.m_cache.items():
            if user_id == match['host']:
                num_players = (QCDB.MAX_SLOTS * 2) - match['players'].count(None)
                if num_players != bot.conf.modes[match['mode']] * 2:
                    raise MatchError('Not enough players to start the match.')
                chk = len(match['ready']) + 1 != bot.conf.modes[match['mode']] * 2
                if bot.conf.require_ready and chk:
                    raise MatchError('All players must be ready before starting the match.')

                await self._start_match(bot, m_id, match)
                break


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~end
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _end_match(self, bot, match_id, match, winning_team):
        if match['status'] != Match.LIVE:
            raise MatchError('Match has not started yet.')

        #make a list of the winning player ids
        if winning_team == 'team1':
            winners = [x for x in range(QCDB.MAX_SLOTS)]
            winning_team_id = 1
        elif winning_team == 'team2':
            winners = [x for x in range(QCDB.MAX_SLOTS, QCDB.MAX_SLOTS * 2)]
            winning_team_id = 2
        else:
            raise MatchError('Invalid winning team specified.')

        #report wins to the database
        for i, player in enumerate(match['players']):
            if player:
                win = True if i in winners else False
                bot.db.report_match(player, win)

        bot.db.update_match(match_id, winning_team_id)

        #remove match from m_cache
        match['mutinies'].clear()
        match['status'] = winning_team_id
        msg = await bot.client.edit_message(match['message'], str(match))

        del self.m_cache[match_id]

        #broadcast the winners
        winners_ids = [x for x in [match['players'][i] for i in winners] if x is not None]
        winners_names = [discord.utils.get(bot.server.members, id=x).display_name for x in winners_ids]
        brd_fmt = (match['mode'], match_id, ', '.join(winners_names))
        brd_msg = '**{}** lobby #{} has ended. Winner(s): {}.'.format(*brd_fmt)
        await bot.broadcast(3, brd_msg)

        await bot.client.clear_reactions(msg)
        await asyncio.sleep(5)
        await bot.client.delete_message(msg)

    async def end_match_direct(self, bot, user_id, match_id, winning_team):
        match = self.m_cache.get(match_id)
        if match and user_id == match['host']:
            await self._end_match(bot, match_id, match, winning_team)
            
    async def end_match_search(self, bot, user_id, winning_team):
        for m_id, match in self.m_cache.items():
            if user_id == match['host']:
                await self._end_match(bot, m_id, match, winning_team)
                break


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~kick
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _kick_player(self, bot, user_id, match_id, match, ind, reason=''):
        if match['status'] > 0:
            raise MatchError('You cannot kick people after the match has ended.')

        kicked_id = match['players'][ind]

        if kicked_id:
            if kicked_id == user_id:
                raise MatchError('You cannot kick yourself.')

            #remove kicked player from match
            bot.db.remove_player_from_match(match_id, kicked_id)
            match['players'][ind] = None

            if kicked_id in match['mutinies']:
                match['mutinies'].remove(kicked_id)
            if kicked_id in match['ready']:
                match['ready'].remove(kicked_id)
            if kicked_id == match['host']:
                for player in match['players']:
                    if player:
                        match['host'] = player

            #give kicked player a cooldown
            if match['status'] == -1:
                self.ban(bot.client.loop, kicked_id, 5, 'Kicked from a live match.')
                bot.db.report_match(kicked_id, False)
            elif match['status'] == 0:
                self.ban(bot.client.loop, kicked_id, 1, 'Recently kicked from a lobby.')
            else:
                raise MatchError('That slot is empty.')

            kicked_member = discord.utils.get(bot.server.members, id=kicked_id)
            if kicked_member:
                brd_fmt = (kicked_member.display_name, match['mode'], match_id, reason)
                brd_msg = '**{}** was kicked from **{}** lobby #{} ({})'.format(*brd_fmt)
                await bot.broadcast(2, brd_msg)

            #if there are any players left in the lobby, update the message
            for player in match['players']:
                if player:
                    await bot.client.edit_message(match['message'], str(match))
                    break
            else: #otherwise cancel the match
                await self._cancel_match(bot, match_id)
        else:
            raise MatchError('Slot is empty.')

    async def kick_player_direct(self, bot, user_id, match_id, slot, reason=''):
        match = self.m_cache.get(match_id)
        if match:
            ind = self.__offset_slot(bot.conf.modes[match['mode']], slot)
            await self._kick_player(bot, user_id, match_id, match, ind, reason=reason)

    async def kick_player_search(self, bot, user_id, slot):
        for m_id, match in self.m_cache.items():
            if user_id == match['host']:
                if match['status'] != 0:
                    raise MatchError('You cannot kick people after the match has started.')
                
                ind = self.__offset_slot(bot.conf.modes[match['mode']], slot)        
                await self._kick_player(bot, user_id, m_id, match, ind, reason='Kicked by host.')
                break  


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~swap
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def _swap_player_to_team(self, bot, match_id, match, ind, team):
        max_players_team = bot.conf.modes[match['mode']]

        swap_to = -1
        if team == 'team1' and ind >= QCDB.MAX_SLOTS:
            for i, player in enumerate(match['players'][:QCDB.MAX_SLOTS]):
                if i > max_players_team - 1:
                    break
                if not player:
                    swap_to = i
                    break
        elif team == 'team2' and ind < QCDB.MAX_SLOTS:
            for j, player in enumerate(match['players'][QCDB.MAX_SLOTS:]):
                if j > max_players_team - 1:
                    break
                if not player:
                    swap_to = j + QCDB.MAX_SLOTS
                    break
        else:
            raise MatchError('No valid team to swap to.')        

        if swap_to == -1:
            raise MatchError('That team is full.')

        tmp = match['players'][ind]
        match['players'][swap_to] = tmp
        match['players'][ind] = None

        bot.db.change_players_on_team(match_id, 'team1', match['players'][:QCDB.MAX_SLOTS])
        bot.db.change_players_on_team(match_id, 'team2', match['players'][QCDB.MAX_SLOTS:])
        
        await bot.client.edit_message(match['message'], str(match))

    async def _swap_players(self, bot, match_id, match, ind1, ind2):
        tmp = match['players'][ind1]
        tmp2 = match['players'][ind2]
        match['players'][ind2] = tmp
        match['players'][ind1] = tmp2

        if tmp or tmp2:
            bot.db.change_players_on_team(match_id, 'team1', match['players'][:QCDB.MAX_SLOTS])
            bot.db.change_players_on_team(match_id, 'team2', match['players'][QCDB.MAX_SLOTS:])

            await bot.client.edit_message(match['message'], str(match))

    async def swap_players_search(self, bot, user_id, slot1, slot2):
        for m_id, match in self.m_cache.items():
            if user_id == match['host']:
                if match['status'] != 0:
                    raise MatchError('You cannot swap people after the match has started.')

                max_players_team = bot.conf.modes[match['mode']]
                ind1 = self.__offset_slot(max_players_team, slot1)
                ind2 = self.__offset_slot(max_players_team, slot2)
 
                await self._swap_players(bot, m_id, match, ind1, ind2)
                break    
      
    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~give_host
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def give_host_search(self, bot, user_id, slot):
        for m_id, match in self.m_cache.items():
            if user_id == match['host']:
                max_players_team = bot.conf.modes[match['mode']]

                if slot < 0 or slot > ((max_players_team * 2) - 1):
                    raise MatchError('Invalid slot number.')

                if slot >= max_players_team:
                    slot += (QCDB.MAX_SLOTS - max_players_team)

                target_id = match['players'][slot]
                if target_id:
                    match['host'] = target_id
                    if target_id in match['ready']:
                        match['ready'].remove(target_id)
                    bot.db.change_host(m_id, target_id)

                    await bot.client.edit_message(match['message'], str(match))
                else:
                    raise MatchError('Slot is empty.')


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~promote
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def promote_search(self, bot, user_id):
        for m_id, match in self.m_cache.items():
            if user_id in match['players']:
                num_players = (QCDB.MAX_SLOTS * 2) - match['players'].count(None)
                max_players = bot.conf.modes[match['mode']] * 2

                if match['status'] == 0:
                    if num_players == max_players:
                        mention = '<@' + match['host'] + '>'
                        hint = '(waiting for host to start) `\"{}start\" to go live.`'.format(bot.conf.prefix)
                    else:
                        if bot.conf.pug_role.id != bot.server.id:
                            mention = '<@&' + bot.conf.pug_role.id + '>'
                        else:
                            mention = ''
                        hint = '(waiting for players) `\"{}join {}\" to play.`'.format(bot.conf.prefix, m_id)

                    await bot.broadcast(1,
                        '{} **{}** lobby #{} **[{}/{}]** {}'
                        .format(mention, match['mode'], m_id, num_players, max_players, hint))
                break


    #~~~~~~~~~~~~~~~~~~~~~~~~~
    #~ready
    #~~~~~~~~~~~~~~~~~~~~~~~~~

    async def unready(self, bot, user_id, user_name, match_id, match):
        if match['status'] == 0 and user_id != match['host']:
            if user_id in match['ready']:
                match['ready'].remove(user_id)
            
            await bot.client.edit_message(match['message'], str(match))
            await bot.broadcast(4, '**{}** is no longer ready.'.format(user_name))

    async def _ready(self, bot, user_id, user_name, match_id, match, online_status):
        if online_status in ('offline', 'idle', 'dnd'):
            raise MatchError('You cannot ready up while offline/AFK/DND.')

        if match['status'] == 0 and user_id != match['host']:
            if user_id in match['ready']:
                match['ready'].remove(user_id)
                await bot.broadcast(4, '**{}** is no longer ready.'.format(user_name))
            else:
                match['ready'].append(user_id)

                if len(match['ready']) + 1 == bot.conf.modes[match['mode']] * 2:
                    ready_msg = '<@{}> All players are ready in **{}** lobby #{}. `\"{}start\" to go live.`'
                    ready_msg_fmt = (match['host'], match['mode'], match_id, bot.conf.prefix)
                    await bot.broadcast(3, ready_msg.format(*ready_msg_fmt))
                else:
                    await bot.broadcast(4, '**{}** is ready!'.format(user_name))

            await bot.client.edit_message(match['message'], str(match))
            
    async def ready_direct(self, bot, user_id, user_name, match_id, online_status):
        match = self.m_cache.get(match_id)
        if match:
            if user_id in match['players']:
                await self._ready(bot, user_id, user_name, match_id, match, online_status)

    async def ready_search(self, bot, user_id, user_name, online_status):
        for m_id, match in self.m_cache.items():
            if user_id in match['players']:
                await self._ready(bot, user_id, user_name, m_id, match, online_status)
                break