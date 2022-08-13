#!/bin/env python3

# Configure logging
import argparse
import csv
import datetime
import dateutil.parser
import logging
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
    TRIAGE_LOCATION: Zoom link to use for the location in exchange calendar event.
    OAUTH_CONFIG_FILE: (see https://github.com/andylytical/pyexch)
    OAUTH_TOKEN_FILE: (see https://github.com/andylytical/pyexch)
    NETRC: (see https://github.com/andylytical/pyexch)
    PYEXCH_REGEX_JSON: (see https://github.com/andylytical/pyexch)
    '''
        }
        parser = argparse.ArgumentParser()
        parser.add_argument( '-d', '--debug', action='store_true' )
        parser.add_argument( '-f', '--csvfile' )
        parser.add_argument( '-l', '--location',
            help='Zoom link to use for the location in exchange calendar event.' )
        defaults = {
            'debug': False,
            'csvfile': 'csv',
        }
        parser.set_defaults( **defaults )
        args = parser.parse_args()
        resources['args'] = args
    return resources['args']


def get_regex_map():
    return {
        "TRIAGE":"^Triage: ",
        "SHIFTCHANGE":"^Triage Shift Change: ",
        }


def get_pyexch():
    if 'pyexch' not in resources:
        regex_map = get_regex_map()
        resources['pyexch'] = pyexch.pyexch.PyExch( regex_map = regex_map )
    return resources['pyexch']


def get_triage_location():
    if 'triage_location' not in resources:
        location = None
        args = get_args()
        try:
            location = args.location
        except AttributeError as e:
            location = os.getenv( 'TRIAGE_LOCATION', None )
        if not location:
            raise UserWarning( 'Missing Triage Location. Use --location or TRIAGE_LOCATION' )
        resources['triage_location'] = location
    return resources['triage_location']


def get_triage_categories():
    if 'triage_categories' not in resources:
        resources['triage_categories'] = [ 'TicketMaster' ]
    return resources['triage_categories']


def parse_csv_input():
    args= get_args()
    p = pathlib.Path( args.csvfile )
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


def get_existing_events( start, end ):
    ''' px = PyExch instance, already logged in
        start = datetime.date OR datetime.datetime
        end = datetime.date OR datetime.datetime
        Get existing events between "start" and "end"
    '''
    logging.debug( pprint.pformat( [ start, end ] ) )
    px = get_pyexch()
    # convert end to a datetime at the end of the day 11:59:59 PM
    existing_events = px.get_events_filtered(
        start = start,
        end = end + datetime.timedelta( seconds=86399 ),
    )
    # pprint.pprint( existing_events )
    logging.debug( f'Existing events: { [ (e.start, e.type, e.subject) for e in existing_events ] }' )
    # create hash of event dates & types
    current_events = {}
    for e in existing_events:
        dt = e.start.date()
        if dt not in current_events:
            current_events[dt] = {}
        current_events[dt][e.type] = e
    return current_events


def create_or_update_triage_event( date, emails, members, existing_event:None):
    ''' date = datetime for new event
        attendees = list of email addresses
        existing_event = raw exchange event
    '''
    if existing_event:
        #logging.info( f'Existing TRIAGE event {pprint.pprint(ev)}' )
        logging.info( f'Existing TRIAGE event for date "{date}"' )
        logging.debug( f'Existing Event: {existing_event}' )
    else:
        px = get_pyexch()
        logging.info( f'Making new TRIAGE event for date "{date}"' )
        px.new_all_day_event( 
            date = date, 
            subject = f"Triage: {', '.join(members)}",
            attendees = emails,
            location = get_triage_location(),
            categories = get_triage_categories(),
            free = True
        )


def run():
    triage_raw_data = parse_csv_input()

#    authenticate()

    # (1) create all triage meetings
    create_triage_meetings( triage_raw_data )

    # (2) create / update SHIFTCHANGE events
    # Get all existing TRIAGE events
    # Extract attendees required_attendees=[ Attendee(), ...]
    #   where Attendee( mailbox=Mailbox(), ...)
    #   and where Mailbox( email_address='...', ...)
    #   thus, emails=[ a.mailbox.email_address for a in required_attendees ]


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
    ]
    for key in no_debug:
        logging.getLogger(key).setLevel(logging.CRITICAL)
    run()
