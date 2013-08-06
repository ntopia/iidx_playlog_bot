
PLAY_LOG_KEY = 'play_log'
def fieldPlaycount( play_side, title ):
	return 'pc.%d.%s' % ( play_side, title )
def fieldHistory( play_side, difficulty, title ):
	return '%d.%d.%s' % ( play_side, difficulty, title )


CLEAR_STR = [ 'NO PLAY', 'FAILED', 'ASSIST CLEAR', 'EASY CLEAR', 'CLEAR', 'HARD CLEAR', 'EX HARD CLEAR', 'FULL COMBO' ]
CLEAR_STR_TO_NUM = { CLEAR_STR[x]: x for x in xrange(len(CLEAR_STR)) }

GRADE_STR = [ 'F', 'E', 'D', 'C', 'B', 'A', 'AA', 'AAA' ]
GRADE_STR_TO_NUM = { GRADE_STR[x]: x for x in xrange(len(GRADE_STR)) }

PLAYSIDE_STR = [ 'SP', 'DP' ]
PLAYSIDE_MAX = len(PLAYSIDE_STR)

DIFFICULTY_STR = [ 'N', 'H', 'A' ]
DIFFICULTY_MAX = len(DIFFICULTY_STR)

HISTORY_PROTOTYPE = { 'clear': CLEAR_STR_TO_NUM['NO PLAY'], 'grade': GRADE_STR_TO_NUM['F'], 'score': 0 }
def isHistoryUpgraded( before, after ):
	for type in HISTORY_PROTOTYPE.iterkeys():
		if before[ type ] < after[ type ]:
			return True
	return False
