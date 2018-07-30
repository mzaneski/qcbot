import sqlite3

class DatabaseAPI:

    def __init__(self, dbname):
        self.dbname = dbname

    def __touch(self, dbname):
        try:
            db = sqlite3.connect(dbname)
        except sqlite3.Error as e:
            print('DB Error: {}'.format(e))
        finally:
            db.close()

    def setup(self, filename):
        try:
            with open(filename, 'r') as f:
                stripped_lines = []
                for line in f.readlines():
                    if not line.startswith('--'): stripped_lines.append(line)
                queries = ''.join(stripped_lines).split(';')

                while '' in queries:
                    queries.remove('')
        except IOError as e:
            print('Error opening sql schema: {}'.format(e))
        else:
            try:
                db = sqlite3.connect(self.dbname)

                with db:
                    c = db.cursor()
                    for q in queries:
                        c.execute(q)
            except sqlite3.Error as e:
                print('Error executing sql schema: {}'.format(e))
            else:
                db.close()

    def _db_get(self, query, *args):
        if not query.lower().startswith('select'):
            print('Non-select query used with db_get. Returning empty.')
            return []
        
        select = []
        try:
            db = sqlite3.connect(self.dbname)
            c = db.cursor()

            c.execute(query, args)
            select = c.fetchall()

        except sqlite3.Error as e:
            print('DB Error: {}'.format(e))
        else:
            db.close()

        return select

    def _db_set(self, query, *args):
        if not query.lower().startswith(('insert into', 'update', 'delete from')):
            print('Bad query with db_set. Only INSERT, UPDATE, DELETE are allowed.')
            return False

        try:
            db = sqlite3.connect(self.dbname)

            with db:
                c = db.cursor()
                c.execute("PRAGMA foreign_keys = ON",)
                c.execute(query, args)

        except sqlite3.Error as e:
            print('DB Error: {}'.format(e))
            return False
        else:
            db.close()
            return True

