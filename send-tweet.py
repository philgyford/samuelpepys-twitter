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

    def __init__(self):

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        self.load_config()

    def load_config(self):

        self.years_ahead = int(os.environ.get('YEARS_AHEAD'))

        self.script_frequency = int(os.environ.get('SCRIPT_FREQUENCY'))

        self.twitter_consumer_key = os.environ.get('TWITTER_CONSUMER_KEY')

        self.twitter_consumer_secret = os.environ.get(
                                                    'TWITTER_CONSUMER_SECRET')

        self.twitter_access_token = os.environ.get('TWITTER_ACCESS_TOKEN')

        self.twitter_access_token_secret = os.environ.get(
                                                'TWITTER_ACCESS_TOKEN_SECRET')

        self.verbose = int(os.environ.get('VERBOSE'))

    def start(self):

        london_tz = pytz.timezone('Europe/London')

        # eg, 2013-01-31 12:00:00
        time_now = datetime.datetime.now(london_tz)

        # eg, 1660-01-31 12:00:00
        old_time_now = london_tz.localize(
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
        f = open(os.path.join(self.project_root,
                                            'tweets', year_dir, month_file))

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
                    local_tweet_time = london_tz.localize(naive_tweet_time)
                    time_diff = (old_time_now - local_tweet_time).total_seconds()
                    if time_diff >= 0 and time_diff < (self.script_frequency * 60):
                        if self.verbose == 1:
                            'Tweeting: %s' % tweet_text
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
