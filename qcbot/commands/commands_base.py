from .command import command

import random

@command('help', whitelist=True)
async def help(bot, message, **kwargs):
    cmds = 'USER COMMANDS:\n'
    for cmd in bot.client.cmds:
        allowed_chans = ''
        try:
            help_str = getattr(bot.client.cmds[cmd], 'help_str')
        except:
            help_str = ''
        if bot.client.cmds[cmd].whitelist and bot.conf.whitelist[cmd]:
            allowed_chans = ' ' + str(bot.conf.whitelist[cmd])
        if not bot.client.cmds[cmd].admin_only:
            cmds += (bot.conf.prefix + cmd + ' ' + help_str + allowed_chans + '\n')

    await bot.client.send_message(message.channel, '```' + cmds + '```')

@command('help_admin', admin_only=True)
async def help_admin(bot, message, **kwargs):
    cmds_admin = '\nADMIN COMMANDS:\n'
    for cmd in bot.client.cmds:
        allowed_chans = ''
        try:
            help_str = getattr(bot.client.cmds[cmd], 'help_str')
        except:
            help_str = ''
        if bot.client.cmds[cmd].whitelist and bot.conf.whitelist[cmd]:
            allowed_chans = ' ' + str(bot.conf.whitelist[cmd])
        if bot.client.cmds[cmd].admin_only:
            cmds_admin += (bot.conf.prefix + cmd + ' ' + help_str + allowed_chans + '\n')

    await bot.client.send_message(message.channel, '```' + cmds_admin + '```')

@command('ping', admin_only=True, disallow_private=False)
async def ping(bot, message, **kwargs):
    await bot.client.send_message(message.channel, 'pong')

@command('coin', whitelist=True)
async def coin(bot, message, **kwargs):
    random.seed()
    if bool(random.getrandbits(1)):
        await bot.client.send_message(message.channel, 'heads')
    else:
        await bot.client.send_message(message.channel, 'tails') 