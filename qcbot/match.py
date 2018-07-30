from .database import QCDB

class Match(dict):
    """Dict that holds match info."""
    
    #match status codes
    LIVE = -1 #in-progress
    LOBBY = 0 #waiting to start
    W_TOP = 1 #match over, top team won
    W_BOT = 2 #match over, bottom team won

    def __init__(self, conf, match_id, host, mode, players=[], status=0, note='', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self['id'] = match_id
        self['host'] = host
        self['mode'] = mode
        self['players'] = players
        self['status'] = status

        self['mutinies'] = []
        self['ready'] = []
        self['needsub'] = []
        self['map'] = ''
        self['note'] = note

        self.max_players_team = conf.modes[mode]
        self.max_players = self.max_players_team * 2
        self.team1_name = conf.teams['team1'][0]
        self.team2_name = conf.teams['team2'][0]

        if kwargs:
            for key, val in kwargs.items():
                self[key] = val

    #def __getattr__(self, attr):
    #    return self.get(attr)

    def __str__(self):
        body = ''
        header = ''
        num_players = len([x for x in self['players'] if x])

        team1 = self['players'][:self.max_players_team]
        team2 = self['players'][QCDB.MAX_SLOTS:(QCDB.MAX_SLOTS + self.max_players_team)]

        body += '\U0001F535 {}\n'.format(self.team1_name)
        for i, player in enumerate(team1):
            if player:
                playername = '<@' + player + '>'

                if player == self['host']:
                    playername += '\U0001F451'
                elif player in self['ready']:
                    playername += ' <- ready!'
                elif player in self['needsub']:
                    playername += ' <- NEEDS SUB!!'
            else:
                playername = ''
            body += '        ' + str(i + 1) + '. ' + playername + '\n'

        body += '\U0001F534 {}\n'.format(self.team2_name)
        for j, player in enumerate(team2):
            if player:
                playername = '<@' + player + '>'

                if player == self['host']:
                    playername += '\U0001F451'
                elif player in self['ready']:
                    playername += ' <- ready!'
                elif player in self['needsub']:
                    playername += ' <- NEEDS SUB! Type \"!sub {}\"'.format(self['id'])          
            else:
                playername = ''
            body += '        ' + str(j + self.max_players_team + 1) + '. ' + playername + '\n'

        header = '#{} **{} [{}/{}]** '.format(self['id'], self['mode'], num_players, self.max_players)

        if num_players == 0 or len(self['mutinies']) >= (num_players // 2) + 1:
            header += '(cancelled)\n'
        elif self['status'] == 0:
            if num_players == self.max_players:
                header += '(waiting for host to start)\n'
            else:
                header += '(waiting for players)\n'
        elif self['status'] == 1:
            header += '(post-game | {} won)\n'.format(self.team1_name)
        elif self['status'] == 2:
            header += '(post-game | {} won)\n'.format(self.team2_name)
        else:
            header += '\U00002757 LIVE \U00002757\n'
            if len(self['mutinies']) > 0:
                body += '[{}/{}] cancel votes.\n'.format(len(self['mutinies']), (num_players // 2) + 1)
            if self['map'] != '':
                body += 'Suggested map: {}\n'.format(self['map'])
        
        if self['note']:
            header += '*' + self['note'] + '*\n'
        return header + body  