import os
import sys
import time
import host
import bf2
import math
import json
import logging
from logging import handlers
import inspect
import datetime as dt
import game.realitytimer as rtimer
import game.realityprism as rprism
import game.realityadmin as radmin
import game.realityconstants as CONSTANTS
import game.realitykits as rkits
import game.realitycore as rcore
import game.realityvehicles as rvehicles


"""
                  !ATTENTION!
This file must be written in Python 2.7, so no:
- f strings
- type hinting


Usage:

\Project Reality BF2\mods\pr\python\game\__init__.py

--Add Import Statement Below to file above--
--Make sure it gets imported and initialized last--

import serverdatadump
serverdatadump.init()

- Create a "datadump" folder in the PR root

"""

refreshSec = 1  # Update stat dump every N seconds
debug = False  # Enumerates bot data as well for use in local, disable to only resolve player data

modDir = str(bf2.gameLogic.getModDir())
# FILES SPECIFIED BELOW ARE WRITTEN TO ROOT GAME/SERVER DIRECTORY
folder = 'datadump'
players_data_file = folder + '/players.json'
squads_data_file = folder + '/squads.json'
server_data_file = folder + '/server.json'
chat_log_file = folder + '/chatlog.log'
lock_file = folder + '/g.lock'


def write_data(data, file):
	"""
	Writes game data to a JSON file with a lock.
	:param data: The data to be written onto a json file.
	:param file: The filepath to the dump file where the data will be written on.
	"""

	with open(lock_file, 'w') as lock:
		lock.write(str(os.getpid()))  # Write the process ID to the lock file

	try:
		with open(file, 'w') as f:
			json.dump(data, f, indent = 2)
	finally:
		os.remove(lock_file)


# Setting a logger
# Grabs the namespace of the caller
caller_frame = inspect.currentframe().f_back  # gets the scope of the caller and ascend one scope
caller_globals = caller_frame.f_globals  # gets the globals of that scope


# Custom Formatter to change the timezone
class CustomFormatter(logging.Formatter):
	def formatTime(self, record, datefmt = None):
		if datefmt:
			return dt.datetime.fromtimestamp(record.created, tz = dt.timezone.utc).astimezone(
				dt.timezone(dt.timedelta(hours = -3))).strftime(datefmt)
		else:
			return super().formatTime(record, datefmt)


# Building Logger
log = logging.getLogger("dumplog")

log_handler = handlers.RotatingFileHandler(
	filename = folder + "/dumplog.log",
	encoding = "utf-8",
	maxBytes = 4 * 1024 * 1024,  # 4 MiB
	backupCount = 0
)

log_formatter = CustomFormatter(
	"%(asctime)s %(name)s [%(levelname)s]: %(message)s",
	datefmt = "[%d/%m - %H:%M:%S]"
)

log_handler.setFormatter(log_formatter)
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)
log.debug("- Log start -")


def init():
	host.registerGameStatusHandler(serverStats)	 # failsafe to ensure callback on map change.		-	[fix issue with this not working]
	host.registerHandler('ChatMessage', onChatMessage)
	rtimer.fireOnce(serverStats, refreshSec)


def onChatMessage(player_id, text, channel, flags):
	p = bf2.playerManager.getPlayerByIndex(player_id)

	# filter chat text
	text = text.replace('HUD_TEXT_CHAT_COMMANDER', '')
	text = text.replace('HUD_TEXT_CHAT_TEAM', '')
	text = text.replace('HUD_TEXT_CHAT_SQUAD', '')
	text = text.replace('HUD_CHAT_DEADPREFIX', '')
	text = text.replace('* ', '')  # This might break some player messages

	try:
		open(chat_log_file, 'a').write(
			str(channel.upper()) + "	" + str(p.getName()) + "	" + str(text) + "\n"
		)	 # [MESSAGE CHANNEL] [PLAYER NAME] [Message]
	except Exception as e:
		log.exception('Failed to write chat message to chatlog file.', exc_info = e)


