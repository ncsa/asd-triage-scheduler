#!/bin/env python3

import argparse
import collections
import csv
import datetime
import logging
import os
import pandas
import pathlib
import pprint
import pyexch.pyexch

import libdate
import libgroup

# Hash to hold module level data
resources = {}

def get_args():
    if 'args' not in resources:
        constructor_args = {
            'formatter_class': argparse.RawTextHelpFormatter,
            'description': 'triage duty scheduler',
            'epilog': '''
ENVIRONMENT VARIABLES:
       TRIAGE_STAFF_FILE: Path to a file containing staff
                          File format is CSV with headers "name", "email", "type",
                          where "type" is one of 'staff', 'manager'.
    TRIAGE_LOCATION_FILE: Path to a file containing a URL for an online meeting
                          Used in the "location" field in newly created exchange calendar events
    TRIAGE_HOLIDAYS_FILE: Path to a file containing a list of holidays to be excluded from scheduling
                          File format is CSV with one header "date"
                          Dates should be in the form of YYYY-MM-DD
       OAUTH_CONFIG_FILE: Path to the pyexch config file
                          (See: https://github.com/andylytical/pyexch)
        OAUTH_TOKEN_FILE: Path to the pyexch token file
                          (See: https://github.com/andylytical/pyexch)
                   NETRC: Alternate path to a netrc file (default is ~/.netrc)
                          (See also: https://github.com/andylytical/pyexch)
       PYEXCH_REGEX_JSON: Alternate regex for matching existing calendar events
                          (See also: https://github.com/andylytical/pyexch)
            '''
        }
        parser = argparse.ArgumentParser( **constructor_args )
        parser.add_argument( '-d', '--debug', action='store_true' )
        parser.add_argument( '-n', '--dryrun', action='store_true',
                help='Show what would be done but make no changes.',
            )
        parser.add_argument( '--location_file',
                help='Override TRIAGE_LOCATION_FILE environment variable.',
            )
        parser.add_argument( '--start', help='Start date (default: today).' )
        parser.add_argument( '--end', help='End date (default: start + 90 days).' )

        # List
        g_list = parser.add_argument_group( title='List Duty Teams' )
        g_list.add_argument( '-l', '--list_teams', action='store_true',
                help=(
                    'List triage teams (built from staff list) with indexes.'
                    '\nUse one of these indices with --start_at.'
                    ),
            )
        # Make Triage Schedule
        g_triage = parser.add_argument_group(
                title='Make Triage Schedule',
                description=(
                    'For all work days from START to END,'
                    '\ncreate a triage event on the calendar,'
                    '\nassigned to the next duty team.'
                    '\nUse --list_teams to see the duty teams.'
                    '\nUse --start_at to start scheduling at a specific duty team.'
                    ),
            )
        g_triage.add_argument( '--mktriage', action='store_true',
                help='Make triage schedule.',
            )
        g_triage.add_argument( '--start_at',
                type=int,
                default=0,
                help=(
                    'Integer index into triage teams.'
                    '\nStart scheduling with the specified triage team.'
                    '\nUse the --list_teams option to see the team list and indices.'
                    ),
            )
        g_triage.add_argument( '--staff_file',
                help='Override TRIAGE_STAFF_FILE environment variable.',
            )

        # Make Handoff Events
        g_handoff = parser.add_argument_group(
                title='Make Handoff Events',
                description=(
                    'For all work days from START to END,'
                    '\nget existing Triage and Handoff events from the calendar,'
                    '\nmake new Handoff events where needed,'
                    '\nupdate existing Handoff events if the current members'
                    ' do not match the associated Triage event members.'
                    ),
            )
        g_handoff.add_argument( '--mkhandoff', action='store_true',
                help='Make or update triage handoff events using data from existing triage events.'
            )

        args = parser.parse_args()
        resources['args'] = args

        # set sane default for start
        if args.start:
            # new_start = dateutil.parser.parse( args.start )
            new_start = pandas.to_datetime( args.start )
            args.start = new_start
        else:
            args.start = datetime.date.today()

        # set sane default for end
        if args.end:
            # new_end = dateutil.parser.parse( args.end )
            new_end = pandas.to_datetime( args.end )
            args.end = new_end
        else:
            args.end = args.start + datetime.timedelta( days=90 )
    return resources['args']


