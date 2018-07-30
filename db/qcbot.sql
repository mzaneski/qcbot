--sqlite3

PRAGMA encoding = "UTF-8";
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
	
    id      TEXT                 PRIMARY KEY,
    handle  TEXT    DEFAULT "UNK"	NOT NULL,
    matches INTEGER DEFAULT 0       NOT NULL CHECK(matches >= 0),
    wins    INTEGER DEFAULT 0       NOT NULL CHECK(matches >= wins AND wins >= 0),
    ruins   INTEGER DEFAULT 0       NOT NULL CHECK(matches >= ruins AND ruins >= 0)

) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS matches (

	id		INTEGER					PRIMARY KEY,
	hostid	TEXT					NOT NULL,
	mode	TEXT	DEFAULT "UNK"	NOT NULL,
	winner	INTEGER DEFAULT 0		NOT NULL CHECK(winner >= -1 AND winner <= 2),

	FOREIGN KEY (hostid) REFERENCES players(id) ON DELETE SET NULL
);

CREATE VIEW IF NOT EXISTS matches_active AS 
	SELECT id, hostid, mode, winner FROM matches WHERE winner < 1;

CREATE TABLE IF NOT EXISTS team1 (

	id 		INTEGER					PRIMARY KEY,
	slot0 	TEXT					CHECK(slot0 != slot1 AND slot0 != slot2 AND slot0 != slot3),
	slot1 	TEXT					CHECK(slot1 != slot0 AND slot1 != slot2 AND slot1 != slot3),
	slot2 	TEXT					CHECK(slot2 != slot0 AND slot2 != slot1 AND slot2 != slot3),
	slot3 	TEXT					CHECK(slot3 != slot0 AND slot3 != slot1 AND slot3 != slot2),

	FOREIGN KEY (id) REFERENCES matches(id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS team2 (

	id 		INTEGER 				PRIMARY KEY,
	slot0 	TEXT					CHECK(slot0 != slot1 AND slot0 != slot2 AND slot0 != slot3),
	slot1 	TEXT					CHECK(slot1 != slot0 AND slot1 != slot2 AND slot1 != slot3),
	slot2 	TEXT					CHECK(slot2 != slot0 AND slot2 != slot1 AND slot2 != slot3),
	slot3 	TEXT					CHECK(slot3 != slot0 AND slot3 != slot1 AND slot3 != slot2),

	FOREIGN KEY (id) REFERENCES matches(id) ON DELETE CASCADE
) WITHOUT ROWID;