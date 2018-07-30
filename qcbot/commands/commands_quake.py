import discord

from .command import command
from ..exceptions import CommandError, MatchError
from ..bot import QuakeBot

STR_SETUP_CONFIRM = 'This will create a new channel for pickup games. Is this ok? Type \"yes\" to confirm or anything else to cancel.'
STR_SETUP_CHAN = 'Type the name of the channel (without the # symbol) you would like game status to be broadcast to (ex: general).'
STR_SETUP_PUG_ROLE = 'Type the name of the role you want to enable pug functionality for. If you don\'t provide a valid role, it will be set to everyone.'
STR_SETUP_MOD_ROLE = 'Type the name of the role of your server moderators. If you don\'t have a moderator role, just type in gibberish to skip this step.'
STR_SETUP_BAD_ROLE = 'Invalid role or doesn\'t exist. Skipping...'
STR_SETUP_SUCCESS = 'Setup successful. If you need to change something later just delete the pickup-games channel and run !setup again.'

@command('setup', admin_only=True)
async def setup(bot, message, **kwargs):
    if (message.author is message.server.owner) and (message.channel is not bot.conf.pug_chan):
        mention = '<@{}> '.format(message.author.id)

        #confirm
        await bot.client.send_message(message.channel, mention + STR_SETUP_CONFIRM)
        check = await bot.client.wait_for_message(timeout=30, author=message.author, channel=message.channel)

        if check is None:
            raise CommandError('Setup timed out.')
        elif not check.content.startswith('y'):
            raise CommandError('Setup cancelled.')

        #setup broadcast channel - MANDATORY
        await bot.client.send_message(message.channel, mention + STR_SETUP_CHAN)
        check_brd_chan = await bot.client.wait_for_message(timeout=30, author=message.author, channel=message.channel)

        if check_brd_chan is None:
            raise CommandError('Setup timed out.')

        temp_brd_chan = discord.utils.get(message.server.channels, name=check_brd_chan.content)
        if temp_brd_chan is None or temp_brd_chan.id == bot.conf.pug_chan.id:
            raise CommandError('Setup cancelled. Invalid channel or doesn\'t exist.')
        elif not temp_brd_chan.permissions_for(bot.server.me).send_messages:
            raise CommandError('Setup cancelled. That channel does not have proper permissions.')
        else:
            brd_chan = temp_brd_chan
            await bot.client.send_message(message.channel, mention + 'Broadcast channel set to <#{}>.'.format(brd_chan.id))

        #setup pug role
        await bot.client.send_message(message.channel, mention + STR_SETUP_PUG_ROLE)
        check_pug_role = await bot.client.wait_for_message(timeout=30, author=message.author, channel=message.channel)

        if check_pug_role is None:
            raise CommandError('Setup timed out.')

        temp_pug_role = discord.utils.get(message.server.roles, name=check_pug_role.content)

        if temp_pug_role is None:
            pug_role = message.server.default_role
            await bot.client.send_message(message.channel, mention + STR_SETUP_BAD_ROLE)
        else:
            pug_role = temp_pug_role
            await bot.client.send_message(message.channel, mention + 'PUG role set to {}.'.format(pug_role.name))

        #setup mod role
        await bot.client.send_message(message.channel, mention + STR_SETUP_MOD_ROLE)
        check_mod_role = await bot.client.wait_for_message(timeout=30, author=message.author, channel=message.channel)

        if check_mod_role is None:
            raise CommandError('Setup timed out.')

        temp_mod_role = discord.utils.get(message.server.roles, name=check_mod_role.content)

        if temp_mod_role is None or temp_mod_role is message.server.default_role or temp_mod_role.id == pug_role.id:
            mod_role = discord.Object(id='')
            await bot.client.send_message(message.channel, mention + STR_SETUP_BAD_ROLE)
        else:
            mod_role = temp_mod_role
            await bot.client.send_message(message.channel, mention + 'Moderator role set to {}.'.format(mod_role.name))

        #save settings
        try:
            everyone_perms = discord.PermissionOverwrite(add_reactions=True,
                                                         send_messages=True,
                                                         send_tts_messages=False,
                                                         attach_files=False)
            this_bot_perms = discord.PermissionOverwrite(add_reactions=True,
                                                         send_messages=True,
                                                         manage_messages=True,
                                                         read_message_history=True)

            everyone = discord.ChannelPermissions(target=message.server.default_role, overwrite=everyone_perms)
            this_bot = discord.ChannelPermissions(target=message.server.me, overwrite=this_bot_perms)
            pug = await bot.client.create_channel(message.server, 'pickup-games', everyone, this_bot, type=discord.ChannelType.text)
            
            topic_fmt = ' '.join([x for x in bot.conf.modes])
            topic_msg = 'Type !create <gamemode> to make a lobby. Available gamemodes: {}'.format(*topic_fmt)
            await bot.client.edit_channel(pug, topic=topic_msg)
        except discord.DiscordException as e:
            await bot.client.send_message(message.channel, mention + 'Error: Setup failed.\n{}'.format(e.args))
        else:
            bot.conf.pug_chan = pug
            bot.conf.brd_chan = brd_chan
            bot.conf.pug_role = pug_role
            bot.conf.mod_role = mod_role
            bot.dump_config()
            await bot.client.send_message(message.channel, mention + STR_SETUP_SUCCESS)
            await bot.on_ready()

