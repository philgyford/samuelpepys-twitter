#!/usr/bin/env python
# coding=utf-8
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
import tweepy
from atproto import Client
from atproto.exceptions import AtProtocolError, InvokeTimeoutError, UnauthorizedError
from mastodon import Mastodon, MastodonError


logging.basicConfig()


class Poster:

    twitter_consumer_key = ""
    twitter_consumer_secret = ""
    twitter_access_token = ""
    twitter_access_token_secret = ""

    mastodon_client_id = ""
    mastodon_client_secret = ""
    mastodon_access_token = ""
    mastodon_api_base_url = "https://mastodon.social"

    atproto_handle = ""
    atproto_password = ""

    # 1 will output INFO logging and above.
    # 2 will output DEBUG logging and above.
    verbose = 0

    # How many years ahead are we of the dated posts?
    years_ahead = 0

    # No matter when we last ran this script, we'll only ever post
    # posts from within the past max_time_window minutes.
    max_time_window = 20

    # Which timezone are we using to check when posts should be sent?
    # eg 'Europe/London'.
    # See http://en.wikipedia.org/wiki/List_of_tz_database_time_zones for
    # possible strings.
    timezone = "Europe/London"

    # Only used if we're using Redis.
    redis_hostname = "localhost"
    redis_port = 6666
    redis_password = None
    # Will be the redis.Redis() object:
    redis = None

    def __init__(self):

        self.logger = logging.getLogger(__name__)

        self.project_root = os.path.abspath(os.path.dirname(__file__))

        self.config_file = os.path.join(self.project_root, "config.cfg")

        self.load_config()

        if self.verbose:
            if self.verbose == 1:
                self.logger.setLevel(logging.INFO)
            elif self.verbose == 2:
                self.logger.setLevel(logging.DEBUG)

        self.redis = redis.Redis(
            host=self.redis_hostname,
            port=self.redis_port,
            password=self.redis_password,
            charset="utf-8",
            decode_responses=True,
        )

        self.twitter_api = None
        self.mastodon_api = None

        if self.twitter_consumer_key:
            self.twitter_api = tweepy.Client(
                consumer_key=self.twitter_consumer_key,
                consumer_secret=self.twitter_consumer_secret,
                access_token=self.twitter_access_token,
                access_token_secret=self.twitter_access_token_secret,
            )

        if self.mastodon_client_id:
            self.mastodon_api = Mastodon(
                client_id=self.mastodon_client_id,
                client_secret=self.mastodon_client_secret,
                access_token=self.mastodon_access_token,
                api_base_url=self.mastodon_api_base_url,
            )

        try:
            self.local_tz = pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            self.logger.error("Unknown or no timezone in settings: %s" % self.timezone)
            sys.exit(0)

    def load_config(self):
        if os.path.isfile(self.config_file):
            self.load_config_from_file()
        else:
            self.load_config_from_env()

    def load_config_from_file(self):
        config = configparser.ConfigParser()
        config.read(self.config_file)

        settings = config["DEFAULT"]

        self.twitter_consumer_key = settings["TwitterConsumerKey"]
        self.twitter_consumer_secret = settings["TwitterConsumerSecret"]
        self.twitter_access_token = settings["TwitterAccessToken"]
        self.twitter_access_token_secret = settings["TwitterAccessTokenSecret"]

        self.mastodon_client_id = settings["MastodonClientId"]
        self.mastodon_client_secret = settings["MastodonClientSecret"]
        self.mastodon_access_token = settings["MastodonAccessToken"]
        self.mastodon_api_base_url = settings["MastodonApiBaseUrl"]

        self.atproto_handle = settings["ATProtoHandle"]
        self.atproto_password = settings["ATProtoPassword"]

        self.verbose = int(settings.get("Verbose", self.verbose))
        self.years_ahead = int(settings.get("YearsAhead", self.years_ahead))
        self.timezone = settings.get("Timezone", self.timezone)
        self.max_time_window = int(settings.get("MaxTimeWindow", self.max_time_window))

        redis_url = urlparse.urlparse(settings.get("RedisURL"))
        self.redis_hostname = redis_url.hostname
        self.redis_port = redis_url.port
        self.redis_password = redis_url.password

    def load_config_from_env(self):
        self.twitter_consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
        self.twitter_consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
        self.twitter_access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
        self.twitter_access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

        self.mastodon_client_id = os.environ.get("MASTODON_CLIENT_ID")
        self.mastodon_client_secret = os.environ.get("MASTODON_CLIENT_SECRET")
        self.mastodon_access_token = os.environ.get("MASTODON_ACCESS_TOKEN")
        self.mastodon_api_base_url = os.environ.get("MASTODON_API_BASE_URL")

        self.atproto_handle = os.environ.get("ATPROTO_HANDLE")
        self.atproto_password = os.environ.get("ATPROTO_PASSWORD")

        self.verbose = int(os.environ.get("VERBOSE", self.verbose))
        self.years_ahead = int(os.environ.get("YEARS_AHEAD", self.years_ahead))
        self.timezone = os.environ.get("TIMEZONE", self.timezone)
        self.max_time_window = int(
            os.environ.get("MAX_TIME_WINDOW", self.max_time_window)
        )

        redis_url = urlparse.urlparse(os.environ.get("REDIS_URL"))
        self.redis_hostname = redis_url.hostname
        self.redis_port = redis_url.port
        self.redis_password = redis_url.password

    def start(self):
        self.logger.debug("Running start()")

        # eg datetime.datetime(2014, 4, 25, 18, 59, 51, tzinfo=<UTC>)
        last_run_time = self.get_last_run_time()
        self.logger.debug(f"Last run time: {last_run_time}")

        # We need to have a last_run_time set before we can send any posts.
        # So the first time this is run, we can't do anythning.
        if last_run_time is None:
            self.set_last_run_time()
            self.logger.warning(
                "No last_run_time in database.\n"
                "This must be the first time this has been run.\n"
                "Settinge last_run_time now.\n"
                "Run the script again in a minute or more, and it should work."
            )
            sys.exit(0)

        local_time_now = datetime.datetime.now(self.local_tz)

        year_dir = str(int(local_time_now.strftime("%Y")) - self.years_ahead)
        month_file = "%s.txt" % local_time_now.strftime("%m")

        # eg posts/1660/01.txt
        path = os.path.join(self.project_root, "posts", year_dir, month_file)

        with open(path) as file:
            lines = [line.strip() for line in file]

        all_posts = self.get_all_posts(lines)

        posts_to_send = self.get_posts_to_send(all_posts, last_run_time, local_time_now)

        self.set_last_run_time()

        # We want to tweet the oldest one first, so reverse list:
        self.send_tweets(posts_to_send[::-1])

        # And the same with Mastodon toots:
        self.send_toots(posts_to_send[::-1])

        # Adn the same with Bluesky skeets:
        self.send_skeets(posts_to_send[::-1])

    def get_all_posts(self, lines):
        """
        Go through all the lines in the file and, for any that contain
        valid post data, add them to a list to return.

        Returns a list of dicts, each one data about a post.
        """
        posts = []

        for line in lines:

            if line != "":
                post = self.parse_post_line(line)

                if post:
                    posts.append(post)
                else:
                    # An invalid line format or invalid post time.
                    continue

        return posts

    def get_posts_to_send(self, all_posts, last_run_time, local_time_now):
        """
        Work out which of all the posts in the month need to be sent.

        all_posts - List of dicts, one per post
        last_run_time - datetime object for when the script was last run
        local_time_now - timezone-aware datetime for now

        Returns a list of dicts of the posts that need sending.
        """

        posts_to_send = []

        local_last_run_time = last_run_time.astimezone(self.local_tz)

        for n, post in enumerate(all_posts):

            local_modern_post_time = self.modernize_time(post["time"])
            now_minus_post = (local_time_now - local_modern_post_time).total_seconds()

            if now_minus_post > 0:
                # Post is earlier than now.

                post_minus_last_run = (
                    local_modern_post_time - local_last_run_time
                ).total_seconds()

                if post_minus_last_run > 0 and now_minus_post <= (
                    self.max_time_window * 60
                ):
                    # And post is since we last ran and within our max time window.

                    if post["is_reply"] is True:
                        # Get the time of the previous post, which is the one
                        # this post is replying to.
                        prev_post = all_posts[n + 1]
                        in_reply_to_time = prev_post["time"]
                    else:
                        in_reply_to_time = None

                    post["in_reply_to_time"] = in_reply_to_time

                    self.logger.info(
                        "Preparing: '{}...' "
                        "timed {}, "
                        "is_reply: {}, "
                        "local_last_run_time: {}, "
                        "local_modern_post_time: {}, "
                        "post_minus_last_run: {}, "
                        "in_reply_to_time: {}".format(
                            post["text"][:20],
                            post["time"],
                            post["is_reply"],
                            local_last_run_time,
                            local_modern_post_time,
                            post_minus_last_run,
                            in_reply_to_time,
                        )
                    )

                    posts_to_send.append(post)
                else:
                    break

        return posts_to_send

    def parse_post_line(self, line):
        """
        Given one line from a text file, try to parse it out into time and
        post text.

        Returns a dict of data if successful, otherwise False

        A line is like one of:

        1666-02-09 14:08 This is my text
        1666-02-09 14:08   This is my text
        1666-02-09 14:08 r This is my text
        1666-02-09 14:08 r   This is my text
        """
        post = False

        pattern = r"""
            ^                           # Start of line
            (
                \d\d\d\d-\d\d-\d\d      # Date like 1666-02-09
                \s
                \d\d\:\d\d              # Time like 14:08
            )                           # GROUP 1: Date and time
            (?:                         # Don't count this group
                \s                      # A space before the 'r'
                (
                    \w                   # A literal 'r' (probably).
                )                       # GROUP 2: r (or None)
            )?                          # The 'r ' is optional
            \s+                         # One or more spaces
            (.*?)                       # The post text
            $                           # End of line
        """

        line_match = re.search(pattern, line, re.VERBOSE)

        if line_match:
            [post_time, post_kind, post_text] = line_match.groups()

            # Check the time maps to a valid modern time:
            local_modern_post_time = self.modernize_time(post_time)

            if local_modern_post_time:

                if post_kind == "r":
                    is_reply = True
                else:
                    is_reply = False

                post = {
                    "time": post_time,
                    "text": post_text.strip(),
                    "is_reply": is_reply,
                }

        return post

    def set_last_run_time(self):
        """
        Set the 'last run time' in the database to now, in UTC.
        """
        time_now = datetime.datetime.now(pytz.timezone("UTC"))
        self.redis.set("last_run_time", time_now.strftime("%Y-%m-%d %H:%M:%S"))

    def get_last_run_time(self):
        """
        Get the 'last run time' from the database.
        Returns, eg
        datetime.datetime(2014, 4, 25, 18, 59, 51, tzinfo=<UTC>)
        or `None` if it isn't currently set.
        """
        last_run_time = self.redis.get("last_run_time")

        if last_run_time:
            return datetime.datetime.strptime(
                last_run_time, "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=pytz.timezone("UTC"))
        else:
            return None

    def modernize_time(self, t):
        """
        Takes a time string like `1661-04-28 12:34` and translates it to the
        modern equivalent in local time, eg:
        datetime.datetime(
            2014, 4, 28, 12, 34, 00,
            tzinfo=<DstTzInfo 'Europe/London' BST+1:00:00 DST>)
        Returns False if something goes wrong.
        """
        naive_time = datetime.datetime.strptime(t, "%Y-%m-%d %H:%M")
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
            self.logger.info(f"Skipping {t} as can't make a modern time from it: {e}")
            local_modern_time = False

        return local_modern_time

    def send_tweets(self, posts):
        """
        `posts` is a list of tweets to post now.

        Each element is a dict of:
            'time' (e.g. '1666-02-09 12:35')
            'text' (e.g. "This is my tweet")
            'is_reply_to' (e.g. '1666-02-09 12:34' or '')
            'in_reply_to_time' (e.g. '1666-02-09 12:33', or None)

        Should be in the order in which they need to be posted.
        """
        if self.twitter_api is None:
            self.logger.debug("No Twitter Consumer Key set; not tweeting")
            return

        for post in posts:
            previous_status_id = None

            if post["in_reply_to_time"] is not None:
                # This tweet is a reply, so check that it's a reply to the
                # immediately previous tweet.
                # It *should* be, but if something went wrong, maybe not.
                previous_status_time = self.redis.get("previous_tweet_time")

                if post["in_reply_to_time"] == previous_status_time:
                    previous_status_id = self.redis.get("previous_tweet_id")

            self.logger.info(
                "Tweeting: {} [{} characters]".format(post["text"], len(post["text"]))
            )

            try:
                response = self.twitter_api.create_tweet(
                    text=post["text"], in_reply_to_tweet_id=previous_status_id
                )
            except tweepy.TweepyException as e:
                self.logger.error(e)
            else:
                # Set these so that we can see if the next tweet is a reply
                # to this one, and then which ID this one was.
                self.redis.set("previous_tweet_time", post["time"])
                self.redis.set("previous_tweet_id", response.data["id"])

            time.sleep(2)

    def send_toots(self, posts):
        """
        `posts` is a list of toot texts to post now.

        Each element is a dict of:
            'time' (e.g. '1666-02-09 12:35')
            'text' (e.g. "This is my toot")
            'is_reply' boolean; is this a reply to the previous toot.
            'in_reply_to_time' (e.g. '1666-02-09 12:33', or None)

        Should be in the order in which they need to be posted.
        """
        if self.mastodon_api is None:
            self.logger.debug("No Mastodon Client ID set; not tooting")
            return

        for post in posts:
            previous_status_id = None

            if post["in_reply_to_time"] is not None:
                # This toot is a reply, so check that it's a reply to the
                # immediately previous toot.
                # It *should* be, but if something went wrong, maybe not.
                previous_status_time = self.redis.get("previous_toot_time")

                if post["in_reply_to_time"] == previous_status_time:
                    previous_status_id = self.redis.get("previous_toot_id")

            self.logger.info(
                "Tooting: {} [{} characters]".format(post["text"], len(post["text"]))
            )

            try:
                status = self.mastodon_api.status_post(
                    post["text"], in_reply_to_id=previous_status_id
                )
            except MastodonError as e:
                self.logger.error(e)
            else:
                # Set these so that we can see if the next toot is a reply
                # to this one, and then which ID this one was.
                self.redis.set("previous_toot_time", post["time"])
                self.redis.set("previous_toot_id", status.id)

            time.sleep(2)

    def send_skeets(self, posts):
        """
        `posts` is a list of skeet texts to post now.

        Each element is a dict of:
            'time' (e.g. '1666-02-09 12:35')
            'text' (e.g. "This is my toot")
            'is_reply' boolean; is this a reply to the previous toot.
            'in_reply_to_time' (e.g. '1666-02-09 12:33', or None)

        Should be in the order in which they need to be posted.
        """
        if self.atproto_handle == "":
            self.logger.debug("No ATProto Handle set; not skeeting")
            return

        if len(posts) > 0:
            client = Client()
            try:
                client.login(self.atproto_handle, self.atproto_password)
            except UnauthorizedError as e:
                self.logger.error(e)
            else:
                for post in posts:
                    reply_to = {}

                    if post["in_reply_to_time"] is not None:
                        # This skeet is a reply, so check that it's a reply to the
                        # immediately previous skeet.
                        # It *should* be, but if something went wrong, maybe not.
                        previous_status_time = self.redis.get("previous_skeet_time")

                        if post["in_reply_to_time"] == previous_status_time:
                            # The root and parent should be the same if this is the
                            # first reply. Subsequent replies should have different
                            # root and parent.
                            root_uri = self.redis.get("root_skeet_uri")
                            root_cid = self.redis.get("root_skeet_cid")
                            parent_uri = self.redis.get("previous_skeet_uri")
                            parent_cid = self.redis.get("previous_skeet_cid")
                            reply_to = {
                                "root": {"uri": root_uri, "cid": root_cid},
                                "parent": {"uri": parent_uri, "cid": parent_cid},
                            }

                    self.logger.info(
                        "Skeeting: {} [{} characters]".format(
                            post["text"], len(post["text"])
                        )
                    )

                    try:
                        if len(reply_to.keys()) > 0:
                            status = client.send_post(
                                text=post["text"], reply_to=reply_to
                            )
                        else:
                            status = client.send_post(text=post["text"])
                    except (AtProtocolError, InvokeTimeoutError) as e:
                        self.logger.error(e)
                    else:
                        # Set these so that we can see if the next skeet is a reply
                        # to this one, and then which ID and URL this one was.
                        self.redis.set("previous_skeet_time", post["time"])
                        self.redis.set("previous_skeet_uri", status["uri"])
                        self.redis.set("previous_skeet_cid", status["cid"])

                        if post["in_reply_to_time"] is None:
                            # It wasn't a reply, so save its details as 'root' in case
                            # the next skeet(s) reply to it or its descendants.
                            self.redis.set("root_skeet_uri", status["uri"])
                            self.redis.set("root_skeet_cid", status["cid"])

            time.sleep(2)


def main():
    poster = Poster()

    poster.start()


if __name__ == "__main__":
    main()
