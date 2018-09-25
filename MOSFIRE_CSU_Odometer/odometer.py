#!/usr/env/python

## Import General Tools
import sys
import os
from datetime import datetime as dt
import re
from glob import glob
import numpy as np
import json

import matplotlib as mpl
mpl.use('Agg')
from matplotlib import pyplot as plt

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def main():
    bars = [i for i in range(1,93)]

    log_files = sorted(glob('/h/instrlogs/mosfire/*/CSU.log*'))
    log_files.append('/sdata1300/syslogs/CSU.log')
    filedates = {}
    
    odometers = {}
    moves = {}
    
    for i,log_file in enumerate(log_files):
        log_path, log_filename = os.path.split(log_file)
        if os.path.exists(os.path.join(log_path, 'odometer.json')):
            print(f"Loading results from {os.path.join(log_path, 'odometer.json')}")
            with open(os.path.join(log_path, 'odometer.json'), 'r') as FO:
                result = json.load(FO)
            odometers[log_file] = result['odometer']
            moves[log_file] = result['nmoves']
        else:
            nmoves = [0 for i in range(1,93)]
            mileage = [0 for i in range(1,93)]

            month_decimal = 0
            year_iteration = 0
            last_pos = {}
            for bar in bars:
                last_pos[bar] = 0
            try:
                print(f'Reading {log_file}')
                with open(log_file, 'r') as FO:
                    contents = FO.readlines()
                print(f'  Analyzing {len(contents):,} lines')
                file_start = None
                file_end = None
                last_line = ''
                for line in contents:
                    match = re.search(f'Record=<(\d\d),', line)
                    if match is not None:
                        bar = int(match.group(1))
                        md = re.match('(\w+)\s+(\d+)\s+(\d+:\d+:\d+).+', line)
                        if md is not None:
                            date_string = f"{md.group(1)} {int(md.group(2)):02d} {md.group(3)}"
                            date = dt.strptime(date_string, '%b %d %H:%M:%S')

                            if date.month < month_decimal:
                                print(f'  Iterating year: {month_decimal} {date.month}')
                                year_iteration +=1
                            month_decimal = date.month


                            if file_start is None:
                                file_start = date
                                ## Look for overlap
                                for compfile in filedates.keys():
                                    fdc = filedates[compfile]
                                    if (file_start >= fdc[0]) and (file_start <= fdc[1]):
                                        print(f'WARNING:  Found Overlap with {compfile}')
                                        print(file_start)
                                        print(compfile, filedates[compfile])
                                        sys.exit(0)
                            else:
                                file_end = date
                            barpos = float(line.strip('\n').split(',')[2])
                            if last_pos[bar] != 0:
                                delta = last_pos[bar] - barpos
                                if abs(delta) > 0:
                                    nmoves[bar-1] += 1
                                    mileage[bar-1] += abs(delta)
                            last_pos[bar] = barpos
                            last_line = line
                        else:
                            print(line)
                assert file_start is not None
                assert file_end is not None

                folder = os.path.split(os.path.split(log_file)[0])[1]
                try:
                    folderdt = dt.strptime(folder, '%Y%m%d')
                except ValueError:
                    year = dt.utcnow().year

                file_end = dt.strptime(file_end.strftime(f'{folderdt.year} %m %d %H:%M:%S'), '%Y %m %d %H:%M:%S')
                file_start = dt.strptime(file_start.strftime(f'{folderdt.year-year_iteration} %m %d %H:%M:%S'), '%Y %m %d %H:%M:%S')

                timespan = file_end - file_start
                filedates[log_file] = [file_start, file_end]
                if i > 0:
                    gap = file_start - filedates[last_file][1]
                    print(f'  Gap of {gap} between start of this and end of last log file')
                last_file = log_file
                print(f'  File covers: {file_start} to {file_end} ({timespan})')
            
                odometers[log_file] = mileage
                moves[log_file] = nmoves
            
                ## Save Result
                result = {'odometer': mileage, 'nmoves': nmoves}
                with open(os.path.join(log_path, 'odometer.json'), 'w') as FO:
                    json.dump(result, FO)
            except UnicodeDecodeError:
                print(f'  Unable to read {log_file}')


    ## Sum All log file results
    nmoves = np.array([0 for i in range(1,93)])
    mileage = np.array([0 for i in range(1,93)])
    for i,log_file in enumerate(log_files):
        nmoves += np.array(moves[log_file])
        mileage += np.array(odometers[log_file])

    bars = np.array(bars)
    mileage /= 1000
    slits = np.array([int((b+1)/2) for b in bars])
    left = np.array([(b%2 != 0) for b in bars])
    right = np.array([(b%2 == 0) for b in bars])

    maxmileage = 0
    maxmoves = 0
    for s in set(slits):
        ids = np.where(slits == s)
        slitmileage = np.sum(mileage[ids])
        maxmileage = max([maxmileage, slitmileage])
        slitmoves = np.sum(nmoves[ids])
        maxmoves = max([maxmoves, slitmoves])

    plt.ioff()

    plt.figure(figsize=(16,10))
    plt.title('Bar Mileage')
    plt.bar(slits[left], mileage[left],
            width=0.9, align='center', color='b')
    plt.bar(slits[right], -mileage[right], bottom=maxmileage,
            width=0.9, align='center', color='g')
    plt.xlim(0,47)
    plt.xlabel("Slit Number")
    plt.ylabel("Mileage (m)")
    plt.grid()
    plt.savefig('CSU_Bar_Mileage.png')

    plt.figure(figsize=(16,10))
    plt.title('Number of Bar Moves')
    plt.bar(slits[left], nmoves[left],
            width=0.9, align='center', color='b')
    plt.bar(slits[right], -nmoves[right], bottom=maxmoves,
            width=0.9, align='center', color='g')
    plt.xlim(0,47)
    plt.xlabel("Slit Number")
    plt.ylabel("N Moves")
    plt.grid()
    plt.savefig('CSU_Bar_Moves.png')


if __name__ == '__main__':
    main()