@command('debug', admin_only=True)
async def cfgdump(bot, message, **kwargs):
    settings = bot.conf()
    s = '```config settings:\n'

    s += ''
    for key, val in settings.items():
        if key not in ('maps', 'whitelist', 'modes', 'teams'):
            s += '\"{}\": {}\n'.format(key, val)

    s += '\nactive matches:\n'

    for m_id, match in bot.pug.m_cache.items():
        s += '{} ({}) status: {} host: {}'.format(
            m_id, match['mode'], match['status'], match['host']
            )

    s += '```'

    await bot.client.send_message(message.channel, s)
    
@command('cfg_chan_broadcast', help_str='<channel name>', admin_only=True)
async def change_chan_broadcast(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    chan = discord.utils.get(message.server.channels, name=split_text[1])
    if chan is None or chan.id == bot.conf.pug_chan.id:
        raise CommandError('Invalid channel or doesn\'t exist.')
    if not chan.permissions_for(bot.server.me).send_messages:
        raise CommandError('That channel won\'t allow me to send messages.')

    bot.conf.brd_chan = chan
    bot.dump_config()
    await bot.client.send_message(message.channel, 'Broadcast channel set to <#{}>.'.format(chan.id))

@command('cfg_role_pugger', help_str='<role name>', admin_only=True)
async def change_role_pugger(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    role = discord.utils.get(message.server.roles, name=split_text[1])
    if role is None:
        raise CommandError('Invalid role or doesn\'t exist.')

    bot.conf.pug_role = role
    bot.dump_config()
    await bot.client.send_message(message.channel, 'PUG role set to {}.'.format(role.name))

@command('cfg_role_moderator', help_str='<role name>', admin_only=True)
async def change_role_moderator(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    role = discord.utils.get(message.server.roles, name=split_text[1])
    if role is None:
        raise CommandError('Invalid role or doesn\'t exist.')
    if role is bot.server.default_role:
        raise CommandError('Moderator role cannot be set to the server default role.')
    if role.id == bot.conf.pug_role.id:
        raise CommandError('Moderator role cannot be the same as the PUG role.')

    bot.conf.mod_role = role
    bot.dump_config()
    await bot.client.send_message(message.channel, 'Moderator role set to {}.'.format(role.name))

@command('cfg_prefix', help_str='<char>', admin_only=True)
async def prefix(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if len(split_text[1]) > 1:
        raise CommandError('Prefix must be a single character.')
    if split_text[1] == bot.client.meta_command_prefix:
        raise CommandError('That character is reserved.')

    bot.conf.prefix = split_text[1]
    await bot.client.send_message(message.channel, 'Bot command prefix changed to {}'.format(bot.conf.prefix))

@command('cfg_whitelist', help_str='<command> <channel_1_name> <channel_2_name> <...>', admin_only=True)
async def whitelist(bot, message, split_text=[], **kwargs):
    try:
        if not split_text[2:]:
            raise CommandError('Not enough arguments.')
        if not bot.client.cmds[split_text[1]].whitelist:
            raise CommandError('That command cannot be whitelisted.')

        whitelist_channels = []
        for arg in split_text[2:]:
            chan = discord.utils.find(lambda x: x.name == arg and x.type == discord.ChannelType.text, message.server.channels)
            if chan is not None:
                whitelist_channels.append(chan.name)
            else:
                raise CommandError('Channel not found.')

    except KeyError:
        raise CommandError('Command not found.')
    except CommandError:
        raise
    else:
        bot.conf.whitelist[split_text[1]] = whitelist_channels
        bot.dump_config()
        if whitelist_channels:
            await bot.client.send_message(message.channel, '{} reserved to: {}'.format(split_text[1], whitelist_channels))
        else:
            await bot.client.send_message(message.channel, '{} is now allowed on all channels.'.format(split_text[1]))

@command('cfg_nickme', help_str='<nickname>', admin_only=True)
async def nickme(bot, message, split_text=[], **kwargs):
    await bot.client.change_nickname(message.server.me, ' '.join(split_text[1:]))

@command('cfg_verbosity', help_str='<level (0 to 4, higher = more annoying)>', admin_only=True)
async def verbosity(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Invalid verbosity level.')

    level = int(split_text[1])
    if level < 0:
        raise CommandError('Verbosity level must be >0')
    
    bot.conf.verbosity = level
    bot.dump_config()

    await bot.client.send_message(message.channel, 'Verbosity set to {}.'.format(level))

@command('cfg_require_ready', help_str='<true/false>', admin_only=True)
async def require_ready(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    if split_text[1] == 'true':
        bot.conf.require_ready = True
        bot.dump_config()
        await bot.client.send_message(message.channel, 'Players must now type \"{}ready\" before their match can start.'.format(bot.conf.prefix))
    elif split_text[1] == 'false':
        bot.conf.require_ready = False
        bot.dump_config()
        await bot.client.send_message(message.channel, 'Matches will now start without checking for player readiness.')
    else:
        raise CommandError('Argument must be \'true\' or \'false\'.')

@command('cfg_autokick_afk', help_str='<true/false>', admin_only=True)
async def autokick_afk(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    if split_text[1] == 'true':
        bot.conf.auto_kick = True
        bot.dump_config()
        await bot.client.send_message(message.channel, 'Players will now be automatically kicked from lobbies if they go AFK/offline.')
    elif split_text[1] == 'false':
        bot.conf.auto_kick = False
        bot.dump_config()
        await bot.client.send_message(message.channel, 'Players will now remain in lobbies if they go AFK/offline.')
    else:
        raise CommandError('Argument must be \'true\' or \'false\'.')

@command('cfg_emoji', help_str='<shortcut> <emoji>', admin_only=True)
async def change_shortcut(bot, message, split_text=[], **kwargs):
    if not split_text[2:]:
        raise CommandError('Not enough arguments.')
    if split_text[1] not in bot.conf.emojis:
        raise CommandError('That isn\'t a valid command shortcut.'
                           'The valid ones are \"join_red\",'
                           '\"join_blue\", \"end_red\", \"end_blue\",'
                           '\"ready\", \"cancel\", \"leave\".')
    
    testmsg = await bot.client.send_message(message.channel, 'Attempting to change {}...'.format(split_text[1]))

    emoji = split_text[2]
    if emoji.startswith('<'):
        emoji_id = emoji[emoji.rfind(':') + 1 :].rstrip('>')
        for server_emoji in bot.server.emojis:
            if emoji_id == server_emoji.id:
                shortcut = server_emoji
                break
        else:
            raise CommandError(emoji + ' was not found as a valid emoji in this server.')
    else:
        shortcut = emoji

    try: #to add the emoji to a test message to see if its valid
        await bot.client.add_reaction(testmsg, shortcut)
    except discord.errors.HTTPException:
        raise CommandError(shortcut + ' is not a valid emoji on discord or this server.')
    else:
        bot.shortcuts[split_text[1]] = shortcut

        if isinstance(shortcut, discord.Emoji):
            bot.conf.emojis[split_text[1]] = shortcut.id
        else:
            bot.conf.emojis[split_text[1]] = shortcut

        bot.dump_config()
        await bot.client.edit_message(testmsg, emoji + ' works and is now the shortcut for ' + split_text[1])

@command('ban', help_str='<@name> <minutes> <reason>', mod_only=True)
async def ban(bot, message, split_text=[], **kwargs):
    if not split_text[2:]:
        raise CommandError('Not enough arguments.')
    if not split_text[2].isdigit():
        raise CommandError('Invalid number of minutes.')
    if split_text[3:]:
        reason = ' '.join(split_text[3:])
    else:
        reason = ''

    banned_id = split_text[1].lstrip('<').lstrip('@').lstrip('!').rstrip('>')

    check = discord.utils.get(message.server.members, id=banned_id)
    if not check:
        raise CommandError('That person doesn\'t exist. Make sure to use \'@\'.')
    if check.id == message.author.id:
        raise CommandError('You cannot ban yourself.')
    if check.server_permissions.administrator:
        raise CommandError('You cannot ban admins.')
    if bot.conf.mod_role.id in [role.id for role in check.roles]:
        raise CommandError('You cannot ban moderators.')

    mins = int(split_text[2])
    if mins > 0:
        bot.pug.ban(bot.client.loop, check.id, mins, reason)

        await bot.client.send_message(message.channel, '{} has been banned for {} minutes. Reason: {}'.format(check.display_name, mins, reason))
    
@command('forgive', help_str='<@name>', mod_only=True)
async def forgive(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    banned_id = split_text[1].lstrip('<').lstrip('@').lstrip('!').rstrip('>')

    check = discord.utils.get(message.server.members, id=banned_id)
    if not check:
        raise CommandError('That person doesn\'t exist. Make sure to use \'@\'.')

    if check.id in bot.pug.banned:
        del bot.pug.banned[check.id]
        await bot.client.send_message(message.channel, '{} has been unbanned.'.format(check.display_name))

@command('force_cancel', help_str='<lobby #>', mod_only=True)
async def force_cancel(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Invalid lobby number.')

    lobby_num = int(split_text[1])
    if lobby_num in bot.pug.m_cache:
        try: await bot.pug._cancel_match(bot, lobby_num)
        except MatchError as e: await bot.client.send_message(message.channel, e.args[0])

@command('force_start', help_str='<lobby #>', mod_only=True)
async def force_start(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Invalid lobby number.')

    lobby_num = int(split_text[1])
    if lobby_num in bot.pug.m_cache:
        try: await bot.pug._start_match(bot, lobby_num, bot.pug.m_cache[lobby_num])
        except MatchError as e: await bot.client.send_message(message.channel, e.args[0])

@command('force_end', help_str='<lobby #> <winning team>', mod_only=True)
async def force_end(bot, message, split_text=[], **kwargs):
    if not split_text[2:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Invalid lobby number.')

    if split_text[2] in bot.conf.teams['team1']:
        team = 'team1'
    elif split_text[2] in bot.conf.teams['team2']:
        team = 'team2'
    else:
        raise CommandError('Invalid team.')    
   
    lobby_num = int(split_text[1])
    if lobby_num in bot.pug.m_cache:
        try: await bot.pug._end_match(bot, lobby_num, bot.pug.m_cache[lobby_num], team)
        except MatchError as e: await bot.client.send_message(message.channel, e.args[0])

@command('force_kick', help_str='<lobby #> <slot #>', mod_only=True)
async def force_kick(bot, message, split_text=[], **kwargs):
    if not split_text[2:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Invalid lobby number.')
    if not split_text[2].isdigit():
        raise CommandError('Invalid slot number.')

    slot_num = int(split_text[2]) - 1
    lobby_num = int(split_text[1])
    
    try: await bot.pug.kick_player_direct(bot, message.author.id, lobby_num, slot_num, reason='Force-kicked by moderator.')
    except MatchError as e: await bot.client.send_message(message.channel, e.args[0])

@command('modes', whitelist=True)
async def gamemodes(bot, message, **kwargs):
    s = 'Available modes: `'
    for mode in bot.conf.modes:
        s += mode + ' '
    s += '`'
    await bot.client.send_message(message.channel, s)

@command('create', help_str='<gamemode> <label>', whitelist=True)
async def create(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1] in bot.conf.modes:
        raise CommandError('Invalid gamemode.')

    if split_text[2:]:
        note = ' '.join(split_text[2:])[:24]
    else:
        note = ''

    try:
        await bot.pug.create_match(bot, message.author.id, message.author.display_name, split_text[1], note)
    except MatchError as e:
        await bot.client.send_message(message.channel, e.args[0])

@command('cancel', whitelist=True)
async def cancel(bot, message, **kwargs):
    await bot.pug.cancel_match_search(bot, message.author.id)

@command('join', help_str='<lobby #> <team>', whitelist=True)
async def join(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    #search the config for team name aliases
    team = ''
    if split_text[2:]:
        if split_text[2] in bot.conf.teams['team1']:
            team = 'team1'
        elif split_text[2] in bot.conf.teams['team2']:
            team = 'team2'
        else:
            raise CommandError('Invalid team.')     

    match_id = int(split_text[1])

    try:
        await bot.pug.join_match_direct(bot, message.author.id, message.author.display_name, match_id, team=team)
    except MatchError as e:
        await bot.client.send_message(message.channel, '{}'.format(e.args[0]))

@command('leave', whitelist=True)
async def leave(bot, message, **kwargs):
    try:
        await bot.pug.leave_match_search(bot, message.author.id, message.author.display_name)
    except MatchError as e:
        await bot.client.send_message(message.channel, '{}'.format(e.args[0]))

@command('start', whitelist=True)
async def start(bot, message, **kwargs):
    try:
        await bot.pug.start_match_search(bot, message.author.id)
    except MatchError as e:
        await bot.client.send_message(message.channel, e.args[0])

@command('end', help_str='<winning team>', whitelist=True)
async def end(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    if split_text[1] in bot.conf.teams['team1']:
        team = 'team1'
    elif split_text[1] in bot.conf.teams['team2']:
        team = 'team2'
    else:
        raise CommandError('Invalid team.')       

    await bot.pug.end_match_search(bot, message.author.id, team)

@command('kick', help_str='<slot #>', whitelist=True)
async def kick(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Must provide a slot # to kick.')

    try:
        await bot.pug.kick_player_search(bot, message.author.id, int(split_text[1]) - 1)
    except MatchError as e:
        await bot.client.send_message(message.channel, e.args[0])

@command('swap', help_str='<slot #> <slot #>', whitelist=True)
async def swap(bot, message, split_text=[], **kwargs):
    if not split_text[2:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit() or not split_text[2].isdigit():
        raise CommandError('Must provide two valid slot positions to swap.')

    try:
        await bot.pug.swap_players_search(bot, message.author.id, int(split_text[1]) - 1, int(split_text[2]) - 1)
    except MatchError as e:
        await bot.client.send_message(message.channel, e.args[0])

@command('give_host', help_str='<slot #>', whitelist=True)
async def give_host(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')
    if not split_text[1].isdigit():
        raise CommandError('Must provide a slot # to give host.')

    try:
        await bot.pug.give_host_search(bot, message.author.id, int(split_text[1]) - 1)
    except MatchError as e:
        await bot.client.send_message(message.channel, e.args[0])

@command('promote', whitelist=True)
async def promote(bot, message, **kwargs):
    await bot.pug.promote_search(bot, message.author.id)

"""
@command('sub', whitelist=True)
async def ringer(bot, message, split_text=[], **kwargs):
    try: await bot.pug.replace_search(bot, message.author.id, message.author.display_name)
    except MatchError as e: await bot.client.send_message(message.channel, e.args[0])
"""

@command('ready', whitelist=True)
async def ready(bot, message, **kwargs):
    try: await bot.pug.ready_search(bot, message.author.id, message.author.display_name, message.author.status.value)
    except MatchError as e: await bot.client.send_message(message.channel, e.args[0])

@command('handle', help_str='<name>', whitelist=True)
async def handle(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        raise CommandError('Not enough arguments.')

    new_name = ' '.join(split_text[1:])
    if len(new_name) > 14:
        raise CommandError('That name is too long.')
    
    for char in new_name:
        dec = ord(char)
        if dec == 32:
            continue
        elif dec > 64 and dec < 91:
            continue
        elif dec > 96 and dec < 123:
            continue
        else:
            raise CommandError('Name contains invalid characters.')
    else:
        bot.db.change_player_name(message.author.id, new_name)
        await bot.client.send_message(message.channel, 'Your in-game handle has been changed to ' + new_name)

@command('pugstats', whitelist=True)
async def stats(bot, message, **kwargs):
    stats = bot.db.get_player_record(message.author.id)

    if stats:
        num_matches = stats[1]
        num_wins = stats[2]
        num_losses = num_matches - num_wins

        if num_losses > 0:
            ratio = round(num_wins / num_losses, 2)
        else:
            ratio = num_wins / 1.0

        s = '`{}: {} played | {} W/L | {} ruined`'.format(message.author.display_name, num_matches, ratio, stats[3])
        await bot.client.send_message(message.channel, s)
    else:
        await bot.client.send_message(message.channel, 'No record for {}'.format(message.author.display_name))

@command('top', help_str='<num (max:10)>', whitelist=True)
async def top(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        limit = 5
    elif split_text[1].isdigit():
        limit = int(split_text[1])
    else:
        raise CommandError('Invalid arguments.')

    top_stats = bot.db.get_top_players(limit)

    s = 'TOP LADS:\n```'
    for i, player in enumerate(top_stats):
        member = discord.utils.get(message.server.members, id=player[0])
        display_name = member.display_name if member else player[1]

        num_losses = player[2] - player[3]
        if num_losses > 0:
            ratio = round(player[3] / num_losses, 2)
        else:
            ratio = player[3] / 1.0

        s += '{}. {} | {} played | {} W/L | {} ruined\n'.format(str(i + 1), display_name, str(player[2]), ratio, str(player[4]))

    s += '```'
    await bot.client.send_message(message.channel, s)

@command('recent', help_str='<num (max:10)>', whitelist=True)
async def recent(bot, message, split_text=[], **kwargs):
    if not split_text[1:]:
        limit = 5
    elif split_text[1].isdigit():
        limit = int(split_text[1])
    else:
        raise CommandError('Invalid arguments.')

    recent_matches = bot.db.get_past_matches(limit)

    s = 'Most recent games:\n```'

    for match in recent_matches:
        s += '#{} {} | '.format(match[0], match[2])

        winning_team = 'team' + str(match[3])
        s += 'winner(s): '
        for player in bot.db.get_players_on_team(match[0], winning_team):
            if player:
                member = discord.utils.get(message.server.members, id=player)
                if member:
                    s += member.display_name + ' '
                else:
                    s += str(bot.db.get_player_name(player)) + ' '
        
        s += '\n'

    s += '```'
    await bot.client.send_message(message.channel, s)
