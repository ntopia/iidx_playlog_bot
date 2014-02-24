
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


def requestEAMU( url, method, param={}, header={} ):
	try:
		http = httplib2.Http()

		param_encoded = urllib.urlencode( param )
		result_header = {	'Content-Type': 'application/x-www-form-urlencoded',
							'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36' }
		result_header.update( header )

		return http.request( url, method, param_encoded, result_header )
	except Exception, e:
		return None, None


def login( kid, password ):
	auth_info = { 'KID': kid, 'pass': password, 'OTP': '' }

	res, c = requestEAMU( 'https://p.eagate.573.jp/gate/p/login.html', 'POST', auth_info, {} )
	if res is None:
		logging.error( 'login : failed..' )
		return False, ''
	if res.status == 302:
		cookie = Cookie.SimpleCookie( res['set-cookie'] ).values()[0].OutputString( attrs=[] )
		expires = Cookie.SimpleCookie( res['set-cookie'] ).values()[0]['expires']
		expire_date = datetime.strptime( expires, '%a, %d-%b-%Y %H:%M:%S %Z' ) + timedelta( hours=9 )
		return True, cookie
	else:
		logging.error( 'login : failed..' )
		return False, ''


def getHttpContents( url, cookie, method='GET', param={} ):
	res, c = requestEAMU( url, method, param, { 'Cookie': cookie } )
	if res.status != 200:
		logging.error( 'getHttpContents : %d %s'%( res.status, url ) )
		return None
	if 'location' in res and ( 'err' in res['location'] or 'REDIRECT' in res['location'] ):
		logging.error( 'getHttpContents : %s'%url )
		return None

	return BeautifulSoup( c.decode('shift_jisx0213') )


def crawlRivalString( rival_id, cookie ):
	try:
		rival_id_conv = rival_id.replace( '-', '' )
		c = getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/rival/rival_search.html', cookie, 'POST', {'iidxid':rival_id_conv,'mode':1} )
		if c is None:
			return None

		table = c.find( name='table', attrs={ 'class': 'table_style1' } )
		target_row = table.findAll( 'tr' )[1]
		target_url = target_row.findAll( 'td' )[1].a['href']

		# /game/2dx/21/p/djdata/data_another.html?rival= ~~~~~~
		rival_string = target_url[46:]
		return rival_string

	except Exception, e:
		logging.error( 'crawlRivalString : %s %s'%( rival_id, e ) )
		return None


def crawlRecentInfo( rival_base64, page_idx, cookie, is_admin_data ):
	try:
		c = getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/djdata/compare_rival.html?index=%d&rival=%s'%(page_idx,rival_base64), cookie )
		if c is None:
			return None

		music_title = c.find( name='div', attrs={ 'class': 'music_info_td' } ).contents[0].strip()

		play_count_str_sp = ''#c.find( name='div', attrs={ 'class': 'musi_info_title_box' } ).find( 'p' ).string
		play_count_sp = 0#int( re.search( '[0-9]+', play_count_str_sp ).group() )
		play_count_dp = 0

		result = {	'title': music_title,
					'play_count': [ play_count_sp, play_count_dp ],
					'data': [ HISTORY_PROTOTYPE.copy() for _ in xrange(PLAYSIDE_MAX*DIFFICULTY_MAX) ] }

		# crawl SP data only (in temp)
		score_table = c.find( name='div', attrs={ 'id': 'sp_table' } )
		rows = []
		if is_admin_data:
			rows = score_table.findAll( name='div', attrs={ 'class': 'clear_info' } )[0::2]
		else:
			rows = score_table.findAll( name='div', attrs={ 'class': 'clear_info' } )[1::2]
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
					try:
						result['data'][k]['bp'] = int(val)
					except ValueError:
						result['data'][k]['bp'] = BP_INF
			row_num = row_num + 1

		return result

	except Exception, e:
		logging.error( 'crawlRecentInfo : %s'%e )
		return None


