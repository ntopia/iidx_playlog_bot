
PLAY_LOG_KEY = 'play_log'
def fieldPlaycount( play_side, title ):
	return 'pc.%d.%s' % ( play_side, title )
def fieldHistory( play_side, difficulty, title ):
	return '%d.%d.%s' % ( play_side, difficulty, title )

CLEAR_STR = [ 'NO PLAY', 'FAILED', 'ASSIST CLEAR', 'EASY CLEAR', 'CLEAR', 'HARD CLEAR', 'EX HARD CLEAR', 'FULL COMBO' ]
CLEAR_SHORTSTR = [ 'NP', 'FAIL', 'AC', 'EC', 'CL', 'HC', 'EX', 'FC' ]
CLEAR_STR_TO_NUM = { CLEAR_STR[x]: x for x in xrange(len(CLEAR_STR)) }

CLEARIMG_SRC_TO_NUM = {
	'/game/2dx/20/p/images/score_icon/clflg0.gif': 0,
	'/game/2dx/20/p/images/score_icon/clflg1.gif': 1,
	'/game/2dx/20/p/images/score_icon/clflg2.gif': 2,
	'/game/2dx/20/p/images/score_icon/clflg3.gif': 3,
	'/game/2dx/20/p/images/score_icon/clflg4.gif': 4,
	'/game/2dx/20/p/images/score_icon/clflg5.gif': 5,
	'/game/2dx/20/p/images/score_icon/clflg6.gif': 6,
	'/game/2dx/20/p/images/score_icon/clflg7.gif': 7,

	'/game/2dx/21/p/images/score_icon/clflg0.gif': 0,
	'/game/2dx/21/p/images/score_icon/clflg1.gif': 1,
	'/game/2dx/21/p/images/score_icon/clflg2.gif': 2,
	'/game/2dx/21/p/images/score_icon/clflg3.gif': 3,
	'/game/2dx/21/p/images/score_icon/clflg4.gif': 4,
	'/game/2dx/21/p/images/score_icon/clflg5.gif': 5,
	'/game/2dx/21/p/images/score_icon/clflg6.gif': 6,
	'/game/2dx/21/p/images/score_icon/clflg7.gif': 7
}

GRADE_STR = [ 'F', 'E', 'D', 'C', 'B', 'A', 'AA', 'AAA' ]
GRADE_STR_TO_NUM = { GRADE_STR[x]: x for x in xrange(len(GRADE_STR)) }

PLAYSIDE_STR = [ 'SP', 'DP' ]
PLAYSIDE_MAX = len(PLAYSIDE_STR)

DIFFICULTY_STR = [ 'N', 'H', 'A' ]
DIFFICULTY_MAX = len(DIFFICULTY_STR)

BP_INF = 99999999

HISTORY_PROTOTYPE = { 'clear': CLEAR_STR_TO_NUM['NO PLAY'], 'grade': GRADE_STR_TO_NUM['F'], 'score': 0, 'bp': BP_INF }
def isHistoryUpgraded( before, after ):
	for type in HISTORY_PROTOTYPE.iterkeys():
		if type == 'bp':
			if before[ type ] > after[ type ]:
				return True
		else:
			if before[ type ] < after[ type ]:
				return True
	return False

SONG_COUNT_BY_TITLE = [ 175, 113, 81, 101, 180, 54, 120 ]
