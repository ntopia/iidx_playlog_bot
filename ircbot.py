# -*- coding: utf-8 -*-

import sys
sys.path.append( './python-irc' )

import time
import logging
import json
import redis
import irc.client
from BufferingBot import BufferingBot, Message

from iidx_util import *
from config import *


def getRedis():
	return redis.Redis( db=9 )


def applyColor( foreground, background = None ):
	if background is None:
		return u'\u0003%s' % foreground
	else:
		return u'\u0003%s,%s' % ( foreground, background )

CLEAR_COLOR = [ u'', applyColor('00','14'), applyColor('00','06'), \
	applyColor('01','09'), applyColor('00','10'), applyColor('00','04'), applyColor('01','08'), applyColor('00','02') ]


def makeUpdateLog( play_log, difficulty, account, music_info ):
	key = 'update_log.%d' % difficulty
	if key not in play_log:
		return None

	lv_str = ''
	if music_info is not None:
		lv_str = '(lv.%d)' % music_info['lv'][difficulty]

	out = u'[%s] \u0002%s\u000f %s%s%s \u0002|\u000f ' % ( account['djname'], play_log['title'], PLAYSIDE_STR[play_log['play_side']], DIFFICULTY_STR[difficulty], lv_str )

	history_b = play_log[key][0]
	history_a = play_log[key][1]

	if history_b['clear'] < history_a['clear']:
		out += u'%s%s\u000f -> ' % ( CLEAR_COLOR[ history_b['clear'] ], CLEAR_STR[ history_b['clear'] ] )
	out += u'%s%s\u000f \u0002|\u000f ' % ( CLEAR_COLOR[ history_a['clear'] ], CLEAR_STR[ history_a['clear'] ] )

	if history_b['score'] < history_a['score']:
		out += u'%d/%s -> ' % ( history_b['score'], GRADE_STR[ history_b['grade'] ] )
	out += u'\u0002%d/%s\u000f' % ( history_a['score'], GRADE_STR[ history_a['grade'] ] )

	return out

def makeOnlyPlayLog( play_log, account, music_info ):
	out = u'[%s] \u0002%s\u000f 을(를) 플레이했지만 아무일도 일어나지 않았다!' % ( account['djname'], play_log['title'] )
	return out


class IIDXBot( BufferingBot ):
	def __init__( self, target_chans ):
		server = ( bot_irc_server, bot_irc_port )
		BufferingBot.__init__( self, [server], bot_irc_nickname,
			username = 'iidx_log_bot', realname = 'iidx_log_bot',
			buffer_timeout = -1, use_ssl = bot_use_ssl )

		self.target_chans = target_chans
		self.connection.add_global_handler( 'welcome', self._on_connected )
		logging.info( 'init end' )

	def _on_connected( self, conn, _ ):
		logging.info( 'connected' )
		self.ircobj.execute_delayed( 2, self._iter_func )

	def _iter_func( self ):
		logging.info( 'iterating...%d' % int(time.time()) )

		r = getRedis()
		play_log_json = r.lpop( PLAY_LOG_KEY )
		while play_log_json is not None:
			play_log = json.loads( play_log_json )
			account = json.loads( r.hget( 'accounts', play_log['rival_id'] ) )

			music_info = None
			if r.hexists( 'music_info', play_log['title'] ):
				music_info = json.loads( r.hget( 'music_info', play_log['title'] ) )

			for chan in self.target_chans:
				pushed = False
				for difficulty in xrange(DIFFICULTY_MAX):
					out = makeUpdateLog( play_log, difficulty, account, music_info )
					if out is None:
						continue
					message = Message( 'privmsg', ( chan, out ), timestamp = time.time() )
					self.push_message( message )
					pushed = True

				if not pushed:
					out = makeOnlyPlayLog( play_log, account, music_info )
					message = Message( 'privmsg', ( chan, out ), timestamp = time.time() )
					self.push_message( message )

			play_log_json = r.lpop( PLAY_LOG_KEY )

		self.ircobj.execute_delayed( 37, self._iter_func )

	def pop_buffer( self, message_buffer ):
		message = message_buffer.peek()
		if message.command in ['privmsg']:
			target = message.arguments[0]
			chan = target.lower()
			if irc.client.is_channel( chan ):
				if chan not in [_.lower() for _ in self.channels]:
					logging.info( 'joinning into... %s' % chan )
					self.connection.join( chan )
		return BufferingBot.pop_buffer( self, message_buffer )


def main():
	logging.basicConfig( level = logging.INFO )

	iidx_log_bot = IIDXBot( bot_target_chans )
	while True:
		try:
			iidx_log_bot.start()
		except KeyboardInterrupt:
			logging.exception( '' )
			break
		except:
			logging.exception( '' )
			raise

if __name__ == '__main__':
	main()
