import json
import time
import argparse
import os

#BreakawayCD rip handler script v0.11 - Leif Claesson 2025

"""
If we only want to archive tracks that were actually played, we have to wait until the
disc is being ejected to be able to know for sure. (writeOnEject = True)
But, if we're archiving whole discs, we can write as soon as ripping is done. (writeOnEject = False)
"""
writeOnEject = False

"""
As a development aid, this script can echo the JSON objects received through the API to a folder.
"""
echo_folder = "c:\\temp\\cdrip\\"


#this example uses the windows registry to keep track of which CDs have already been ripped
import winreg
access_registry = winreg.ConnectRegistry(None,winreg.HKEY_CURRENT_USER)


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


try:
	"""
	If echo_folder is set, we'll write the JSON objects to files.
	The API is called up to _four times_.
	1: When the disc is fully ripped, to ask whether we should write or not.
	2: If #1 said to write, the script gets called again to let you know it's done.
	3: When the disc is _ejected_, to ask whether we should write or not.
	4: If #3 said to write, the script gets called again to let you know it's done.
	
	When a disc has been ripped, you can push the buttons in BreakawayCD to re-run the script as many times as you want.
	This is an invaluable development aid.
	"""
	
	if len(echo_folder):
		code=0

		if data["written"]:
			code |= 1
		if data["ejected"]:
			code |= 2
			
		with open(f'{echo_folder}\\output_{data["deck"]}-{code+1}.txt', "w") as g:
			g.write(filedata)
except:
	pass


if data["error"]:
	print("Error! Don't write.")
	exit(1)	#don't write!

if writeOnEject:
	reg_key = f'SOFTWARE\\BreakawayCD\\Ripped Tracks\\{data["title"]}'
else:
	reg_key = f'SOFTWARE\\BreakawayCD\\Ripped Discs\\{data["title"]}'

if data["ejected"] != writeOnEject:
	# if we're in the wrong state, i.e. we're interested in writing on Eject but
	# the disc has not been ejected, or the other way around, then exit here.
	if(writeOnEject):
		print("Don't write, the disc wasn't ejected yet, only ripped.")
		print("We'll wait until the disc is ejected so we'll know what was actually played.")
	else:
		print("Don't write, the disc was ejected but we already did our work when the disc finished ripping.")
	exit(1)	#don't write!


if writeOnEject:	#keep only the tracks that were played.
	for track in data["track-details"]:
		track["id"] = f'T{track["number"]:02} {data["cddb-id"]}'
		if track["length-bytes"]>0 and "played-bytes" in track:
			fraction = track["played-bytes"] / track["length-bytes"]

			if fraction > 0.8:	#if we've played 80% of the track, keep it
				track["keep"] = True


if data["written"] == False:	#we're being asked permission

	try:
		access_key = winreg.OpenKey(access_registry, reg_key)
	except:
		access_key = None

	if writeOnEject:
		#check whether any of the tracks that have been played need to be written
		doWrite=False
		for track in data["track-details"]:
			if "keep" in track: #we flagged this earlier if more than 80% of the track was played
				alreadyWritten=False
				try:  # have we written this track already?
					regvalue = winreg.QueryValueEx(access_key, track["id"]) if access_key else None
					if len(regvalue) >= 2 and regvalue[1] == winreg.REG_SZ:  # Found, and it's a string as it should be
						if regvalue[0] == track["title"]:  # have we already ripped it with the same CDDB match?
							alreadyWritten = True
				except:
					pass  # we haven't written this track already

				if not alreadyWritten:
					doWrite=True

		if doWrite:
			print("Do write, we need at least one track.")
			exit(0) #go ahead and write
		else:
			print("Don't write, we don't need any tracks.")
			exit(1)	#don't write!

		pass
	else:
		alreadyWritten = False
		try:	#have we written this disc already?
			regvalue=winreg.QueryValueEx(access_key, data["cddb-id"]) if access_key else None
			if len(regvalue)>=1:	#Found
				alreadyWritten=True
		except:
			pass	#we haven't written this disc already

		if alreadyWritten:
			print("Don't write.")
			exit(1)	#don't write!
		else:
			print("Go ahead and write!")
			exit(0) #go ahead and write
else:
	print("Disc has been written.")
	access_key = winreg.CreateKey(access_registry, reg_key)

	if writeOnEject:
		#delete the tracks that were written _in this session_ that we're not interested in
		#but leave any track that was already there, because in order to
		#be there it would have had to have been played in an earlier session!
		for track in data["track-details"]:
			if "keep" in track:
				#set a registry key so we don't write this track again
				winreg.SetValueEx(access_key, track["id"], 0, winreg.REG_SZ, track["title"])
				#this would be a good place to import the track to the playout system.
			if "keep" not in track and track["already-present"] == False:
				print(f'Deleting {track["filepath"]}')
				try:
					os.unlink(track["filepath"])
				except:
					pass
	else:
		# disc has been written!
		# set a registry key so we don't write this disc again
		winreg.SetValueEx(access_key, data["cddb-id"], 0, winreg.REG_NONE, None)
		# this would be a good place to import the disc to the playout system.

	print("Exiting with code 0 (OK)")
	exit(0)	#return 0 = OK



