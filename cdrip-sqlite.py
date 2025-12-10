import json
import time
import argparse
import os
import sqlite3

# BreakawayCD example rip handler script v3.32.49 - modified for SQL storage

###############################################
# trackMode switches the way BreakawayCD writes out its files in ripping mode.
# trackMode = True - writes out JUST the files that played more than 80% (Editable below, search 0.8) and the metadata includes track information
# trackMode = False - writes out the entire CD and changes the metadata output to the disc information only
###############################################

trackMode = True

echo_folder = "c:\\temp\\cdrip\\"
log_file    = "c:\\temp\\cdrip\\logfile.csv"

# ----------------------------------------------------------
# SQL DATABASE INIT (replaces Windows Registry)
# ----------------------------------------------------------
db_path = "c:\\temp\\cdrip\\ripped.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS written_tracks (
    title TEXT,
    track_id TEXT,
    track_title TEXT,
    PRIMARY KEY (title, track_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS written_discs (
    title TEXT,
    cddb_id TEXT,
    PRIMARY KEY (title, cddb_id)
)
""")
conn.commit()
# ----------------------------------------------------------

parser = argparse.ArgumentParser("CD rip handler script")
parser.add_argument("jsonfile", help="Filename of JSON data from BreakawayCD")
args = parser.parse_args()

print(f'Reading JSON file: {args.jsonfile}\n')

filedata = ""
with open(args.jsonfile) as f:
    filedata = f.read()

if filedata:
    data = json.loads(filedata)
    print(json.dumps(data, indent=2))

print("")

# echo JSON stage files
try:
    if len(echo_folder):
        stage = 0
        if data["written"]:
            stage |= 1
        if data["ejected"]:
            stage |= 2

        with open(f'{echo_folder}\\output_{data["deck"]}-{stage+1}.txt', "w") as g:
            g.write(filedata)
except:
    pass

if data["error"]:
    print("Error! Don't write.")
    exit(1)


# ----------------------------------------------------------
# KEY NAME (not used in SQL, but kept for compatibility)
# ----------------------------------------------------------
if trackMode:
    reg_key = f'SOFTWARE\\BreakawayCD\\Ripped Tracks\\{data["title"]}'
else:
    reg_key = f'SOFTWARE\\BreakawayCD\\Ripped Discs\\{data["title"]}'
# ----------------------------------------------------------


# ----------------------------------------------------------
# STATE CHECK (same logic as original)
# ----------------------------------------------------------
if data["ejected"] != trackMode:
    if(trackMode):
        print("Don't write, disc not ejected yet.")
    else:
        print("Don't write, disc was already processed after ripping.")
    exit(1)
# ----------------------------------------------------------

# ----------------------------------------------------------
# Determine which tracks to keep (unchanged)
# ----------------------------------------------------------
if trackMode:
    for track in data["track-details"]:
        track["id"] = f'T{track["number"]:02} {data["cddb-id"]}'
        if track["length-bytes"] > 0 and "played-bytes" in track:
            fraction = track["played-bytes"] / track["length-bytes"]
            if fraction > 0.8:
                track["keep"] = True
# ----------------------------------------------------------

# ======================================================================
# PART 1 — Being asked whether to write (data["written"] == False)
# ======================================================================
if data["written"] == False:

    if trackMode:
        # check SQL instead of registry
        doWrite = False

        for track in data["track-details"]:
            if "keep" in track:
                cur.execute("""
                    SELECT track_title FROM written_tracks
                    WHERE title=? AND track_id=?
                """, (data["title"], track["id"]))
                row = cur.fetchone()

                alreadyWritten = (row is not None and row[0] == track["title"])

                if not alreadyWritten:
                    doWrite = True

        if doWrite:
            print("Do write, we need at least one track.")
            exit(0)
        else:
            print("Don't write, no new tracks needed.")
            exit(1)

    else:
        # entire disc mode
        cur.execute("""
            SELECT 1 FROM written_discs
            WHERE title=? AND cddb_id=?
        """, (data["title"], data["cddb-id"]))
        row = cur.fetchone()

        if row:
            print("Don't write.")
            exit(1)
        else:
            print("Go ahead and write!")
            exit(0)


# ======================================================================
# PART 2 — Data has been written. Now mark in SQL + clean files
# ======================================================================
else:
    print("Disc has been written.")

    if trackMode:
        # Write tracks to SQL
        for track in data["track-details"]:
            if "keep" in track:
                # Insert into SQL instead of registry
                cur.execute("""
                    INSERT OR REPLACE INTO written_tracks (title, track_id, track_title)
                    VALUES (?, ?, ?)
                """, (data["title"], track["id"], track["title"]))
                conn.commit()

                # Write log file entry
                try:
                    with open(log_file, "at") as f:
                        nb = track["length-bytes"]
                        nsec = int(nb/176400)
                        trklen = f'{int(nsec/60)}:{nsec%60}'
                        f.write(f'"TRACK","{track["played-date"]}","{track["played-time"]}",'
                                f'"{data["title"]}","{track["title"]}",{track["number"]},'
                                f'"{trklen}","{data["cddb-id"]}"\n')
                except:
                    pass

            if "keep" not in track and track["already-present"] == False:
                print(f'Deleting {track["filepath"]}')
                try:
                    os.unlink(track["filepath"])
                except:
                    pass

    else:
        # disc write mode
        cur.execute("""
            INSERT OR REPLACE INTO written_discs (title, cddb_id)
            VALUES (?, ?)
        """, (data["title"], data["cddb-id"]))
        conn.commit()

        try:
            with open(log_file, "at") as f:
                nb = sum(t["length-bytes"] for t in data["track-details"])
                nsec=int(nb/176400)
                disclen=f'{int(nsec/60)}:{nsec%60}'
                f.write(f'"DISC","{data["ripped-date"]}","{data["ripped-time"]}",'
                        f'"{data["title"]}","",{data["tracks"]},"{disclen}",'
                        f'"{data["cddb-id"]}"\n')
        except:
            pass

    print("Exiting with code 0 (OK)")
    exit(0)
