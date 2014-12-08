# http://mark-dot-net.blogspot.jp/2014/03/python-equivalents-of-linq-methods.html
# https://docs.python.org/2/library/itertools.html#recipes

import os
import json
import ntpath

from datetime import timedelta, datetime

# https://github.com/wooster/biplist
from biplist import readPlist
from plistlib import dump


def timestamp_2datetime(ts, t0):
    return (t0 + timedelta(seconds=ts, hours=9)).strftime('%Y-%m-%d %H:%M:%S')


def log_timestamp_2datetime(ts):
    return timestamp_2datetime(ts, datetime(2001, 1, 1))


def db_timestamp_2datetime(ts):
    return timestamp_2datetime(ts, datetime(1970, 1, 1))


class TlogProcessor:
    def __init__(self, tlog):
        self.tlog = tlog

        self.plist = readPlist(self.tlog)

        self.bigArray = self.plist[b'$objects']
        pos = 0
        for idx, itm in enumerate(self.bigArray):

            if isinstance(itm, dict):
                itm[b'pos'] = pos
            else:
                self.bigArray[idx] = {b'pos': pos, b'NS.string': itm}
                self.plist[b'$objects'][idx] = {b'pos': pos, b'NS.string': itm}

            pos += 1

        self.deleted_obj_ids = self.load_deleted_activities()

        # self.tlog2xml()

    def tlog2xml(self, xml_file=None):

        """

        :rtype : object
        """
        filename = self.tlog + '.xml' if not xml_file else xml_file

        with open(filename, 'wb') as fp:
            dump(self.plist, fp)

        return filename

    def load_deleted_activities(self):
        # such an element (OpCode=2) indicates deletion of an activity:
        delete_command = "\
        <dict>\
            <key>$class</key>\
            <integer>20</integer>\
            <key>OpCode</key>\
            <integer>2</integer>\
            <key>SyncID</key>\
            <integer>29</integer>\
            <key>TransactionObject</key>\
            <integer>378</integer>\
            <key>pos</key>\
            <integer>377</integer>\
        </dict>\
        "
        # the class is defined as follows:
        delete_class = "\
            <dict>\
                <key>$classes</key>\
                <array>\
                    <string>TransactionLogItemV2</string>\
                    <string>NSObject</string>\
                </array>\
                <key>$classname</key>\
                <string>TransactionLogItemV2</string>\
                <key>pos</key>\
                <integer>20</integer>\
            </dict>\
        "
        x_log_id = next(iter([x for x in self.bigArray if b'$classname' in x
                              and 'TransactionLogItemV2'.encode('ascii') == x[b'$classname']]),
                        {b'pos': -1})[b'pos']

        # now find all the activities which use that $classname and have OpCode=2:
        delete_commands = [_ for _ in self.bigArray if
                           b'$class' in _
                           and x_log_id == _[b'$class']
                           and b'OpCode' in _
                           and 2 == _[b'OpCode']
        ]

        return list(map(lambda _: self.bigArray[self.bigArray[_][b'ObjectID']][b'NS.string'].decode('ascii'),
                        [_[b'TransactionObject'] for _ in delete_commands]))

    def get_activity_logs(self, activity):

        # find the joyPos, pick 0 if none:
        """
        :rtype : list of activities
        :param activity: name of the activity to filter
        :return: 
        """

        # check the cache file - if it's up to date use it, otherwise parse the log
        dump_txt = os.path.expanduser('~') + '/temp/' + \
                   os.path.basename(os.path.dirname(self.tlog)) + '\\' + \
                   os.path.basename(self.tlog) + '.' + activity + '.txt'

        if os.path.exists(dump_txt)\
                and os.path.getmtime(self.tlog) <= os.path.getmtime(dump_txt):
            # just use the cache:
            print('Using cache: ' + dump_txt)
            return json.load(open(dump_txt, 'r'))

        marker_id = \
            next(
                iter([x for x in self.bigArray if b'$classname' in x and activity.encode('ascii') == x[b'$classname']]),
                {b'pos': -1})[b'pos']

        # find all the activities:
        acts = [x for x in self.bigArray if b'$class' in x and x[b'$class'] == marker_id]

        # filter the requested data
        data = list(map(self.extract_data, acts))

        # erase the deleted objects:
        data = [_ for _ in data if not _['ObjectID'] in self.deleted_obj_ids]

        # print( [x['Note'] for x in data] )

        directory = os.path.dirname(dump_txt)
        if not os.path.exists(directory):
            os.makedirs(directory)

        print('Dumping the data into: ' + dump_txt)
        json.dump(data, open(dump_txt, 'w'))

        return data

    def extract_data(self, activity):

        data = dict()

        data['ObjectID'] = self.bigArray[activity[b'ObjectID']][b'NS.string'].decode('ascii')
        data['Pos'] = activity[b'pos']

        if b'PictureNote' in activity and 0 < len(self.bigArray[activity[b'PictureNote']][b'NS.objects']):
            picture_note = self.bigArray[self.bigArray[activity[b'PictureNote']][b'NS.objects'][0]]

            if b'ActivityId' in picture_note:
                data['ActivityId'] = self.bigArray[picture_note[b'ActivityId']][b'NS.string'].decode('utf-8')

            data['Filename'] = self.bigArray[picture_note[b'FileName']][b'NS.string'].decode('utf-8')

            # make sure that thumbnail exists
            bn = ntpath.dirname(ntpath.dirname(self.tlog)) + '\\Media\\' + data['Filename']

            if os.path.isfile(bn + '.jpg') and not os.path.isfile(bn + ' (Mobile).jpg'):
                print('Creating a thumbnail: ' + bn + ' (Mobile).jpg')

                import PIL
                from PIL import Image

                org = PIL.Image.open(bn + '.jpg')
                factor = org.size[0] / 300

                org.resize((int(org.size[0] / factor), int(org.size[1] / factor)), Image.ANTIALIAS) \
                    .save(bn + ' (Mobile).jpg', quality=100)

        if b'Duration' in activity:
            data['DurationMin'] = activity[b'Duration']

        data['Timestamp'] = log_timestamp_2datetime(self.bigArray[activity[b'Timestamp']][b'NS.time'])

        data['Time'] = log_timestamp_2datetime(self.bigArray[activity[b'Time']][b'NS.time'])

        data['Note'] = ''
        if b'Note' in activity:
            data['Note'] = self.bigArray[activity[b'Note']][b'NS.string']
            if not isinstance(data['Note'], str):
                data['Note'] = data['Note'].decode('utf-8')

        return data
