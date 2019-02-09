#!/usr/bin/env python
# coding=utf-8
import codecs
import datetime
import logging
import os
import re
import sys
import time
import urllib.parse as urlparse

import pytz
import configparser
import redis
import twitter
from mastodon import Mastodon


logging.basicConfig()


class Tweeter:

    twitter_consumer_key = ''
    twitter_consumer_secret = ''
    twitter_access_token = ''
    twitter_access_token_secret = ''

    mastodon_client_id = ''
    mastodon_client_secret = ''
    mastodon_access_token = ''
    mastodon_api_base_url = 'https://mastodon.social'

    # 1 will output stuff.
    verbose = 0

    # How many years ahead are we of the dated tweets?
    years_ahead = 0

    # Whenever we last ran this script, we'll only ever post tweets from within
    # the past max_time_window minutes.
    max_time_window = 20

    # Which timezone are we using to check when tweets should be sent?
    # eg 'Europe/London'.
    # See http://en.wikipedia.org/wiki/List_of_tz_database_time_zones for
    # possible strings.
    timezone = 'Europe/London'

    # Only used if we're using Redis.
    redis_hostname = 'localhost'
    redis_port = 6379
    redis_password = None
    # Will be the redis.Redis() object:
    redis = None

    def __init__(self):

        self.logger = logging.getLogger(__name__)

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        self.config_file = (os.path.join(self.project_root, 'config.cfg'))

        self.load_config()

        if self.verbose:
            self.logger.setLevel(logging.INFO)

        self.redis = redis.Redis(host=self.redis_hostname,
                                port=self.redis_port,
                                password=self.redis_password,
                                charset='utf-8',
                                decode_responses=True)

        self.twitter_api = None
        self.mastodon_api = None

        if self.twitter_consumer_key:
            self.twitter_api = twitter.Api(
                consumer_key=self.twitter_consumer_key,
                consumer_secret=self.twitter_consumer_secret,
                access_token_key=self.twitter_access_token,
                access_token_secret=self.twitter_access_token_secret
            )

        if self.mastodon_client_id:
            self.mastodon_api = Mastodon(
                client_id=self.mastodon_client_id,
                client_secret=self.mastodon_client_secret,
                access_token=self.mastodon_access_token,
                api_base_url=self.mastodon_api_base_url
            )

        try:
            self.local_tz = pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            self.error('Unknown or no timezone in settings: %s' % self.timezone)
            sys.exit(0)

    def load_config(self):
        if os.path.isfile(self.config_file):
            self.load_config_from_file()
        else:
            self.load_config_from_env()

    def load_config_from_file(self):
        config = configparser.ConfigParser()
        config.read(self.config_file)

        settings = config['DEFAULT']

        self.twitter_consumer_key = settings['TwitterConsumerKey']
        self.twitter_consumer_secret = settings['TwitterConsumerSecret']
        self.twitter_access_token = settings['TwitterAccessToken']
        self.twitter_access_token_secret = settings['TwitterAccessTokenSecret']

        self.mastodon_client_id = settings['MastodonClientId']
        self.mastodon_client_secret = settings['MastodonClientSecret']
        self.mastodon_access_token = settings['MastodonAccessToken']
        self.mastodon_api_base_url = settings['MastodonApiBaseUrl']

        self.verbose = int(settings.get('Verbose', self.verbose))
        self.years_ahead = int(settings.get('YearsAhead', self.years_ahead))
        self.timezone = settings.get('Timezone', self.timezone)
        self.max_time_window = int(settings.get('MaxTimeWindow',
                                                        self.max_time_window))

        self.redis_hostname = settings.get('RedisHostname',
                                                        self.redis_hostname)
        self.redis_port = int(settings.get('RedisPort', self.redis_port))
        self.redis_password = settings.get('RedisPassword',
                                                        self.redis_password)

    def load_config_from_env(self):
        self.twitter_consumer_key = os.environ.get('TWITTER_CONSUMER_KEY')
        self.twitter_consumer_secret = os.environ.get(
                                                    'TWITTER_CONSUMER_SECRET')
        self.twitter_access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
        self.twitter_access_token_secret = os.environ.get(
                                                'TWITTER_ACCESS_TOKEN_SECRET')

        self.mastodon_client_id = os.environ.get('MASTODON_CLIENT_ID')
        self.mastodon_client_secret = os.environ.get('MASTODON_CLIENT_SECRET')
        self.mastodon_access_token = os.environ.get('MASTODON_ACCESS_TOKEN')
        self.mastodon_api_base_url = os.environ.get('MASTODON_API_BASE_URL')

        self.verbose = int(os.environ.get('VERBOSE', self.verbose))
        self.years_ahead = int(os.environ.get('YEARS_AHEAD', self.years_ahead))
        self.timezone = os.environ.get('TIMEZONE', self.timezone)
        self.max_time_window = int(os.environ.get('MAX_TIME_WINDOW',
                                                        self.max_time_window))

        redis_url = urlparse.urlparse(os.environ.get('REDIS_URL'))
        self.redis_hostname = redis_url.hostname
        self.redis_port = redis_url.port
        self.redis_password = redis_url.password

    def start(self):

        # eg datetime.datetime(2014, 4, 25, 18, 59, 51, tzinfo=<UTC>)
        last_run_time = self.get_last_run_time()

        # We need to have a last_run_time set before we can send any tweets.
        # So the first time this is run, we can't do anythning.
        if last_run_time is None:
            self.set_last_run_time()
            logging.warning("No last_run_time in database.\nThis must be the first time this has been run.\nSettinge last_run_time now.\nRun the script again in a minute or more, and it should work.")
            sys.exit(0)

        local_time_now = datetime.datetime.now(self.local_tz)

        year_dir = str(int(local_time_now.strftime('%Y')) - self.years_ahead)
        month_file = '%s.txt' % local_time_now.strftime('%m')

        # eg tweets/1660/01.txt
        path = os.path.join(self.project_root, 'tweets', year_dir, month_file)

        with open(path) as file:
            lines = [line.strip() for line in file]

        all_tweets = self.get_all_tweets(lines)

        tweets_to_send = self.get_tweets_to_send(
                                    all_tweets, last_run_time, local_time_now)

        self.set_last_run_time()

        # We want to tweet the oldest one first, so reverse list:
        self.send_tweets(tweets_to_send[::-1])

        # And the same with Mastodon toots:
        self.send_toots(tweets_to_send[::-1])

    def get_all_tweets(self, lines):
        """
        Go through all the lines in the file and, for any that contain
        valid tweet data, add them to a list to return.

        Returns a list of dicts, each one data about a tweet.
        """
        tweets = []

        for line in lines:

            if line != '':
                tweet = self.parse_tweet_line(line)

                if tweet:
                    tweets.append(tweet)
                else:
                    # An invalid line format or invalid tweet time.
                    continue

        return tweets

    def get_tweets_to_send(self, all_tweets, last_run_time, local_time_now):
        """
        Work out which of all the tweets in the month need to be sent.

        all_tweets - List of dicts, one per tweet
        last_run_time - datetime object for when the script was last run
        local_time_now - timezone-aware datetime for now

        Returns a list of dicts of the tweets that need sending.
        """

        tweets_to_send = []

        local_last_run_time = last_run_time.astimezone(self.local_tz)

        for n, tweet in enumerate(all_tweets):

            local_modern_tweet_time = self.modernize_time(tweet['time'])
            now_minus_tweet = (local_time_now - local_modern_tweet_time).total_seconds()
            tweet_minus_lastrun = (local_modern_tweet_time - local_last_run_time).total_seconds()

            if now_minus_tweet >= 0:
                # Tweet is earlier than now.
                if tweet_minus_lastrun >= 0 and now_minus_tweet <= (self.max_time_window * 60):
                    # And Tweet is since we last ran and within our max time window.

                    if tweet['is_reply'] == True:
                        # Get the time of the previous tweet, which is the one
                        # this tweet is replying to.
                        prev_tweet = all_tweets[n+1]
                        in_reply_to_time = prev_tweet['time']
                    else:
                        in_reply_to_time = None

                    tweet['in_reply_to_time'] = in_reply_to_time

                    tweets_to_send.append(tweet)
                else:
                    break

        return tweets_to_send

    def parse_tweet_line(self, line):
        """
        Given one line from a text file, try to parse it out into time and
        tweet text.

        Returns a dict of data if successful, otherwise False

        A line is like one of:

        1666-02-09 14:08 This is my text
        1666-02-09 14:08   This is my text
        1666-02-09 14:08 r This is my text
        1666-02-09 14:08 r   This is my text
        """
        tweet = False

        pattern = '''
            ^                           # Start of line
            (
                \d\d\d\d-\d\d-\d\d      # Date like 1666-02-09
                \s
                \d\d\:\d\d              # Time like 14:08
            )                           # GROUP 1: Date and time
            (?:                         # Don't count this group
                \s                      # A space before the 'r'
                (
                    r                   # A literal 'r'.
                )                       # GROUP 2: r (or None)
            )?                          # The 'r ' is optional
            \s+                         # One or more spaces
            (.*?)                       # The tweet text
            $                           # End of line
        '''

        line_match = re.search(pattern, line, re.VERBOSE)

        if line_match:
            [tweet_time, tweet_kind, tweet_text] = line_match.groups()

            # Check the time maps to a valid modern time:
            local_modern_tweet_time = self.modernize_time(tweet_time)

            if local_modern_tweet_time:

                if tweet_kind == 'r':
                    is_reply = True
                else:
                    is_reply = False

                tweet = {
                    'time':     tweet_time,
                    'text':     tweet_text.strip(),
                    'is_reply': is_reply,
                }

        return tweet

    def set_last_run_time(self):
        """
        Set the 'last run time' in the database to now, in UTC.
        """
        time_now = datetime.datetime.now(pytz.timezone('UTC'))
        self.redis.set('last_run_time', time_now.strftime("%Y-%m-%d %H:%M:%S"))

    def get_last_run_time(self):
        """
        Get the 'last run time' from the database.
        Returns, eg
        datetime.datetime(2014, 4, 25, 18, 59, 51, tzinfo=<UTC>)
        or `None` if it isn't currently set.
        """
        last_run_time = self.redis.get('last_run_time')

        if last_run_time:
            return datetime.datetime.strptime(last_run_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone('UTC'))
        else:
            return None

    def modernize_time(self, t):
        """
        Takes a time string like `1661-04-28 12:34` and translates it to the
        modern equivalent in local time, eg:
        datetime.datetime(2014, 4, 28, 12, 34, 00, tzinfo=<DstTzInfo 'Europe/London' BST+1:00:00 DST>)
        Returns False if something goes wrong.
        """
        naive_time = datetime.datetime.strptime(t, '%Y-%m-%d %H:%M')
        try:
            local_modern_time = self.local_tz.localize(
                datetime.datetime(
                    naive_time.year + self.years_ahead,
                    naive_time.month,
                    naive_time.day,
                    naive_time.hour,
                    naive_time.minute,
                    naive_time.second,
                )
            )
        except ValueError as e:
            # Unless something else is wrong, it could be that naive_time
            # is 29th Feb and there's no 29th Feb in the current, modern, year.
            self.log(
                "Skipping %s as can't make a modern time from it: %s" % (t, e))
            local_modern_time = False

        return local_modern_time

    def send_tweets(self, tweets):
        """
        `tweets` is a list of tweets to post now.

        Each element is a dict of:
            'time' (e.g. '1666-02-09 12:35')
            'text' (e.g. "This is my tweet")
            'is_reply_to' (e.g. '1666-02-09 12:34' or '')

        Should be in the order in which they need to be posted.
        """
        if self.twitter_api is None:
            self.log('No Twitter Consumer Key set; not tweeting')
            return

        for tweet in tweets:

            if tweet['in_reply_to_time'] is not None:
                # This tweet is a reply, so check that it's a reply to the
                # immediately previous tweet.
                # It *should* be, but if something went wrong, maybe not.
                previous_status_time = self.redis.get('previous_status_time')

                if tweet['in_reply_to_time'] == previous_status_time:
                    previous_tweet_id = self.redis.get('previous_tweet_id')
                else:
                    previous_tweet_id = None

            self.log('Tweeting: {} [{} characters]'.format(
                                            tweet['text'],
                                            len(tweet['text']) ))

            try:
                status = self.twitter_api.PostUpdate(
                                tweet['text'],
                                in_reply_to_status_id=previous_tweet_id)
            except twitter.TwitterError as e:
                self.error(e)
            else:
                # Set these so that we can see if the next tweet is a reply
                # to this one, and then one ID this one was.
                self.redis.set('previous_status_time', tweet['time'])
                self.redis.set('previous_tweet_id', status.id)

            time.sleep(2)

    def send_toots(self, toots):
        """
        `toots` is a list of toot texts to post now.

        Each element is a dict of:
            'time' (e.g. '1666-02-09 12:35')
            'text' (e.g. "This is my toot")
            'is_reply' boolean; is this a reply to the previous toot.

        Should be in the order in which they need to be posted.
        """
        if self.mastodon_api is None:
            self.log('No Mastodon Client ID set; not tooting')
            return

        for toot in toots:
            self.log('Tooting: %s [%s characters]' % (
                                        toot['text'], len(toot['text'])))
            status = self.mastodon_api.toot(toot['text'])
            time.sleep(2)


    def log(self, s):
        self.logger.info(s)

    def error(self, s):
        self.logger.error(s)


def main():
    tweeter = Tweeter()

    tweeter.start()


if __name__ == "__main__":
    main()
