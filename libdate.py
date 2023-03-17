#!/bin/env python3

import datetime
import logging
import pprint
import pandas
import os


# Hash to hold module level data
resources = {}

def daynames():
    key = 'daynames'
    if key not in resources:
        resources[key] = ( 'Mon', 'Tue', 'Wed', 'Thr', 'Fri', 'Sat', 'Sun', )
    return resources[key]


def holidays():
    ''' list of datetime.date values for holidays
    '''
    key = 'holidays'
    if key not in resources:
        filename = os.environ['TRIAGE_HOLIDAYS_FILE']
        df = pandas.read_csv( filename ).squeeze( 'columns' )
        dti = pandas.to_datetime( df )
        # for d in dti:
        #     logging.debug( pprint.pformat( d ) )
        resources[key] = dti
    return resources[key]


def get_workdays( start, end ):
    ''' list of dates from start to end excluding weekends and holidays
        start: string or datetime object
        end: string or datetime object
    '''
    return pandas.bdate_range(
        start = start,
        end = end,
        freq = 'C',
        holidays = list( holidays() ),
        )


if __name__ == '__main__':
    start = datetime.date.today()
    end = start + datetime.timedelta( days=90 )
    for i,day in enumerate( get_workdays( start, end ) ):
        print( f'{i:02d} {day} {daynames()[day.weekday()]}' )