def doUpdateRecent( rival_id ):
	try:
		r = getRedis()

		account = json.loads( r.hget( 'accounts', rival_id ) )
		data_key = account[ 'rival_id' ]
		res, cookie = login( crawl_eamu_id, crawl_eamu_pass )
		if not res:
			return

		rival_base64 = crawlRivalString( rival_id, cookie )
		if not rival_base64:
			logging.error( 'doUpdateRecent : failed to crawl rival_base64' )
			return

		c = getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/djdata/music_recent_another.html?rival=%s'%rival_base64, cookie )
		if c is None:
			logging.error( 'doUpdateRecent : failed to update' )
			return

		for i in xrange( 4, -1, -1 ):
			info = crawlRecentInfo( rival_base64, i, cookie, rival_id == crawl_eamu_rival_id )
			if info == None:
				logging.error( 'recent crawl failed.. %d'%i )
				continue

			for play_side in xrange(1):	# fixed on SP (in temp)
				# PLAY COUNT updating ---------------------------------
				field_pc = fieldPlaycount(play_side, info['title'])
				play_count_before = int(r.hget(data_key, field_pc)) if r.hexists(data_key, field_pc) else 0
				play_count_after = 0#info['play_count'][play_side]
				if play_count_after > 0:
					r.hset( data_key, field_pc, play_count_after )

				# HISTORY updating ---------------------------------
				pushed = False
				for difficulty in xrange(DIFFICULTY_MAX):
					field_hs = fieldHistory(play_side, difficulty, info['title'])
					history_before = json.loads(r.hget(data_key, field_hs)) if r.hexists(data_key, field_hs) else HISTORY_PROTOTYPE.copy()
					history_after = info['data'][ play_side*DIFFICULTY_MAX + difficulty ]
					if isHistoryUpgraded( history_before, history_after ):
						r.hset( data_key, field_hs, json.dumps(history_after) )

						# pushing a play log ---------------------------------
						play_log = {}
						play_log['rival_id'] = data_key
						play_log['timestamp'] = int(time.time())
						play_log['play_side'] = play_side
						play_log['title'] = info['title']
						play_log['difficulty'] = difficulty
						play_log['before'] = history_before
						play_log['after'] = history_after

						r.rpush( PLAY_LOG_KEY, json.dumps(play_log) )
						pushed = True

				if not pushed and play_count_before < play_count_after:
					play_log = {}
					play_log['rival_id'] = data_key
					play_log['timestamp'] = int(time.time())
					play_log['play_side'] = play_side
					play_log['title'] = info['title']

					r.rpush( PLAY_LOG_KEY, json.dumps(play_log) )

	except Exception, e:
		logging.error( 'doUpdateRecent : %s'%e )
		return


def doUpdateAll( rival_id ):
	try:
		r = getRedis()

		if not r.hexists( 'accounts', rival_id ):
			logging.error( 'accounts doesnt exists!' )
			return

		account = json.loads( r.hget( 'accounts', rival_id ) )
		data_key = account[ 'rival_id' ]
		r.delete( data_key )
		res, cookie = login( crawl_eamu_id, crawl_eamu_pass )
		if not res:
			return

		rival_base64 = crawlRivalString( rival_id, cookie )
		if not rival_base64:
			logging.error( 'doUpdateRecent : failed to crawl rival_base64' )
			return

		for group_num in xrange(len(SONG_COUNT_BY_TITLE)):
			logging.info( 'group %d : %d songs'%(group_num, SONG_COUNT_BY_TITLE[group_num]) )
			c = getHttpContents( 'http://p.eagate.573.jp/game/2dx/21/p/djdata/music_title.html?s=1&list=%d&rival=%s'%(group_num,rival_base64), cookie )
			if c is None:
				logging.error( 'crawl failed.. %d'%group_num )
				continue

			for i in xrange( SONG_COUNT_BY_TITLE[group_num] ):
				logging.info( '%d/%d (in group %d)'%(i, SONG_COUNT_BY_TITLE[group_num], group_num) )
				info = crawlRecentInfo( rival_base64, i, cookie, rival_id == crawl_eamu_rival_id )
				if info == None:
					logging.error( 'crawl failed.. %d.%d'%(group_num,i) )
					continue

				for play_side in xrange(1):	# fixed on SP (in temp)
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


def addAccount( rival_id, djname ):
	try:
		r = getRedis()

		account_info = {}
		account_info[ 'rival_id' ] = rival_id
		account_info[ 'djname' ] = djname

		r.hset( 'accounts', rival_id, json.dumps(account_info) )

	except Exception, e:
		logging.error( 'addAccount : %s'%e )
		return


def doMainJob():
	try:
		logging.info( 'start doMainJob!' )

		r = getRedis()
		user_list = r.hkeys( 'accounts' )
		for user in user_list:
			logging.info( 'start crawl user ' + user )
			doUpdateRecent( user )

		logging.info( 'end doMainJob!' )

	except Exception, e:
		logging.error( 'doMainJob : %s'%e )
		return


def main():
	if len(sys.argv) > 1:
		logging.basicConfig( stream=sys.stdout, level=logging.INFO, format='%(asctime)s] %(levelname)s] %(message)s' )

		cmd = sys.argv[1]
		if cmd == 'add_account':
			if len(sys.argv) < 4:
				print( 'BREAK!!')
			else:
				addAccount( sys.argv[2], sys.argv[3] )
				print( 'account registered!' )
		elif cmd == 'crawl_all':
			if len(sys.argv) < 3:
				print( 'BREAK!!' )
			else:
				doUpdateAll( sys.argv[2] )
				print( 'all-updating completed!' )
		else:
			print( 'BREAK!!' )
	
	else:
		logging.basicConfig( filename='log', level=logging.INFO, format='%(asctime)s] %(levelname)s] %(message)s' )

		doMainJob()


if __name__ == '__main__':
	main()
