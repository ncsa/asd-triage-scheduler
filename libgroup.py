#!/bin/env python3

import itertools
import pprint
import logging

def fair_pairs( members ):
    ''' Split members list in half, create all pairings such that
        individual recurrences are as far apart as possible
    '''
    # first half and second half, if count is odd, first half is shorter
    L1 = members[:len(members)//2]
    L2 = members[len(members)//2:]
    L1_size = len(L1)
    L2_size = len(L2)
    scalar = int( L1_size == L2_size )

    fairlist = []
    loopcount = -1
    for counter in range( L1_size * L2_size ):
        if counter % L1_size == 0:
            loopcount = loopcount + 1
            logging.debug( f'loopcount={loopcount}' )
        i = ( counter + (loopcount * scalar) ) % L1_size
        j = counter % L2_size
        logging.debug( f'{counter:02d}  ({i}, {j}) .. {L1[i] , L2[j]}' )
        fairlist.append( ( L1[i], L2[j] ) )
    return fairlist

if __name__ == '__main__':

    staff = (
        'A',
        'B',
        'C',
        'D',
        'E',
        'F',
        'G',
        'H',
        'I',
    )
    duty_pairs = fair_pairs( staff )
    for i, elem in enumerate( duty_pairs ):
        print( f'{i:02d} {elem}' )