def get_regex_map():
    return {
        "TRIAGE":"^Triage: ",
        "HANDOFF":"^Triage Hand-Off",
        }


def get_pyexch():
    if 'pyexch' not in resources:
        regex_map = get_regex_map()
        resources['pyexch'] = pyexch.pyexch.PyExch( regex_map = regex_map )
    return resources['pyexch']


def get_staff_data():
    ''' Read in the multi-purpose TRIAGE_STAFF_FILE
        Reads the CSV file and stores a dict
    '''
    key = 'staffdata'
    if key not in resources:
        filename = os.getenv( 'TRIAGE_STAFF_FILE', get_args().staff_file )
        if not filename:
            raise UserWarning( 'Missing staff file. Use --staff_file or TRIAGE_STAFF_FILE' )
        df = pandas.read_csv( filename, sep=None, engine='python' )
        resources[key] = { row.Name: row for row in df.itertuples() }
    return resources[key]


def get_staff():
    key = 'staff'
    if key not in resources:
        data = get_staff_data()
        resources[key] = { k: v for k,v in data.items() if v.Type == 'staff' }
    return resources[key]


def get_managers():
    key = 'managers'
    if key not in resources:
        data = get_staff_data()
        resources[key] = { k: v for k,v in data.items() if v.Type == 'manager' }
    return resources[key]


def get_MODs( date ):
    ''' Given a date, return the Managers On Duty for that day
    '''
    key = 'mod'
    if key not in resources:
        # Create a mapping of int-day-of-week -> Manager(s)
        daychars = ( 'M', 'T', 'W', 'R', 'F', )
        resources[key] = [ [], [], [], [], [], ]
        for name,mgr in get_managers().items():
            for dow_char in mgr.DOW:
                dow_int = daychars.index( dow_char )
                resources[ key ][ dow_int ].append( mgr )
    # do the lookup
    return resources[ key ][ date.weekday() ]



def get_triage_location():
    if 'triage_location' not in resources:
        l_file = os.getenv( 'TRIAGE_LOCATION_FILE', get_args().location_file )
        if not l_file:
            raise UserWarning( 'Missing location file. Use --location_file or TRIAGE_LOCATION_FILE' )
        p = pathlib.Path( l_file )
        location = p.read_text()
        if len(location) < 1:
            raise UserWarning( f"Unable to read location from file '{l_file}'" )
        resources['triage_location'] = location
    return resources['triage_location']


def get_triage_categories():
    if 'triage_categories' not in resources:
        resources['triage_categories'] = [ 'TicketMaster' ]
    return resources['triage_categories']


def get_existing_events( start=None, end=None ):
    ''' Get existing events between "start" and "end"
        start = datetime.date
        end = datetime.date
    '''
    logging.debug( pprint.pformat( [ start, end ] ) )
    px = get_pyexch()
    # ensure end is 11:59:59 PM
    existing_events = px.get_events_filtered(
        start = datetime.datetime( start.year, start.month, start.day ),
        end = datetime.datetime( end.year, end.month, end.day, hour=11, minute=59, second=59 ),
    )
    # logging.debug( f'Existing events: { [ (e.start, e.type, e.subject) for e in existing_events ] }' )
    for e in existing_events:
        logging.debug( f'{e.start} {e.type} {e.subject}' )
    # create hash of event dates & types
    current_events = {}
    for e in existing_events:
        dt = e.start.date()
        if dt not in current_events:
            current_events[dt] = {}
        current_events[dt][e.type] = e
    return current_events


def validate_user_input():
    ''' Check that all user input is present and valid
    '''
    location = get_triage_location() #will fail if location is not provided
    logging.debug( f"Triage Location: '{location}'" )

    get_staff() #will throw error in case of a problem

    args = get_args()
    if args.mktriage:
        logging.debug( f"MKTRIAGE" )
    if args.mkhandoff:
        logging.debug( f"MKHANDOFF" )