class QCDB(DatabaseAPI):

    TPLAYERS = 'players'
    CPLAYERID = 'id'
    CNAME = 'handle'
    CMATCHES = 'matches'
    CWINS = 'wins'
    CRUINS = 'ruins'

    TMATCHES = 'matches'
    TACTIVE = 'matches_active'
    CMATCHID = 'id'
    CMODE = 'mode'
    CHOSTID = 'hostid'
    CWINNER = 'winner'

    TTEAM1 = 'team1'
    TTEAM2 = 'team2'
    CTEAMID = 'id'
    CSLOT0 = 'slot0'
    CSLOT1 = 'slot1'
    CSLOT2 = 'slot2'
    CSLOT3 = 'slot3'

    MAX_SLOTS = 4

    def __init__(self, dbname):
        super().__init__(dbname)

    #------
    #Player
    #------
    def get_player_record(self, player_id):
        fill_ins = (QCDB.CNAME, QCDB.CMATCHES, QCDB.CWINS, QCDB.CRUINS, QCDB.TPLAYERS, QCDB.CPLAYERID)
        get = self._db_get('SELECT {}, {}, {}, {} FROM {} WHERE {} == ?'.format(*fill_ins), player_id)

        if not get:
            return []
        return get[0]

    def get_player_name(self, player_id):
        fill_ins = (QCDB.CNAME, QCDB.TPLAYERS, QCDB.CPLAYERID)
        get = self._db_get('SELECT {} FROM {} WHERE {} == ?'.format(*fill_ins), player_id)

        if not get:
            return []
        return get[0][0]

    def get_top_players(self, limit):
        fill_ins = (QCDB.CPLAYERID, QCDB.CNAME, QCDB.CMATCHES, QCDB.CWINS, QCDB.CRUINS, QCDB.TPLAYERS)
        
        lim = 5 if limit > 10 or limit < 1 else limit
        return self._db_get(
            'SELECT {0}, {1}, {2}, {3}, {4}, (({2} * {3}) / ({2} - {3} + 1)) AS power FROM {5} ORDER BY power DESC, {4} ASC LIMIT ?'
            .format(*fill_ins), lim
            )

    def add_player(self, player_id, name):
        fill_ins = (QCDB.TPLAYERS, QCDB.CPLAYERID, QCDB.CNAME)
        self._db_set('INSERT INTO {} ({}, {}) VALUES (?, ?)'.format(*fill_ins), player_id, name)

    def remove_player(self, player_id):
        fill_ins = (QCDB.TPLAYERS, QCDB.CPLAYERID)
        self._db_set('DELETE FROM {} WHERE {} == ?'.format(*fill_ins), player_id)

    def report_match(self, player_id, bWin):
        if bWin:
            fill_ins = (QCDB.TPLAYERS, QCDB.CMATCHES, QCDB.CMATCHES, QCDB.CWINS, QCDB.CWINS, QCDB.CPLAYERID)
            q = 'UPDATE {} SET {} = {} + 1, {} = {} + 1 WHERE {} == ?'.format(*fill_ins)
        else:
            fill_ins = (QCDB.TPLAYERS, QCDB.CMATCHES, QCDB.CMATCHES, QCDB.CPLAYERID)
            q = 'UPDATE {} SET {} = {} + 1 WHERE {} == ?'.format(*fill_ins)
        
        self._db_set(q, player_id)

    def report_ruined_match(self, player_id):
        fill_ins = (QCDB.TPLAYERS, QCDB.CMATCHES, QCDB.CRUINS, QCDB.CPLAYERID)
        self._db_set('UPDATE {0} SET {1} = {1} + 1, {2} = {2} + 1 WHERE {3} == ?'.format(*fill_ins), player_id)

    def change_player_record(self, player_id, matches, wins):
        fill_ins = (QCDB.TPLAYERS, QCDB.CMATCHES, QCDB.CWINS, QCDB.CPLAYERID)
        self._db_set('UPDATE {} SET {} = ?, {} = ? WHERE {} == ?'.format(*fill_ins), matches, wins, player_id)

    def change_player_name(self, player_id, name):
        fill_ins = (QCDB.TPLAYERS, QCDB.CNAME, QCDB.CPLAYERID)
        self._db_set('UPDATE {} SET {} = ? WHERE {} == ?'.format(*fill_ins), name, player_id)

    #-----
    #Match
    #-----

    def get_match(self, match_id):
        fill_ins = (QCDB.TMATCHES, QCDB.CMATCHID)
        get = self._db_get('SELECT * FROM {} WHERE {} == ?'.format(*fill_ins), match_id)
        
        if not get:
            return []
        return get[0]

    def get_match_mode(self, match_id):
        fill_ins = (QCDB.CMODE, QCDB.TMATCHES, QCDB.CMATCHID)
        get = self._db_get('SELECT {} FROM {} WHERE {} == ?'.format(*fill_ins), match_id)
        
        if not get:
            return []
        return get[0][0]

    def get_active_match_status(self, match_id):
        fill_ins = (QCDB.CWINNER, QCDB.TACTIVE, QCDB.CMATCHID)
        get = self._db_get('SELECT {} FROM {} WHERE {} == ?'.format(*fill_ins), match_id)
        
        if not get:
            return []
        return get[0][0]

    def get_active_match_by_host(self, host_id):
        fill_ins = (QCDB.TACTIVE, QCDB.CHOSTID)
        get = self._db_get('SELECT * FROM {} WHERE {} == ?'.format(*fill_ins), host_id)
        
        if not get:
            return []
        return get[0]

    def get_active_match_id_by_host(self, host_id):
        fill_ins = (QCDB.CMATCHID, QCDB.TACTIVE, QCDB.CHOSTID)
        get = self._db_get('SELECT {} FROM {} WHERE {} == ?'.format(*fill_ins), host_id)
        
        if not get:
            return []
        return get[0][0]

    def get_active_matches(self):
        fill_ins = (QCDB.TACTIVE, QCDB.CMATCHID)
        return self._db_get('SELECT * FROM {} ORDER BY {} ASC'.format(*fill_ins))

    def get_past_matches(self, limit):
        fill_ins = (QCDB.TMATCHES, QCDB.CWINNER, QCDB.CMATCHID)

        lim = 5 if limit > 10 or limit < 1 else limit
        return self._db_get('SELECT * FROM {} WHERE {} > 0 ORDER BY {} DESC LIMIT ?'.format(*fill_ins), lim)

    def create_match(self, host_id, mode):
        fill_ins = (QCDB.TMATCHES, QCDB.CMODE, QCDB.CHOSTID)
        self._db_set('INSERT INTO {} ({}, {}) VALUES (?, ?)'.format(*fill_ins), mode, host_id)

        match_id = self.get_active_match_id_by_host(host_id)
        self._create_teams(match_id, host_id)
        return match_id

    def update_match(self, match_id, winner):
        fill_ins = (QCDB.TMATCHES, QCDB.CWINNER, QCDB.CMATCHID, QCDB.CWINNER)
        self._db_set('UPDATE {} SET {} == ? WHERE {} == ? AND {} < 1'.format(*fill_ins), winner, match_id)

    def remove_match(self, match_id):
        fill_ins = (QCDB.TMATCHES, QCDB.CMATCHID)
        self._db_set('DELETE FROM {} WHERE {} == ?'.format(*fill_ins), match_id)

    def change_host(self, match_id, player_id):
        players_in_match = self.get_all_players_in_match(match_id)

        for player in players_in_match:
            if player == player_id:
                self._db_set('UPDATE {} SET {} == ? WHERE {} == ?'.format(QCDB.TMATCHES, QCDB.CHOSTID, QCDB.CMATCHID), player_id, match_id)

    def get_all_players_in_match(self, match_id):
        p1 = self.get_players_on_team(match_id, 'team1')
        p2 = self.get_players_on_team(match_id, 'team2')

        if p1 and p2:
            return [player for player in (p1 + p2)]
        else:
            return []

    def get_players_on_team(self, match_id, team):
        if team in (QCDB.TTEAM1, QCDB.TTEAM2):
            fill_ins = (QCDB.CSLOT0, QCDB.CSLOT1, QCDB.CSLOT2, QCDB.CSLOT3, team, QCDB.CMATCHID)
            get = self._db_get('SELECT {}, {}, {}, {} FROM {} WHERE {} == ?'.format(*fill_ins), match_id)
                    
            if not get:
                return []
            return get[0]
        else:
            return []

    def add_player_to_match(self, match_id, player_id, team, maxplayers):
        players_in_match = self.get_all_players_in_match(match_id)

        slot_added = -1
        #make sure we cant add the player twice
        for player in players_in_match:
            if player == player_id:
                return
        
        players_on_team = self.get_players_on_team(match_id, team)

        #add player to first empty (None) slot if maxplayers hasn't been surpassed
        if players_on_team:
            for i, player in enumerate(players_on_team):
                if i > (maxplayers - 1):
                    break
                if player is None:
                    self._db_set('UPDATE {} SET {} = ? WHERE {} == ?'.format(team, 'slot' + str(i), QCDB.CMATCHID), player_id, match_id)
                    slot_added = i
                    break

        return slot_added

    def remove_player_from_match(self, match_id, player_id):
        success = False
        players_in_match = self.get_all_players_in_match(match_id)

        for i, player in enumerate(players_in_match):
            if player == player_id:
                if i < (len(players_in_match) // 2):
                    success = self._db_set('UPDATE {} SET {} = null WHERE {} == ?'.format(QCDB.TTEAM1, 'slot' + str(i), QCDB.CMATCHID), match_id)
                else:
                    success = self._db_set('UPDATE {} SET {} = null WHERE {} == ?'.format(QCDB.TTEAM2, 'slot' + str(i - (len(players_in_match) // 2)), QCDB.CMATCHID), match_id)
                break

        return success

    def change_players_on_team(self, match_id, team, new):
        if team in (QCDB.TTEAM1, QCDB.TTEAM2):
            fill_ins = (team, QCDB.CSLOT0, QCDB.CSLOT1, QCDB.CSLOT2, QCDB.CSLOT3, QCDB.CMATCHID)
            self._db_set('UPDATE {} SET {} = ?, {} = ?, {} = ?, {} = ? WHERE {} == ?'.format(*fill_ins), new[0], new[1], new[2], new[3], match_id)

    #-----
    #Teams
    #-----

    def _create_teams(self, match_id, host_id):
        #create rows in team1, team2 tables and add the host to the first team
        self._db_set('INSERT INTO {} ({}, {}) VALUES (?, ?)'.format(QCDB.TTEAM1, QCDB.CTEAMID, QCDB.CSLOT0), match_id, host_id)
        self._db_set('INSERT INTO {} ({}) VALUES (?)'.format(QCDB.TTEAM2, QCDB.CTEAMID), match_id)