from ..exceptions import CommandError

def command(name,
            help_str='',
            admin_only=False,
            mod_only=False,
            disallow_private=True,
            whitelist=False):

    def wrap(func):
        async def deco(bot, message, *args, **kwargs):
            if admin_only and not message.author.server_permissions.administrator:
                return
            if mod_only and not message.author.server_permissions.administrator:
                for role in message.author.roles:
                    if role.id == bot.conf.mod_role.id:
                        break
                else:
                    return
            if disallow_private and message.channel.is_private:
                return
            if whitelist:
                if (bot.conf.whitelist[name]
                    and not message.channel.name in bot.conf.whitelist[name]):
                    return

            try:
                await func(bot, message, *args, **kwargs)
            except CommandError as e:
                errfmt = (e.args[0], bot.conf.prefix, name, help_str)
                errmsg = 'Error: {} Usage: `{}{} {}`'.format(*errfmt)
                await bot.client.send_message(message.channel, errmsg)
            except Exception:
                raise
            
        setattr(deco, 'name', name)
        setattr(deco, 'whitelist', whitelist)
        setattr(deco, 'admin_only', admin_only)
        setattr(deco, 'mod_only', mod_only)
        setattr(deco, 'help_str', help_str)

        return deco
    return wrap