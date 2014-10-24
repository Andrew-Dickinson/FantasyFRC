#!/usr/bin/python
# -*- coding: utf-8 -*-

UNDETERMINED = 0
DIDNTQUALIFY = 1
QUARTERFINALIST = 2
SEMIFINALIST = 3
FINALIST = 4
WINNER = 5

convert_TBA_level_to_progress = {'qm': DIDNTQUALIFY,
                                 'ef': DIDNTQUALIFY,
                                 'qf': QUARTERFINALIST,
                                 'sf': SEMIFINALIST,
                                 'f': FINALIST}