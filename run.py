#!/bin/env python3

# Configure logging
import argparse
import csv
import datetime
import dateutil.parser
import logging
import os
import pathlib
import pprint
import pyexch.pyexch

# Hash to hold module level data
resources = {}

def get_args():
    if 'args' not in resources:
        constructor_args = {
            'formatter_class': argparse.RawDescriptionHelpFormatter,
            'description': 'triage duty scheduler',
            'epilog': '''
ENVIRONMENT VARIABLES:
    TRIAGE_CSVFILE: File containing tab separated data from spreadsheet
    TRIAGE_LOCATIONFILE: File with meeting location for exchange calendar event
    OAUTH_CONFIG_FILE: (see https://github.com/andylytical/pyexch)
    OAUTH_TOKEN_FILE: (see https://github.com/andylytical/pyexch)
    NETRC: (see https://github.com/andylytical/pyexch)
    PYEXCH_REGEX_JSON: (see https://github.com/andylytical/pyexch)
            '''
        }
        parser = argparse.ArgumentParser( **constructor_args )
        parser.add_argument( '-d', '--debug', action='store_true' )
        parser.add_argument( '-n', '--dryrun', action='store_true',
            help='Show what would be done but make no changes.')

        parser.add_argument( '--mktriage', action='store_true',
            help='Make Triage duty events from CSV file. Requires TRIAGE_CSVFILE or --csvfile')
        parser.add_argument( '--mkhandoff', action='store_true',
            help='Make triage handoff events using actual triage events in the next 90 days.')

        parser.add_argument( '-f', '--csvfile',
            help='Override TRIAGE_CSVFILE environment variable.' )
        parser.add_argument( '-l', '--locationfile',
            help='Override TRIAGE_LOCATIONFILE environment variable.' )

        mkhandoff_group = parser.add_argument_group( 'Make Handoff',
            'Optionally specify start, end dates for making handoff meetings.' )
        mkhandoff_group.add_argument( '--start', help='Start date for --mkhandoff (default: today).' ) 
        mkhandoff_group.add_argument( '--end', help='End date for --mkhandoff (default: start + 90 days).' )
        # defaults = {
        #     'start': datetime.date.today(),
        #     'end': datetime.date.today() + datetime.timedelta( days=90 ),
        # }
        # parser.set_defaults( **defaults )
        args = parser.parse_args()
        resources['args'] = args

        # set sane default for start
        if args.start:
            new_start = dateutil.parser.parse( args.start )
            args.start = new_start
        else:
            args.start = datetime.date.today()

        # set sane default for end
        if args.end:
            new_end = dateutil.parser.parse( args.end )
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


def get_csvfile():
    if 'csvfile' not in resources:
        csvfile = os.getenv( 'TRIAGE_CSVFILE', get_args().csvfile )
        if not csvfile:
            raise UserWarning( 'Missing csvfile. Use --csvfile or TRIAGE_CSVFILE' )
        resources['csvfile'] = csvfile
    return resources['csvfile']


def get_triage_location():
    if 'triage_location' not in resources:
        l_file = os.getenv( 'TRIAGE_LOCATIONFILE', get_args().locationfile )
        if not l_file:
            raise UserWarning( 'Missing location file. Use --locationfile or TRIAGE_LOCATIONFILE' )
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

    args = get_args()
    if args.mktriage:
        csvfile = get_csvfile() #will fail if csvfile is not provided
        logging.debug( f"CSV file: '{csvfile}'" )
    if args.mkhandoff:
        logging.debug( f"MKHANDOFF" )


def parse_csv_input():
    p = pathlib.Path( get_csvfile() )
    with p.open() as f:
        csv_data = csv.reader( f, dialect='excel-tab' )
        triage_raw_data = {}
        for row in csv_data:
            date = dateutil.parser.parse(row[0])
            members = []
            emails = []
            for elem in row[1:]:
                if '@' in elem:
                    emails.append( elem )
                else:
                    members.append( elem )
            triage_raw_data[date] = { 'emails': emails, 'members': members }
    logging.debug( pprint.pformat( triage_raw_data ) )
    return triage_raw_data


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
    triage_start_date = min( mtg_data.keys() )
    # add one work day to end_date for benefit of handoff events
    triage_end_date = max( mtg_data.keys() )
    existing_events = get_existing_events(
        start = triage_start_date,
        end = triage_end_date,
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
        px = get_pyexch()
        logging.info( f'Making new TRIAGE event for date "{date}"' )
        args = get_args()
        if args.dryrun:
            logging.info( f'DRYRUN: Subj:"{subj}" Attendees:"{emails}"' )
        else:
            px.new_all_day_event( 
                date = date, 
                subject = subj,
                attendees = emails,
                location = get_triage_location(),
                categories = get_triage_categories(),
                free = True
            )


def create_handoff_meetings():
    args = get_args()

    # Get all existing TRIAGE & HANDOFF events from Exchange calendar
    existing_events = get_existing_events(
        start = args.start,
        end = args.end
    )
    # for edate, types in existing_events.items():
    #     for etype, event in types.items():
    #         logging.debug( f'{event.start} {event.type} {event.subject}' )

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
        handoff_date = next_date
        handoff_members = curr_members + next_members
        logging.debug( f'Collected handoff data: {handoff_date} {handoff_members}' )
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
    if existing_event:
        logging.info( f'Found existing HANDOFF event for date "{date}"' )
        #logging.debug( f'Existing Event: {existing_event}' )
        existing_members = sorted( [ a.mailbox.email_address for a in existing_event.raw_event.required_attendees ] )
        new_members = sorted( emails )
        if existing_members != new_members:
            logging.error( f'Member mismatch for HANDOFF date "{date}"' )
            logging.error( f'Existing: "{existing_members}"' )
            logging.error( f'New:      "{new_members}"' )
            raise SystemExit()
    else:
        subj = 'Triage Hand-Off'
        ev_start = datetime.datetime.combine( date,  datetime.time( hour=8, minute=45 ) )
        ev_end = datetime.datetime.combine( date, datetime.time( hour=9, minute=00 ) )
        logging.info( f'Making new HANDOFF event for date "{date}"' )
        args = get_args()
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


def run():
    validate_user_input()

    if args.mktriage:
        logging.info( f"Attempting to make triage meetings from CSV data" )
        triage_raw_data = parse_csv_input()
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
