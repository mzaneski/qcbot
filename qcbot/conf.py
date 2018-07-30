import discord

class Config:
    """Server variable data class. Each bot gets its own config object
    which is stored and serialized in its respective directory as
    settings.json"""
    
    #use .copy() or dict()!!
    SERIALIZED_DEFAULTS = {
        'prefix':'!',
        'pug_chan':'',
        'brd_chan':'',
        'pug_role':'',
        'mod_role':'',
        'verbosity':3,
        'require_ready':False,
        'auto_kick':True,
        'modes':{
            'duel':1,
            '2v2':2,
            'tdm':4,
            'sac':4,
            '3v3':3
        },
        'teams':{
            'team1':[
                'Blue Team',
                'blue',
                'blu'
                'Blue',
                'bot',
                'bottom',
                'team1',
                '1'
            ],
            'team2':[
                'Red Team',
                'red',
                'Red',
                'top',
                'team2',
                '2',
            ]
        },
        'maps':{
            'Awoken':['duel', '2v2', 'tdm', '3v3'],
            'Blood Covenant':['duel', '2v2', 'tdm', 'sac', '3v3'],
            'Blood Run':['duel','2v2', '3v3'],
            'Burial Chamber':['tdm', 'sac', '3v3'],
            'Church of Azathoth':['tdm', 'sac', '3v3'],
            'Corrupted Keep':['duel', '2v2', '3v3'],
            'Lockbox':['tdm', 'sac', '3v3'],
            'Ruins of Sarnath':['duel', '2v2', 'tdm', 'sac', '3v3'],
            'Tempest Shrine':['tdm', 'sac', '3v3'],
            'Vale of Pnath':['duel', '2v2', '3v3']
        },
        'emojis':{
            'join_red':'\ud83d\udd34',
            'join_blue':'\ud83d\udd35',
            'end_red':'\ud83d\udd34',
            'end_blue':'\ud83d\udd35',
            'ready':'\u2705',
            'cancel':'\u274c',
            'leave':'\ud83d\udeaa',
        },
        'whitelist':{},
    }

    REGIONS = {'na':':flag_us:', 'eu':':flag_eu:', 'ru':':flag_ru:', 'aus':':flag_au:'}

    def __init__(self, settings):
        self.prefix = settings['prefix']
        self.pug_chan = discord.Object(id=settings['pug_chan'])
        self.brd_chan = discord.Object(id=settings['brd_chan'])
        self.pug_role = discord.Object(id=settings['pug_role'])
        self.mod_role = discord.Object(id=settings['mod_role'])
        self.verbosity = settings['verbosity']
        self.require_ready = settings['require_ready']
        self.auto_kick = settings['auto_kick']
        self.modes = settings['modes']
        self.teams = settings['teams']
        self.maps = settings['maps']
        self.emojis = settings['emojis']
        self.whitelist = settings['whitelist']

    def __call__(self):
        return self.serial()

    def serial(self):
        settings = {
            'prefix':self.prefix,
            'pug_chan':self.pug_chan.id,
            'brd_chan':self.brd_chan.id,
            'pug_role':self.pug_role.id,
            'mod_role':self.mod_role.id,
            'verbosity':self.verbosity,
            'require_ready':self.require_ready,
            'auto_kick':self.auto_kick,
            'modes':self.modes,
            'teams':self.teams,
            'maps':self.maps,
            'emojis':self.emojis,
            'whitelist':self.whitelist
        }

        return settings

    def generate_maplist(self):
        maplist = {}

        for gamemode in self.modes:
            maplist[gamemode] = []
            for mapname in self.maps:
                if gamemode in self.maps[mapname]:
                    maplist[gamemode].append(mapname)

        return maplist