def create_triage_meetings( mtg_data ):
    ''' Use mtg_data to create meetings iff they don't already exist
        mtg_data = {
            datetime: {
                'emails': list of email addrs,
                'members': Names of attendees,
            }
        )
    '''
    # get existing events
    args = get_args()
    # triage_start_date = min( mtg_data.keys() )
    # add one work day to end_date for benefit of handoff events
    # triage_end_date = max( mtg_data.keys() )
    existing_events = get_existing_events(
        start = args.start,
        end = args.end,
    )
    # try to create events for dates from csv
    for dt, data in mtg_data.items():
        try:
            # dt is a datetime, use just the date component to match existing event
            ev = existing_events[dt.date()]['TRIAGE']
        except KeyError:
            ev = None
        create_or_update_triage_event(
            date = dt,
            emails = data['emails'],
            members = data['members'],
            existing_event = ev
        )


def create_or_update_triage_event( date, emails, members, existing_event=None ):
    ''' date = datetime for new event
        emails = list of email addresses
        members = list of names (used in the event title)
        existing_event = raw exchange event
    '''
    if existing_event:
        logging.info( f'Found existing TRIAGE event for date "{date}"' )
        #logging.debug( f'Existing Event: {existing_event}' )
    else:
        subj = f"Triage: {', '.join(members)}"
        logging.info( f'Making new TRIAGE event for date "{date}"' )
        args = get_args()
        if args.dryrun:
            logging.info( f'DRYRUN: Subj:"{subj}" Attendees:"{emails}"' )
        else:
            get_pyexch().new_all_day_event(
                date = date,
                subject = subj,
                attendees = emails,
                location = get_triage_location(),
                categories = get_triage_categories(),
                free = True,
            )


def create_handoff_meetings():
    args = get_args()

    # Get all existing TRIAGE & HANDOFF events from Exchange calendar
    existing_events = get_existing_events(
        start = args.start,
        end = args.end,
        )
    # For each day there is a TRIAGE event,
    #   get the required_attendees from both this and the next TRIAGE event
    #   Required_attendees=[ Attendee(), ...]
    #     where Attendee( mailbox=Mailbox(), ...)
    #     and where Mailbox( email_address='...', ...)
    #     thus, emails=[ a.mailbox.email_address for a in required_attendees ]
    triage_dates = sorted( existing_events.keys() )
    loop_end = len( triage_dates ) - 1
    for i in range( loop_end ):
        # get members from current triage event
        curr_date = triage_dates[i]
        curr_triage_event = existing_events[ curr_date ][ 'TRIAGE' ]
        curr_members = [ a.mailbox.email_address for a in curr_triage_event.raw_event.required_attendees ]
        logging.debug( f'{curr_triage_event.start} {curr_triage_event.subject}, {curr_members}' )
        # get members from next triage event
        try:
            next_date = triage_dates[i+1]
        except KeyError:
            logging.error( f'Next date not found, after curr_date: "{curr_date}"' )
            raise
        try:
            next_triage_event = existing_events[ next_date ][ 'TRIAGE' ]
            next_members = [ a.mailbox.email_address for a in next_triage_event.raw_event.required_attendees ]
        except KeyError:
            logging.error( f'No event data found after date: "{curr_date}"' )
            raise
        except TypeError:
            logging.error( f'Are there Required Attendees for the triage meeting on "{next_date}"?' )
            raise
        handoff_date = next_date
        managers_on_duty = [ m.Email for m in get_MODs( handoff_date ) ]
        logging.debug( f'MODs for {handoff_date}: {managers_on_duty}' )
        handoff_members = curr_members + next_members + managers_on_duty
        logging.debug( f'Calculated handoff data: {handoff_date} {handoff_members}' )
        # get existing handoff event, if it exists
        try:
            handoff_event = existing_events[ handoff_date ][ 'HANDOFF' ]
        except KeyError:
            handoff_event = None
        create_or_update_handoff_event( handoff_date, handoff_members, handoff_event )


