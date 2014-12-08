#!/usr/bin/python3.4

import os
from os import path
import time
from datetime import datetime, timedelta
from itertools import groupby
from dropbox_helper import DropboxHelper
from functools import reduce
from TlogProcessor import TlogProcessor


syncRoot = "/Apps/FirstYear/sinkv2/Ilya__40A5E3EB-3FF1-4D9E-81B3-BA156E8BFDD0"
#syncRoot = "/Apps/FirstYear/sinkv2/Ilya_m4__EEF9E7D4-EAE4-4338-B1DA-D2B187097E7B"
#syncRoot = "/Apps/FirstYear/sinkv2/Bodes__B77BCBD9-9EAB-4CC1-A83B-4D64414E0F47"

# 9 stands for Tokyo Standard Time
timezone_bug = timedelta(hours=time.timezone/60/60+9)
sleeping_folder = '~/sleeping/static/'

def calc_average(days_data, n_last_days):

    sum_n_last_days = list(reduce(sum_of_two_days, days_data[-1*n_last_days:]))

    return [(s[0], timedelta(seconds=s[1].total_seconds()//n_last_days)) for s in sum_n_last_days]


def sum_of_two_days(acc, z):

    d1 = list(acc)
    d2 = list(z)

    z_sum = []
    for idx, val in enumerate(d1):
        d1_val = val[1] - d1[0][0]
        d2_val = d2[idx][1] - d2[0][0]
        z_sum.append(d1_val + d2_val)

    return list(zip([d[0] for d in d1], z_sum))


def graph_data_to_js(data):

    return [[str(d[0])[:-3], str(d[1])[:-3], str(d[0])[:-3]] for d in data]


def day_intervals_to_graph_data(one_day):

    # ds is the day we are talking about
    the_day = one_day[0]['From']

    # t0 is the start of that day
    t0 = the_day - timedelta(hours=the_day.hour, minutes=the_day.minute, seconds=the_day.second)

    # how many minutes to put on the graph
    # if the_day is today, end the graph at the current time:
    minutes_to_show = int(min(24*60, (datetime.now() + timezone_bug - t0).total_seconds()//60))
    #print(minutes_to_show)

    delta_mins = 10
    # delta-Xs we are going to use
    dxs = range(0, minutes_to_show, delta_mins)
    xs=[]
    ys = []
    for x in dxs:
        x_ = timedelta(minutes=x)

        # the gaps which are fully inside of the segment [0,x]
        full_gaps = [_ for _ in one_day if _['To'] <= t0 + x_]
        full_gaps_len = sum(_['Delta'] for _ in full_gaps)

        # the gaps which are partially covered by the segment [0,x]
        half_gaps = [_ for _ in one_day if _['From'] <= t0 + x_ < _['To']]

        if 0 == len(half_gaps):
            # simple case of no partial gaps:
            ys.append(timedelta(minutes=full_gaps_len))
        else:
            ys.append(timedelta(minutes=(full_gaps_len + (t0 + x_ - half_gaps[0]['From']).total_seconds()/60)))

        xs.append(x_)

    return list(zip(xs, ys))


def copy_data_from_dropbox(local):
    dh = DropboxHelper()

    remote = syncRoot

    dh.mirror_tlog_files(remote, local)

def load_sleeps_data(local):
    all_sleeps = []

    for root, subFolders, files in os.walk(os.path.expanduser(local)):
        for file in files:
            if file.endswith('.tlog'):
                all_sleeps.extend(TlogProcessor(path.join(root, file)).get_activity_logs('Sleep'))

    # group these by ObjectID, then take the very latest log for each ObjectID
    sleeps = []
    keys = []
    group_by_id = lambda s: s['ObjectID']
    for k, g in groupby(sorted(all_sleeps, key=group_by_id), group_by_id):
        sleeps.append(sorted(g, key=lambda _: _['Timestamp'], reverse=True)[0])
        keys.append(k)

    return sleeps, keys


def get_sleeps_in_window(sleeps, win_start, win_end):

    s = [(datetime.strptime(_['Time'], '%Y-%m-%d %H:%M:%S'), _['DurationMin']) for _ in sleeps]

    all_in_window = set([_ for _ in s if win_start <= _[0] <= win_end
                         and not 0 == _[1]
                         and _[0] + timedelta(minutes = _[1]) <= win_end])

    started_in_window = set([_ for _ in s if win_start <= _[0] <= win_end]) - all_in_window
    ended_in_window = set([_ for _ in s if 0 != _[1] and win_start <= _[0] + timedelta(minutes = _[1]) <= win_end]) - all_in_window

    assert len(started_in_window) <= 1
    assert len(ended_in_window) <= 1

    # cut these at the windows start/end - being careful with the ongoing sleep
    started_in_window = [(_[0], int((win_end - _[0]).total_seconds()/60)) for _ in list(started_in_window)]
    ended_in_window = [(win_start, int(_[1] - (win_start - _[0]).total_seconds()/60)) for _ in list(ended_in_window)]

    # merge the lists
    started_in_window.extend(ended_in_window)
    started_in_window.extend(list(all_in_window))

    return reduce(lambda x, y: x + y, [_[1] for _ in started_in_window])


def last_24_hours_ending(sleeps, end_time):

    day_start = end_time - timedelta(hours=end_time.hour, minutes=end_time.minute, seconds=end_time.second)
    graph_data = []

    for win_end_sec in range(0,int((end_time - day_start).total_seconds()), 60*10):
    #debug
    #for win_end_sec in [int((end_time - day_start).total_seconds())]:
        # find the sleeps in the last 24 hours
        win_end = day_start + timedelta(seconds=win_end_sec) + timezone_bug
        win_start = win_end - timedelta(hours=24)

        mins_slept = get_sleeps_in_window(sleeps, win_start, win_end)
        mins_x = win_end_sec//60
        graph_data.append("['{0:02}:{1:02}','{2:02}:{3:02}']".format(mins_x//60, mins_x % 60, mins_slept//60, mins_slept % 60))

    return '[%s]' % ",".join(graph_data)


def main(skip_copy=False):

    local = r"~/FirstYear/cache"

    # bring the logs locally first
    if not skip_copy:
        copy_data_from_dropbox(local)

    # all the sleeping information
    (sleeps, keys) = load_sleeps_data(local)
    print('Loaded %i unique sleeps' % len(keys))

    #print(json.dumps(sleeps, sort_keys=True, indent=4, separators=(',', ': ')))

    # group by time into days: "Time": "2014-10-29 06:55:38",
    # sleep_intervals_grouped is a list of arrays of sleeping intervals
    # one array per each day when the sleep started
    daily_intervals = []
    group_by_day = lambda s: s['Time'][:10]
    for k, g in groupby(sorted(sleeps, key=group_by_day), group_by_day):
        daily_intervals.append([{'From': datetime.strptime(x['Time'], '%Y-%m-%d %H:%M:%S'),
                                         'To': datetime.strptime(x['Time'], '%Y-%m-%d %H:%M:%S')
                                               + timedelta(minutes=x['DurationMin']),
                                         'Delta': x['DurationMin']}
                     for x in sorted(g, key=lambda _: _['Time'])])

    # extend the night into the next day -
    # take the last sleep of the each day, these are "night sleeps"
    nights = [_[-1:][0] for _ in daily_intervals if _[-1:][0]['From'].day != _[-1:][0]['To']]
    for night in nights:
        # cut the hours/mins/secs
        midnight = datetime.combine(night['To'].date(), datetime.min.time())
        new_interval = {'From': midnight,
                        'To': night['To'],
                        'Delta': (night['To']-midnight).seconds//60}

        # append the interval to the next day -
        next_day = [_ for _ in daily_intervals if _[0]['From'].date() == midnight.date()]

        if 0 == len(next_day):
            # no sleep that starts on the next_day is registered - probably didn't fall asleep yet on that day
            print('No proper day for', new_interval)
            daily_intervals.append([   new_interval])
        else:
            # the interval might overlap - fix it if needed
            if next_day[0][0]['From'] < new_interval['To']:
                new_interval['To'] = next_day[0][0]['From']
                new_interval['Delta'] = (next_day[0][0]['From'] - new_interval['From']).total_seconds()//60

            next_day[0].insert(0, new_interval)

    print('Days covered: ', len(daily_intervals))
    if 0 == len(daily_intervals):
        return

    last_sleep = daily_intervals[-1:][0][-1:][0]

    # if the last sleep is with zero duration - meaning it's still going on - fix it to end now
    if 0 == last_sleep['Delta']:
        last_sleep['To'] = datetime.now() + timezone_bug
        last_sleep['Delta'] = (last_sleep['To']-last_sleep['From']).total_seconds()//60

    print(daily_intervals[-1:][0][-1:])
    #all_sleeps.pop()

    #print(days)
    #print(json.dumps(days, sort_keys=True, indent=4, separators=(',', ': ')))

    today_color = 0xff4466
    yesterday_color = 0x6644ff
    default_color = 0xcccccc

    i = 0
    lines = ''
    colors = ''

    if False:
        with open(os.path.expanduser(sleeping_folder + 'all_lines.js'), 'w') as f:
            for day in daily_intervals:

                day_data = day_intervals_to_graph_data(day)

                f.write('line%i=' % i + str(list(graph_data_to_js(day_data))) + ';\n')

                color_width = (default_color - i * 0x010101 * 3, 3) if i < len(daily_intervals)-2 else ((today_color, 5) if not i + 2 == len(daily_intervals) else (yesterday_color, 5))
                colors += "{color: '#%X', lineWidth: %i}, " % color_width

                lines += 'line%i,' % i

                i += 1

            f.write('colors=[%s]\n' % colors)
            f.write('lines=[%s]\n' % lines)

    with open(os.path.expanduser(sleeping_folder + 'lines.js'), 'w') as f:

        days_data = list(map(day_intervals_to_graph_data, daily_intervals))

        f.write('average_last_4weeks=' + str(graph_data_to_js(calc_average(days_data[:-1], 4*7))) + ';\n')
        f.write('average_last_week=' + str(graph_data_to_js(calc_average(days_data[:-1], 7))) + ';\n')

        f.write('ototoi=' + str(list(graph_data_to_js(days_data[-3:][0]))) + ';\n')
        f.write('yesterday=' + str(list(graph_data_to_js(days_data[-2:][0]))) + ';\n')
        f.write('today=' + str(list(graph_data_to_js(days_data[-1:][0]))) + ';\n')

        print('days_data[-1:]', days_data[-1:])

        # find the best/words days
        ttl_sleep_time = lambda s: s[len(s)-1][1]
        longest_day = sorted(days_data, key=ttl_sleep_time, reverse=True)[0]
        f.write('longest_day={0};\n'.format(list(graph_data_to_js(longest_day))))

        now_fixed = datetime.now() + timezone_bug
        f.write('prev24={0};\n'.format(last_24_hours_ending(sleeps, now_fixed-timedelta(hours=24))))
        f.write('last24={0};\n\n'.format(last_24_hours_ending(sleeps, now_fixed)))

        f.write("colors=[\n\
                        {color: '#DDDDDD', lineWidth: 10, label:'Last 4 weeks avg.'},\n\
                        {color: '#DDDDFF', lineWidth: 10, label:'Last week avg.'},\n\
                        {color: '#000000', lineWidth: 2, label:'Record day'},\n\
                        {color: '#66FF44', lineWidth: 5, label:'Day before yesterday'},\n\
                        {color: '#4466FF', lineWidth: 5, label:'Yesterday'},\n\
                        {color: '#4466FF', lineWidth: 2, label:'Prev 24h'},\n\
                        {color: '#FF4466', lineWidth: 5, label:'Today'},\n\
                        {color: '#FF4466', lineWidth: 2, label:'Last 24h'},\n\
                        ];\n")

        f.write('lines=[average_last_4weeks, average_last_week, longest_day, ototoi, yesterday, prev24, today, last24];\n')

    import webbrowser
    webbrowser.open('file:///' + os.path.expanduser(sleeping_folder + 'jqPlot.html'))

main(False)

#strange_file = r"C:\Users\maxlevy\Dropbox\Apps\FirstYear\sinkv2\Ilya__40A5E3EB-3FF1-4D9E-81B3-BA156E8BFDD0\4F9DA8D8-9B8C-4787-A30D-20A9D99BD4A1__903C2920-0025-4D02-854D-9D152B4B38F7\TransactionLog0.tlog"
#tl = TlogProcessor(strange_file)

#print( tl.get_activity_logs('Sleep') )