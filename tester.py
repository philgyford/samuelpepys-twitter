#!/usr/bin/env python
# coding=utf-8
import codecs
import datetime
from glob import glob
import os
import re

class Tester:
    """
    Test all the text files to ensure:
        * Tweets are all in order - within each file the most recent should
          be first.
        * All Tweets are <= 280 characters in length.
        * All Tweets start with something that's not a lowercase character.
        * All Tweets end with something that's not a lowercase character.

    Outputs a report listing all errors.
    """

    def __init__(self):

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        # Will be a list of dicts:
        self.errors = []

    def start(self):

        # Cycle through every directory in /tweets/ whose name is four digits:
        for d in glob('{}/tweets/{}'.format(self.project_root, '[0-9]' * 4)):
            for f in os.listdir(d):
                # Test every .txt file:
                if f.endswith('.txt'):
                    self.test_file(
                            os.path.join(self.project_root, 'tweets', d, f))

        last_file = None

        # Output all errors, if any.
        if len(self.errors) == 0:
            print("\nEverything is OK.")
        else:
            for err in self.errors:
                # err has 'filepath', 'time' and 'text' elements.
                if last_file is None or last_file != err['filepath']:
                    # eg 'FILE: 1660/01.txt'
                    dir_file = '/'.join(err['filepath'].split('/')[-2:])
                    print("\nFILE tweets/{}".format(dir_file))

                print(" {}: {}".format(err['time'], err['text']))

                last_file = err['filepath']


    def test_file(self, filepath):
        "Test an individual file."

        f = codecs.open(filepath, 'r', 'utf-8')

        prev_time = None

        for line in f:
            line = line.strip()
            if line != '':
                # Use same match as in tweeter.py, and only test matching lines.
                line_match = re.match(
                            '^(\d{4}-\d{2}-\d{2}\s\d{2}\:\d{2})\s(.*?)$', line)

                if line_match:
                    [tweet_time, tweet_text] = line_match.groups()

                    # Check times are in the correct order.

                    t = datetime.datetime.strptime(tweet_time, '%Y-%m-%d %H:%M')

                    if prev_time is not None:
                        if t > prev_time:
                            self.add_error(filepath, tweet_time,
                                "Time is after previous time ({}).".format(prev_time))
                        elif t == prev_time:
                            self.add_error(filepath, tweet_time,
                                "Time is the same as previous time ({}).".format(prev_time))
                    prev_time = t

                    # Test tweet length.

                    if len(tweet_text) > 280:
                        self.add_error(filepath, tweet_time,
                            "Tweet is {} characters long.".format(len(tweet_text)))

                    # Test first/last characters.

                    if tweet_text[0].islower():
                        self.add_error(filepath, tweet_time,
                            'Tweet begins with lowercase character ("{}...")'.format(tweet_text[:20]))

                    if tweet_text[-1].islower():
                        self.add_error(filepath, tweet_time,
                            'Tweet ends with lowercase character ("...{}")'.format(tweet_text[-20:]))
        f.close()

    def add_error(self, filepath, dt, txt):
        self.errors.append({
            'filepath': filepath,
            'time': dt,
            'text': txt
        })


def main():
    tester = Tester()

    tester.start()


if __name__ == "__main__":
    main()
