# coding=utf-8
import codecs
import configparser
import datetime
import os
import re
import pytz
import redis
import twitter


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

    # How many minutes apart is the script running?
    script_frequency = 10

    # Which timezone are we using to check when tweets should be sent?
    # eg 'Europe/London'.
    # See http://en.wikipedia.org/wiki/List_of_tz_database_time_zones for
    # possible strings.
    timezone = 'Europe/London'

    def __init__(self):

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        self.config_file = (os.path.join(self.project_root, 'config.cfg'))

        self.load_config()

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
        self.script_frequency = int(settings.get('ScriptFrequency',
                                                        self.script_frequency))
        self.timezone = settings.get('Timezone', self.timezone)

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

        self.script_frequency = int(os.environ.get('SCRIPT_FREQUENCY',
                                                        self.script_frequency))
        self.timezone = os.environ.get('TIMEZONE', self.timezone)


    def start(self):

        try:
            local_tz = pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise TweeterError('Unknown or no timezone in settings: %s' % self.timezone)


        # eg, 2013-01-31 12:00:00
        time_now = datetime.datetime.now(local_tz)

        # eg, 1660-01-31 12:00:00
        old_time_now = local_tz.localize(
                        datetime.datetime(
                            int(time_now.strftime('%Y')) - self.years_ahead,
                            int(time_now.strftime('%m')),
                            int(time_now.strftime('%d')),
                            int(time_now.strftime('%H')),
                            int(time_now.strftime('%M')),
                            int(time_now.strftime('%S')),
                        )
                    )

        # Can't just use strftime on old_time_now because it only works on
        # years > 1900. Grrr.
        year_dir = str(int(time_now.strftime('%Y')) - self.years_ahead)
        month_file = '%s.txt' % time_now.strftime('%m')

        # eg tweets/1660/01.txt
        f = codecs.open(os.path.join(
                            self.project_root, 'tweets', year_dir, month_file),
                        'r', 'utf-8')

        for line in f:
            line = line.strip()
            if line != '':
                line_match = re.match(
                                '^(\d{4}-\d{2}-\d{2}\s\d{2}\:\d{2})\s(.*?)$',
                                                                        line)
                if line_match:
                    [tweet_time, tweet_text] = line_match.groups()
                    naive_tweet_time = datetime.datetime.strptime(tweet_time,
                                                            '%Y-%m-%d %H:%M')
                    local_tweet_time = local_tz.localize(naive_tweet_time)
                    time_diff = (old_time_now - local_tweet_time).total_seconds()
                    if time_diff >= 0 and time_diff < (self.script_frequency * 60):
                        self.log(u'Tweeting: %s [%s characters]' % (
                                                tweet_text, len(tweet_text)))
                        api = twitter.Api(
                            consumer_key=self.twitter_consumer_key,
                            consumer_secret=self.twitter_consumer_secret,
                            access_token_key=self.twitter_access_token,
                            access_token_secret=self.twitter_access_token_secret
                        )
                        status = api.PostUpdate(tweet_text)
                        self.log(status.text)
                        break
        f.close()

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
