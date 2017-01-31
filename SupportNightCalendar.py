#!/usr/env/python

from __future__ import division, print_function

## Import General Tools
import sys
import os
import argparse

import numpy as np
from astropy.table import Table
from astropy import units as u
from astropy import coordinates as c
from astropy.time import Time, TimezoneInfo
from astroplan import Observer
from datetime import datetime as dt
from datetime import timedelta as tdelta

class ParseError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


##-------------------------------------------------------------------------
## ICS File Object
##-------------------------------------------------------------------------
class ICSFile(object):
    '''
    Class to represent an ICS calendar file.
    '''
    def __init__(self, filename):
        self.file = filename
        self.lines = ['BEGIN:VCALENDAR\n',
                      'PRODID:-//hacksw/handcal//NONSGML v1.0//EN\n',
                      '\n']


    def add_event(self, title, starttime, endtime, description, verbose=False):
        assert type(title) is str
        assert type(starttime) in [dt, str]
        assert type(endtime) in [dt, str]
        assert type(description) in [list, str]
        now = dt.utcnow()
        try:
            starttime = starttime.strftime('%Y%m%dT%H%M%S')
        except:
            pass
        try:
            endtime = endtime.strftime('%Y%m%dT%H%M%S')
        except:
            pass
        if verbose:
            print('{} {}'.format(starttime[0:8], title))
        if type(description) is list:
            description = '\\n'.join(description)
        new_lines = ['BEGIN:VEVENT\n',
                     'UID:{}@mycalendar.com\n'.format(now.strftime('%Y%m%dT%H%M%S.%fZ')),
                     'DTSTAMP:{}\n'.format(now.strftime('%Y%m%dT%H%M%SZ')),
                     'DTSTART;TZID=Pacific/Honolulu:{}\n'.format(starttime),
                     'DTEND;TZID=Pacific/Honolulu:{}\n'.format(endtime),
                     'SUMMARY:{}\n'.format(title),
                     'DESCRIPTION: {}\n'.format(description),
                     'END:VEVENT\n',
                     '\n',
                     ]
        self.lines.extend(new_lines)


    def write(self):
        self.lines.append('END:VCALENDAR\n')
        if os.path.exists(self.file): os.remove(self.file)
        with open(self.file, 'w') as FO:
            for line in self.lines:
                FO.write(line)
            



