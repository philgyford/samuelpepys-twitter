import codecs
import datetime
import os
import re
import pytz

import twitter


class Tweeter:

    # DEFAULT SETTINGS. OVERRIDE IN ENVIRONMENT SETTINGS:

    # 1 will output stuff.
    verbose = 0

    # How many years ahead are we of the dated tweets?
    years_ahead = 0

    # How many minutes apart is the script running?
    script_frequency = 10

    twitter_consumer_key = ''
    twitter_consumer_secret = ''
    twitter_access_token = ''
    twitter_access_token_secret = ''

    # Which timezone are we using to check when tweets should be sent?
    # eg 'Europe/London'.
    # See http://en.wikipedia.org/wiki/List_of_tz_database_time_zones for
    # possible strings.
    timezone = ''

    def __init__(self):

        import locale
        print u"Encoding: %s" % locale.getdefaultlocale()[1]
        self.project_root = os.path.abspath(os.path.dirname(__file__))

        print u"Unicode test: £ ’ …"

        self.load_config()

    def load_config(self):

        self.years_ahead = int(os.environ.get('YEARS_AHEAD', '0'))

        self.script_frequency = int(os.environ.get('SCRIPT_FREQUENCY', '10'))

        self.twitter_consumer_key = os.environ.get('TWITTER_CONSUMER_KEY')

        self.twitter_consumer_secret = os.environ.get(
                                                    'TWITTER_CONSUMER_SECRET')

        self.twitter_access_token = os.environ.get('TWITTER_ACCESS_TOKEN')

        self.twitter_access_token_secret = os.environ.get(
                                                'TWITTER_ACCESS_TOKEN_SECRET')

        self.verbose = int(os.environ.get('VERBOSE', '0'))

        self.timezone = os.environ.get('TIMEZONE', 'Europe/London')

    def start(self):

        local_tz = pytz.timezone(self.timezone)

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
                        if self.verbose == 1:
                            print u'Tweeting: %s [%s characters]' % (
                                                tweet_text, len(tweet_text))
                        api = twitter.Api(
                            consumer_key=self.twitter_consumer_key,
                            consumer_secret=self.twitter_consumer_secret,
                            access_token_key=self.twitter_access_token,
                            access_token_secret=self.twitter_access_token_secret
                        )
                        status = api.PostUpdate(tweet_text)
                        if self.verbose == 1:
                            print status
                        break
        f.close()


class TweeterError(Exception):
    pass


def main():
    tweeter = Tweeter()

    tweeter.start()


if __name__ == "__main__":
    main()
