
import logging
import sys
import json
import httplib2
import urllib
import Cookie
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import redis
import re

from iidx_util import *
from config import *


def getRedis():
	return redis.Redis( db=9 )


def logout( cookie ):
	try:
		getHttpContents( 'https://p.eagate.573.jp/gate/p/logout.html', cookie )
	except Exception, e:
		logging.error( 'logout : %s'%e )


def getHttpContents( url ):
	try:
		http = httplib2.Http()
		res, c = http.request( url )

		if res.status != 200:
			logging.error( 'getHttpContents : %d %s'%( res.status, url ) )
			return None

		if 'err' in res['content-location'] or 'REDIRECT' in res['content-location']:
			logging.error( 'getHttpContents : %s'%url )
			return None

		return BeautifulSoup( c.decode('utf-8') )

	except Exception, e:
		logging.error( 'getHttpContents : %s %s'%( url, e ) )
		return None


def crawlMusicInfo():
	try:
		r = getRedis()

		c = getHttpContents( 'http://iidxsd.sift-swift.net/view/ac/20/all' )
		if c is None:
			return

		res = c.find_all( 'tr', 'back0' )
		for row in res:
			tds = row.find_all( 'td' )

			title = tds[0].contents[1]
			lv_n = int(tds[4].string) if tds[4].string != '-' else 0
			lv_h = int(tds[5].string) if tds[5].string != '-' else 0
			lv_a = int(tds[6].string) if tds[6].string != '-' else 0

			data = { 'title': title, 'lv': [ lv_n, lv_h, lv_a ] }
			r.hset( 'music_info', title, json.dumps( data ) )

		res = c.find_all( 'tr', 'back1' )
		for row in res:
			tds = row.find_all( 'td' )

			title = tds[0].contents[1]
			lv_n = int(tds[4].string) if tds[4].string != '-' else 0
			lv_h = int(tds[5].string) if tds[5].string != '-' else 0
			lv_a = int(tds[6].string) if tds[6].string != '-' else 0

			data = { 'title': title, 'lv': [ lv_n, lv_h, lv_a ] }
			r.hset( 'music_info', title, json.dumps( data ) )

	except Exception, e:
		logging.error( 'crawlMusicInfo : %s'%e )
		return


crawlMusicInfo()