##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():

    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    parser = argparse.ArgumentParser(
             description="Program description.")
    ## add arguments
    parser.add_argument('--sasched',
        type=str, dest="sasched",  default='sasched.csv',
        help="The csv file of the SA's duty nights.")
    parser.add_argument('-t', '--telsched',
        type=str, dest="telsched", default='telsched.csv',
        help="The csv file of the telescope schedule.")
    parser.add_argument('-s', '--start',
        type=str, dest="start",
        help="Start time for calendar entry in HHMMSS or HHMM 24 hour format.")
    parser.add_argument('-e', '--end',
        type=str, dest="end", default='2300',
        help="End time for calendar entry in HHMMSS or HHMM 24 hour format.")
    args = parser.parse_args()

    if args.start:
        if len(args.start) == 4:
            args.start = args.start + '00'
        elif len(args.start) == 6:
            args.start = args.start
        else:
            raise ParseError('Could not parse start time: "{}"'.format(args.start))

    if args.end:
        if len(args.end) == 4:
            args.end = args.end + '00'
        elif len(args.end) == 6:
            args.end = args.end
        else:
            raise ParseError('Could not parse end time: "{}"'.format(args.end))


    ##-------------------------------------------------------------------------
    ## Read in Telescope Schedule and SA Support Schedule
    ##-------------------------------------------------------------------------
    telsched = Table.read(args.telsched, format='ascii.csv', guess=False)
    assert '#' in telsched.keys()
    assert 'Date' in telsched.keys()
    assert 'Instrument' in telsched.keys()
    assert 'Principal' in telsched.keys()
    assert 'Observers' in telsched.keys()
    assert 'Location' in telsched.keys()
    assert 'InstrAcc' in telsched.keys()
    sasched = Table.read(args.sasched, format='ascii.csv', guess=False)
    keys = sasched.keys()
    assert '#' in keys
    assert 'Date' in keys
    assert len(keys) == 3
    saname = keys.pop(-1)

    sasched = sasched[~sasched[saname].mask]
    print('Processing {:d} nights in SA schedule.'.format(len(sasched)))
    type = {'K1': 'Support',
            'K1T': 'Training',
            'K1oc': 'On Call',
            'K2': 'Support',
            'K2T': 'Training',
            'K2oc': 'On Call',
            }

    obs = Observer.at_site('Keck')
    HST = TimezoneInfo(utc_offset=-10*u.hour, tzname='HST')
    ## Calculate Elevation of True Horizon from Maunakea
    ##   Formulas from https://en.wikipedia.org/wiki/Horizon
    h = 4.2*u.km
    R = (1.0*u.earthRad).to(u.km)
    d = np.sqrt(h*(2*R+h))
    phi = (np.arccos((d/R).value)*u.radian).to(u.deg)
    MKhorizon = phi - 90*u.deg

    min_before_sunset = 30.
    min_after_sunrise = 30.

    ##-------------------------------------------------------------------------
    ## Create Output iCal File
    ##-------------------------------------------------------------------------
    ical_file = ICSFile('Nights.ics')

    for night in sasched:
        date = night['Date']
        telstr = night[saname]
        print('  {} {}'.format(night['Date'], telstr))
        time = Time('{} 23:00:00'.format(date))

        sunset = obs.sun_set_time(time, which='next', horizon=MKhorizon)
        dusk_nauti = obs.sun_set_time(time, which='next', horizon=-12*u.deg)
        sunrise = obs.sun_rise_time(time, which='next', horizon=MKhorizon)
        dawn_nauti = obs.sun_rise_time(time, which='next', horizon=-12*u.deg)

#         if obs.moon_altaz(sunset).alt > 0*u.deg:
#             moon_set = obs.moon_set_time(sunset, which='next',
#                                          horizon=MKhorizon)
#             print('Moon Set at {}'.format(moon_set))
#         else:
#             moon_rise = obs.moon_rise_time(sunset, which='next',
#                                            horizon=MKhorizon)
#             print('Moon Rise at {}'.format(moon_rise))

        if args.start:
            calend = '{}T{}'.format(date.replace('-', ''), args.start)
        else:
            calstart = (sunset.to_datetime(timezone=HST)\
                        - tdelta(0,min_before_sunset*60.)).strftime('%Y%m%dT%H%M%S')
        if args.end:
            calend = '{}T{}'.format(date.replace('-', ''), args.end)
        else:
            calend = (sunrise.to_datetime(timezone=HST)\
                      + tdelta(0,min_after_sunrise*60.)).strftime('%Y%m%dT%H%M%S')

        tel = int(night[saname][1:2])
        entry = telsched[(telsched['Date'] == date) & (telsched['TelNr'] == tel)]
        assert len(entry) == 1
        title = '{} {} ({})'.format(entry['Instrument'][0],
                                             type[telstr],
                                             entry['Location'][0])
        description = ['Sunset @ {}'.format(
                           sunset.to_datetime(timezone=HST).strftime('%H:%M') ),
                       '12 deg Twilight @ {}'.format(
                           dusk_nauti.to_datetime(timezone=HST).strftime('%H:%M') ),
                       '12 deg Twilight @ {}'.format(
                           dawn_nauti.to_datetime(timezone=HST).strftime('%H:%M') ),
                       'Sunrise @ {}'.format(
                           sunrise.to_datetime(timezone=HST).strftime('%H:%M') ),
                       'PI: {}'.format(entry['Principal'][0]),
                       'Observers: {}'.format(entry['Observers'][0]),
                       'Location: {}'.format(entry['Location'][0]),
                       'Account: {}'.format(entry['InstrAcc'][0]),
                       ]
                           
        ical_file.add_event(title, calstart, calend, description)

    ical_file.write()


if __name__ == '__main__':
    main()