def create_or_update_handoff_event( date, emails, existing_event=None ):
    ''' date = date of the event
        emails = list of email addresses
        existing_event = raw exchange event
    '''
    args = get_args()
    if existing_event:
        logging.info( f'Found existing HANDOFF event for date "{date}"' )
        #logging.debug( f'Existing Event: {existing_event}' )
        existing_members = sorted( [ a.mailbox.email_address for a in existing_event.raw_event.required_attendees ] )
        new_members = sorted( emails )
        if existing_members != new_members:
            logging.debug( f'Member mismatch for HANDOFF date "{date}"' )
            logging.debug( f'Existing: "{existing_members}"' )
            logging.debug( f'New:      "{new_members}"' )
            msg = f'Updated member list for HANDOFF date "{date}"'
            if args.dryrun:
                logging.info( f'DRYRUN: {msg}' )
            else:
                px = get_pyexch()
                px.update_event( existing_event.raw_event, attendees=new_members )
                logging.info( msg )
    else:
        subj = 'Triage Hand-Off'
        ev_start = datetime.datetime.combine( date,  datetime.time( hour=8, minute=45 ) )
        ev_end = datetime.datetime.combine( date, datetime.time( hour=9, minute=00 ) )
        logging.info( f'Making new HANDOFF event for date "{date}"' )
        if args.dryrun:
            logging.info( f'DRYRUN: Start:"{ev_start}" End:"{ev_end}" Subj:"{subj}" Attendees:"{emails}"' )
        else:
            px = get_pyexch()
            px.new_event(
                start = ev_start,
                end = ev_end,
                subject = subj,
                attendees = emails,
                location = get_triage_location(),
                categories = get_triage_categories()
            )


def mk_triage_schedule():
    ''' Create a dict with
        keys = date
        values = { 'emails': emails, 'members': members }
    '''
    staff = get_staff()
    triage_teams = get_triage_teams()
    logging.debug( f'starting length triage_teams: {len(triage_teams)}' )
    args = get_args()
    workdays = list( libdate.get_workdays( args.start, args.end ) )
    logging.debug( f'num workdays: {len(workdays)}' )
    # ensure triage_teams is longer than workdays
    scalar = int( len(workdays) / len(triage_teams) ) + 1
    logging.debug( f'Scalar: {scalar}' )
    triage_teams *= scalar
    logging.debug( f'new length triage_teams: {len(triage_teams)}' )
    # create the data
    triage_raw_data = {}
    for day in workdays:
        # TODO - add checks here to skip if someone is on PTO or has a PM
        members = triage_teams.popleft()
        emails = [ staff[x].Email for x in members ]
        triage_raw_data[day] = { 'emails': emails, 'members': members }
    return triage_raw_data


def get_triage_teams():
    staff = get_staff()
    teamlist = libgroup.fair_pairs( list( staff.keys() ) )
    teams = collections.deque( teamlist )
    teams.rotate( -(get_args().start_at) )
    return teams


def run():
    validate_user_input()

    args = get_args()

    if args.list_teams:
        # pprint.pprint( get_triage_teams() )
        for i,members in enumerate( get_triage_teams() ):
            print( f'{i: >2d} {members}' )
        return True

    if args.mktriage:
        logging.info( f"make triage schedule" )
        triage_raw_data = mk_triage_schedule()
        logging.debug( f'Triage raw data: {triage_raw_data}' )
        create_triage_meetings( triage_raw_data )

    if args.mkhandoff:
        create_handoff_meetings()


if __name__ == '__main__':
    log_lvl = logging.INFO
    args = get_args()
    fmt = '%(levelname)s %(message)s'
    if args.debug:
        log_lvl = logging.DEBUG
        fmt = '%(levelname)s [%(filename)s:%(funcName)s:%(lineno)s] %(message)s'
    logging.basicConfig( level=log_lvl, format=fmt )
    no_debug = [
        'exchangelib',
        'urllib3',
        'requests_oauthlib',
    ]
    for key in no_debug:
        logging.getLogger(key).setLevel(logging.CRITICAL)
    run()
