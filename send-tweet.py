# coding=utf-8
import codecs
import configparser
import datetime
import os
import re
import pytz
import redis
import sys
import time
import twitter
import urlparse


class Tweeter:

    # These MUST be set in a config file or environment settings:
    twitter_consumer_key = ''
    twitter_consumer_secret = ''
    twitter_access_token = ''
    twitter_access_token_secret = ''

    # These are OPTIONAL settings, with their defaults:
    
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

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        self.config_file = (os.path.join(self.project_root, 'config.cfg'))

        self.load_config()

        self.redis = redis.Redis(host=self.redis_hostname,
                                port=self.redis_port,
                                password=self.redis_password)

    def load_config(self):
        if os.path.isfile(self.config_file):
            self.load_config_from_file()
        else:
            self.load_config_from_env()

    def load_config_from_file(self):
        config = configparser.ConfigParser()
        config.read(self.config_file)

        settings = config['DEFAULT']

        # Required settings:
        self.twitter_consumer_key = settings['TwitterConsumerKey']
        self.twitter_consumer_secret = settings['TwitterConsumerSecret']
        self.twitter_access_token = settings['TwitterAccessToken']
        self.twitter_access_token_secret = settings['TwitterAccessTokenSecret']

        # Optional settings:
        self.verbose = int(settings.get('Verbose', self.verbose))
        self.years_ahead = int(settings.get('YearsAhead', self.years_ahead))
        self.timezone = settings.get('Timezone', self.timezone)
        self.max_time_window = settings.get('MaxTimeWindow',
                                                        self.max_time_window)

        self.redis_hostname = settings.get('RedisHostname',
                                                        self.redis_hostname)
        self.redis_port = int(settings.get('RedisPort', self.redis_port))
        self.redis_password = settings.get('RedisPassword',
                                                        self.redis_password)

    def load_config_from_env(self):
        # Required settings:
        self.twitter_consumer_key = os.environ.get('TWITTER_CONSUMER_KEY')
        self.twitter_consumer_secret = os.environ.get(
                                                    'TWITTER_CONSUMER_SECRET')
        self.twitter_access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
        self.twitter_access_token_secret = os.environ.get(
                                                'TWITTER_ACCESS_TOKEN_SECRET')
        # Optional settings:
        self.verbose = int(os.environ.get('VERBOSE', self.verbose))
        self.years_ahead = int(os.environ.get('YEARS_AHEAD', self.years_ahead))
        self.timezone = os.environ.get('TIMEZONE', self.timezone)
        self.max_time_window = os.environ.get('MAX_TIME_WINDOW',
                                                        self.max_time_window)

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
            print "No last_run_time in database.\nThis must be the first time this has been run.\nSettinge last_run_time now.\nRun the script again in a few minutes or more, and it should work."
            sys.exit(0)

        try:
            local_tz = pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise TweeterError('Unknown or no timezone in settings: %s' %
                                                                self.timezone)

        local_last_run_time = last_run_time.astimezone(local_tz)
        local_time_now = datetime.datetime.now(local_tz)

        year_dir = str(int(local_time_now.strftime('%Y')) - self.years_ahead)
        month_file = '%s.txt' % local_time_now.strftime('%m')

        # eg tweets/1660/01.txt
        f = codecs.open(os.path.join(
                            self.project_root, 'tweets', year_dir, month_file),
                        'r', 'utf-8')

        tweets_to_send = []

        for line in f:
            line = line.strip()
            if line != '':
                line_match = re.match(
                                '^(\d{4}-\d{2}-\d{2}\s\d{2}\:\d{2})\s(.*?)$',
                                                                        line)
                if line_match:
                    [tweet_time, tweet_text] = line_match.groups()
                    local_modern_tweet_time = self.modernize_time(tweet_time, local_tz)

                    now_minus_tweet = (local_time_now - local_modern_tweet_time).total_seconds()
                    tweet_minus_lastrun = (local_modern_tweet_time - local_last_run_time).total_seconds()

                    # Tweet is earlier than now:
                    if now_minus_tweet >= 0:
                        print "A\n"
                        # And Tweet is since we last ran and within our max
                        # time window:
                        if tweet_minus_lastrun >= 0 and now_minus_tweet < (self.max_time_window * 60):
                            print "Sending %s\n" % tweet_text
                            tweets_to_send.append(tweet_text)
                        else:
                            print "Breaking\n"
                            break

        f.close()

        self.set_last_run_time()

        # We want to tweet the oldest one first, so reverse list:
        self.send_tweets(tweets_to_send[::-1])

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

    def modernize_time(self, t, local_tz):
        """
        Takes a time string like `1661-04-28 12:34` and translates it to the
        modern equivalent in local time, eg:
        datetime.datetime(2014, 4, 28, 12, 34, 00, tzinfo=<DstTzInfo 'Europe/London' BST+1:00:00 DST>)
        `local_tz` is a pytz timezone object.
        """
        naive_time = datetime.datetime.strptime(t, '%Y-%m-%d %H:%M')
        local_modern_time = local_tz.localize(
            datetime.datetime(
                naive_time.year + self.years_ahead,
                naive_time.month,
                naive_time.day,
                naive_time.hour,
                naive_time.minute,
                naive_time.second,
            )
        )
        return local_modern_time

    def send_tweets(self, tweets):
        """
        `tweets` is a list of tweet texts to post now.
        Should be in the order in which they need to be posted.
        """

        if len(tweets) > 0:
            for tweet_text in tweets:
                self.log(u'Tweeting: %s [%s characters]' % (
                                                tweet_text, len(tweet_text)))
                api = twitter.Api(
                    consumer_key=self.twitter_consumer_key,
                    consumer_secret=self.twitter_consumer_secret,
                    access_token_key=self.twitter_access_token,
                    access_token_secret=self.twitter_access_token_secret
                )
                status = api.PostUpdate(tweet_text)
                time.sleep(2)


    def log(self, s):
        if self.verbose == 1:
            print s.encode('utf-8')


class TweeterError(Exception):
    pass


def main():
    tweeter = Tweeter()

    tweeter.start()


if __name__ == "__main__":
    main()