# Server Data
def serverStats(null):  # Don't remove "null" arg
	# files saved to datadump directory in GAME(local)/SERVER(dedi) directory
	# files are reset on every write, to prevent size inflation & simplify retrieval of data stored within

	# Player Data
	squadData = {}
	playersData = {}
	serverData = {}
	try:  # to prevent runtime failure for random errors
		for p in bf2.playerManager.getPlayers():
			if not debug:
				if p.isAIPlayer() or not p.isAlive():
					continue

			try:
				kit = p.getKit()
				playerKitName = kit.templateName
				pKitStr = rkits.getKitTypeString(playerKitName)
			except Exception as e:
				log.exception('Failed to get player kit.', exc_info = e)
				pKitStr = 'UNKNOWN KIT'

			try:  # Not working, needs to fix.
				# playerVehicle = bf2.objectManager.getRootParent(p.getVehicle())
				# pVehStr = str(getVehicleType(p.getVehicle().templateName))
				# pVehStr = rvehicles.getVehicleTypeString(p.getVehicle().templateName)  # Next to try
				# pVehType = rvehicles.getVehicleType(pVeh)
				pVehStr = str(p.getVehicle().getTemplateProperty())
			except Exception as e:
				log.exception('Failed to get player vehicle.', exc_info = e)
				pVehStr = 'UNKNOWN VEHICLE'
				# pVehType = 'UNKNOWN VEHICLE TYPE'

			try:
				playersData[p.getName()] = {
					'squadNum'							: p.getSquadId(),
					'rank'									: p.score.rank,
					'scoreFrac' 						: p.score.rplScore,
					'scoreSkill'						: p.score.skillScore,
					'scoreTeamWork'					: p.score.rplScore,
					'score'									: p.score.score,
					'bulletsFired'					:	dict(p.score.bulletsFired),
					'kills'									:	p.score.kills,
					'deaths' 								:	p.score.deaths,
					'tks'										:	p.score.TKs,
					'onlineTimeMinutes'			: (int(float(time.time())) - int(float(rprism.GetPlayerHeader(p).replace("\x03",",").split(",")[6]))) / 60,
					'idleTimeMinutes'				: int(radmin.AFKDetection.estimateAFKNess(p) / 60),
					'kit'										: pKitStr,
					'vehicle'								: pVehStr,
					'ping'									: p.getPing(),
					'isAlive'								: bool(p.isAlive()),
					'isDown'								: bool(p.isManDown()),
					'timeToSpawn'						: p.getTimeToSpawn(),
					'suicides'							: p.score.suicides,
					'heals'									: p.score.heals,
					'revives'								: p.score.revives,
					'ammos'									: p.score.ammos,  # Ammo given?
					'repairs'								: p.score.repairs,
					'damageAssists'					: p.score.damageAssists,
					'passengerAssists'			: p.score.passengerAssists,
					'driverAssists'					: p.score.driverAssists,
					'targetAssists'					: p.score.targetAssists,
					'teamDamages'						: p.score.teamDamages,
					'teamVehicleDamages'		:	p.score.teamVehicleDamages,
					'flagCaptures'					: p.score.cpCaptures,
					'flagDefends'						: p.score.cpDefends,
					'flagAssists'						: p.score.cpAssists,
					'flagNeutralizes'				: p.score.cpNeutralizes,
					'flagNeutralizeAssists'	: p.score.cpNeutralizeAssists,
					'team' 									: p.getTeam()
				}
			except Exception as e:
				log.exception('Failed to create player data dict entry.', exc_info = e)

			# Squad Data
			# Ai squads & Ai squad members are ignored completely, if debug is disabled
			# If enabled keep in mind that data will be inconsistent because it will try to get data from both teams
			try:
				squad_id = str(p.getSquadId())
				if squad_id not in squadData:
					squadData[squad_id] = {  # Model
						'name' 			: '',
						'leader'		: '',
						'members'		: [],
						'size' 			: 0,
						'score'			: 0,
						'deaths'		: 0,
						'kills'			:	0,
						'isLocked'	: False
					}

				squadData[squad_id]['name'] = rcore.getPlayerSquadName(p)
				if p.isSquadLeader(): squadData[squad_id]['leader'] = p.getName()
				squadData[squad_id]['members'].append(p.getName())
				squadData[squad_id]['size'] += 1
				squadData[squad_id]['score'] += int(p.score.score)
				squadData[squad_id]['deaths'] += int(p.score.deaths)
				squadData[squad_id]['kills'] += int(p.score.kills)
				squadData[squad_id]['isLocked'] = rcore.getIsSquadLocked(p.getTeam(), p.getSquadId())
			except Exception as e:
				log.exception('Failed to create or update squad data dict entry.', exc_info = e)

		# Map Data
		try:
			currentMapID = int(host.rcon_invoke('admin.currentLevel').strip())
			if currentMapID in radmin.g_mapList:
				_map = radmin.g_mapList[currentMapID]
				mapName = rcore.getMapName(_map[0], True)
				# gamemode = rcore.getGameModeName(_map[1])  # Irrelevant
				layer = _map[2].upper()
				currentMap = mapName
				currentMapLayer = layer

			nextMapID = int(host.rcon_invoke('admin.nextLevel').strip())
			if nextMapID in radmin.g_mapList:
				_map = radmin.g_mapList[nextMapID]
				mapName = rcore.getMapName(_map[0], True)
				# gamemode = rcore.getGameModeName(_map[1])  # Irrelevant
				layer = _map[2].upper()
				nextMap = mapName
				nextMapLayer = layer
		except Exception as e:
			log.exception('Failed to set map data.', exc_info = e)

		# Server Data
		try:
			commander = bf2.playerManager.getCommander(2)
			history = radmin.g_lastPlayedMaps
			for m in history:
				x = m.split(' Co-op ')
				x[1] = x[1].upper()
				m = ' '.join(x)

			serverData = {
				'currentMap'					: currentMap,
				'currentMapLayer'			: currentMapLayer,
				'currentMapAndLayer'	: currentMap + ' ' + currentMapLayer,
				'nextMap'							: nextMap,
				'nextMapLayer'				: nextMapLayer,
				'nextMapAndLayer'			: nextMap + ' ' + nextMapLayer,
				'history'							: history,
				# 'gameMode'						: host.ss_getParam('gameMode'),  # gmp_coop - Irrelevant
				'serverUptime'				: host.timer_getWallTime(),
				'roundTime'						: rcore.getTimeSinceRoundStart(),
				'playersInclAi'				: bf2.playerManager.getNumberOfPlayers(),
				'bTeamName'						: bf2.gameLogic.getTeamName(1),
				'bTeamTickets'				: bf2.gameLogic.getTickets(1),
				'bTeamAliveNum'				: bf2.playerManager.getNumberOfAlivePlayersInTeam(1),  # a useful additional signifier to identify maps with broken spawns for instance...
				'pTeamName'						: bf2.gameLogic.getTeamName(2),
				'pTeamTickets'				: bf2.gameLogic.getTickets(2),
				'pTeamCommander'			: commander.getName() if commander is not None else None,
				'pTeamNumExclAi'			: bf2.playerManager.getNumberOfPlayersInTeam(2),
				'pTeamAliveNum'				: bf2.playerManager.getNumberOfAlivePlayersInTeam(2),  # signifies how many players have spawned
				# Need to turn it into a list of names, for now we count dict items
				'admins'							: len(radmin.g_admins) + len(radmin.g_lite_admins),
				'adminsPrism'					: len(radmin.g_prism_admins),
				# 'maxPlayers'					: host.ss_getParam(maxPlayers)  # not working
			}
		except Exception as e:
			log.exception('Failed to create server data dict.', exc_info = e)

		# Server Data Dump
		try:
			# json.dump(serverData, open(server_data_file, 'w'), indent = 2)
			write_data(serverData, server_data_file)
		except Exception as e:
			log.exception('Failed to write server data file.', exc_info = e)

		# Squad Data Dump
		try:
			# json.dump(squadData, open(squads_data_file, 'w'), indent = 2)
			write_data(squadData, squads_data_file)
		except Exception as e:
			log.exception('Failed to write squad data file.', exc_info = e)

		# Player Data Dump
		try:
			# json.dump(playersData, open(players_data_file, 'w'), indent = 2)
			write_data(playersData, players_data_file)
		except Exception as e:
			log.exception('Failed to write player data file.', exc_info = e)


	except Exception as e:
		log.exception('Main script function has failed!', exc_info = e)

	rtimer.fireOnce(serverStats, refreshSec)