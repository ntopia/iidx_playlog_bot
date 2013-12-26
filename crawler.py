
import logging
import sys
import json
import httplib2
import urllib
import Cookie
import time
from datetime import datetime, timedelta
from BeautifulSoup import BeautifulSoup
import redis
import re

from iidx_util import *
from config import *


def getRedis():
	return redis.Redis( db=9 )


def login( kid, password ):
	try:
		http = httplib2.Http()

		loginUrl = 'https://p.eagate.573.jp/gate/p/login.html'
		loginHeader = { 'content-type' : 'application/x-www-form-urlencoded', 'Origin': 'https://p.eagate.573.jp', 'Referer': 'https://p.eagate.573.jp/gate/p/login.html', 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.72 Safari/537.36'  }
		auth_info = { 'KID': kid, 'pass': password, 'OTP': '' }

		params = urllib.urlencode( auth_info )
		res, c = http.request( loginUrl, 'POST', params, headers=loginHeader )
		if res.status == 302:
			cookie = Cookie.SimpleCookie( res['set-cookie'] ).values()[0].OutputString( attrs=[] )
			expires = Cookie.SimpleCookie( res['set-cookie'] ).values()[0]['expires']
			expire_date = datetime.strptime( expires, '%a, %d-%b-%Y %H:%M:%S %Z' ) + timedelta( hours=9 )
			return True, cookie
		else:
			logging.error( 'login : failed..' )
			return False, ''

	except Exception, e:
		logging.error( 'login : %s'%e )
		return False, ''


def logout( cookie ):
	try:
		getHttpContents( 'https://p.eagate.573.jp/gate/p/logout.html', cookie )
	except Exception, e:
		logging.error( 'logout : %s'%e )


def getHttpContents( url, cookie ):
	try:
		http = httplib2.Http()
		res, c = http.request( url, headers={ 'cookie': cookie } )

		if res.status != 200:
			logging.error( 'getHttpContents : %d %s'%( res.status, url ) )
			return None

		if 'err' in res['content-location'] or 'REDIRECT' in res['content-location']:
			logging.error( 'getHttpContents : %s'%url )
			return None

		return BeautifulSoup( c.decode('shift_jisx0213') )

	except Exception, e:
		logging.error( 'getHttpContents : %s %s'%( url, e ) )
		return None


def crawlRecentInfo( page_idx, cookie ):
	try:
		c = getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/djdata/music_info.html?index=%d'%page_idx, cookie )
		if c is None:
			return None

		music_title = c.find( name='div', attrs={ 'class': 'music_info_td' } ).contents[0].strip()

		play_count_str_sp = c.find( name='div', attrs={ 'class': 'musi_info_title_box' } ).find( 'p' ).string
		play_count_sp = int( re.search( '[0-9]+', play_count_str_sp ).group() )
		play_count_dp = 0

		result = {	'title': music_title,
					'play_count': [ play_count_sp, play_count_dp ],
					'data': [ HISTORY_PROTOTYPE.copy() for _ in xrange(PLAYSIDE_MAX*DIFFICULTY_MAX) ] }

		# crawl SP data only (in temp)
		score_table = c.find( name='div', attrs={ 'id': 'sp_table' } )
		rows = score_table.findAll( name='div', attrs={ 'class': 'clear_info' } )
		row_num = 1
		for row in rows:
			cols = row.findAll( name='div', attrs={ 'class': 'clear_cel' } )
			if len(cols) == 0:
				continue

			for k in xrange(DIFFICULTY_MAX):
				if row_num == 1:
					val = cols[k].img['src']
					result['data'][k]['clear'] = CLEARIMG_SRC_TO_NUM[val]
				elif row_num == 2:
					val = 'F' if cols[k].find( 'img' ) == None else cols[k].find( 'img' )['alt']
					result['data'][k]['grade'] = GRADE_STR_TO_NUM[val]
				elif row_num == 3:
					val = cols[k].contents[2]
					val = val[ : val.find('(') ]
					try:
						result['data'][k]['score'] = int(val)
					except ValueError:
						result['data'][k]['score'] = 0
				else:
					val = cols[k].contents[2]
					# we doesn't crawl the miss count
			row_num = row_num + 1

		return result

	except Exception, e:
		logging.error( 'crawlRecentInfo : %s'%e )
		return None


def doUpdateRecent( rival_id ):
	try:
		r = getRedis()

		# get account info
		account = json.loads( r.hget( 'accounts', rival_id ) )
		data_key = account[ 'rival_id' ]
		res, cookie = login( account[ 'eamu_id' ], account[ 'eamu_pass' ] )
		if not res:
			return

		getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/djdata/music_recent.html', cookie )

		for i in xrange( 4, -1, -1 ):
			info = crawlRecentInfo( i, cookie )
			if info == None:
				continue

			for play_side in xrange(1):	# fixed on SP (in temp)
				# PLAY COUNT updating ---------------------------------
				field_pc = fieldPlaycount(play_side, info['title'])
				play_count_before = int(r.hget(data_key, field_pc)) if r.hexists(data_key, field_pc) else 0
				play_count_after = info['play_count'][play_side]
				if play_count_after > 0:
					r.hset( data_key, field_pc, play_count_after )

				# HISTORY updating ---------------------------------
				updated_res = [ None for _ in xrange(DIFFICULTY_MAX) ]
				for difficulty in xrange(DIFFICULTY_MAX):
					field_hs = fieldHistory(play_side, difficulty, info['title'])
					history_before = json.loads(r.hget(data_key, field_hs)) if r.hexists(data_key, field_hs) else HISTORY_PROTOTYPE.copy()
					history_after = info['data'][ play_side*DIFFICULTY_MAX + difficulty ]
					if isHistoryUpgraded( history_before, history_after ):
						r.hset( data_key, field_hs, json.dumps(history_after) )
						updated_res[difficulty] = [ history_before, history_after ]

				# pushing a play log ---------------------------------
				if play_count_before < play_count_after:
					play_log = {}
					play_log['rival_id'] = data_key
					play_log['timestamp'] = int(time.time())
					play_log['play_side'] = play_side
					play_log['title'] = info['title']
					play_log['play_count'] = [ play_count_before, play_count_after ]
					for difficulty in xrange(DIFFICULTY_MAX):
						if updated_res[difficulty] is not None:
							play_log['update_log.%d'%difficulty] = updated_res[difficulty]

					r.rpush( PLAY_LOG_KEY, json.dumps(play_log) )

	except Exception, e:
		logging.error( 'doUpdateRecent : %s'%e )
		return


def doUpdateAll( rival_id ):
	song_count = [ 175, 113, 81, 102, 177, 54, 119 ]
	try:
		r = getRedis()

		# get account info
		account = json.loads( r.hget( 'accounts', rival_id ) )
		data_key = account[ 'rival_id' ]
		res, cookie = login( account[ 'eamu_id' ], account[ 'eamu_pass' ] )
		if not res:
			return

		for song_ct in xrange(len(song_count)):
			print( 'ct:%d' % song_ct )
			getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/djdata/music_title.html?s=1&list=%d'%song_ct, cookie )

			for i in xrange( song_count[song_ct] ):
				info = crawlRecentInfo( i, cookie )
				if info == None:
					continue

				for play_side in xrange(1):	# fixed on SP (in temp)
					# PLAY COUNT updating ---------------------------------
					field_pc = fieldPlaycount(play_side, info['title'])
					play_count_after = info['play_count'][play_side]
					if play_count_after > 0:
						r.hset( data_key, field_pc, play_count_after )

					# HISTORY updating ---------------------------------
					for difficulty in xrange(DIFFICULTY_MAX):
						field_hs = fieldHistory(play_side, difficulty, info['title'])
						history_before = HISTORY_PROTOTYPE.copy()
						history_after = info['data'][ play_side*DIFFICULTY_MAX + difficulty ]
						if isHistoryUpgraded( history_before, history_after ):
							r.hset( data_key, field_hs, json.dumps(history_after) )

	except Exception, e:
		logging.error( 'doUpdateAll : %s'%e )
		return


def addAccount( rival_id, eamu_id, eamu_pass, djname ):
	try:
		r = getRedis()

		account_info = {}
		account_info[ 'rival_id' ] = rival_id
		account_info[ 'eamu_id'] = eamu_id
		account_info[ 'eamu_pass'] = eamu_pass
		account_info[ 'djname' ] = djname

		r.hset( 'accounts', rival_id, json.dumps(account_info) )

	except Exception, e:
		logging.error( 'addAccount : %s'%e )
		return


def doMainJob():
	try:
		r = getRedis()
		user_list = r.hkeys( 'accounts' )
		for user in user_list:
			doUpdateRecent( user )

	except Exception, e:
		logging.error( 'doMainJob : %s'%e )
		return



if len( sys.argv ) > 1:
	cmd = sys.argv[1]
#	if cmd == 'add_account':
#		addAccount( 'your iidx id', 'your eamu id', 'your eamu pass', 'your dj name' )
#	if cmd == 'crawl_all':
#		doUpdateAll( 'your iidx id' )

else:
	doMainJob()

