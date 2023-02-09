# Samuel Pepys Twitter

Python 3 script for posting Twitter tweets and/or Mastodon Toots at specific
times. Used for the [@samuelpepys](http://twitter.com/samuelpepys) Twitter
account and [@samuelpepys@mastodon.social](https://mastodon.social/@samuelpepys)
Mastodon account.

Uses Redis to store the time the script last ran.

It can send only Twitter tweets, or only Mastodon toots, or send identical
updates to both simultaneously.

It needs to be run automatically, ideally once per minute, e.g. via `cron`.
Every minute, this should be run:

    python poster.py

See below for installation instructions, including for Heroku.


## Post files

There are files of posts in dated yearly directories and monthly files, eg,
`posts/1660/01.txt`. Most recent posts at the top of each file. The years
should be `YEARS_AHEAD` years ago. eg, if `YEARS_AHEAD` is set to `353`, then
posts in the `1660` directory will be used in 2013.

You could set `YEARS_AHEAD` to `0` and then posts will be sent on the day
they're dated for. Possibly a more useful and common requirement!

Posts should be in time order, with most recent first. Each post should be on
a single line, preceded by its date and time,  and an optional 'r' (to indicate
the post's "kind". `r`, a reply, is currently the only option, see below). Valid formats:

    1660-01-02 11:20   This is post 3

    1660-01-02 11:18 r This is a reply to post 1.

    1660-01-02 11:16   This is post 1.

Any lines that aren't of that format will be ignored. So feel free to comment
out any posts to be ignored by prepending them with a different character, and
leave blank lines to make reading easier.

The script doesn't check for length of post, so any posts longer than 280
characters will be submitted and rejected.


## What gets posted

The script looks through all the posts and grabs any whose time (adjusted with
    `YEARS_AHEAD`) fulfills all three conditions:

1. It is earlier than *now* (ie, not in the future).
2. It is since the script last ran.
3. It is also since `MAX_TIME_WINDOW` minutes ago.

The last condition is to catch the following scenario: Something goes wrong with the server or script and it isn't run successfully for, say, 12 hours. The next time it's run it would instantly post all posts set for the last 12 hours. Assuming we don't want this, set `MAX_TIME_WINDOW` to how many minutes back we'd want to check.

If you *would* want to post all the past 12 hours worth of posts, set `MAX_TIME_WINDOW` to a very large number.

Any posts that match those conditions will be posted a couple of seconds apart, in the order their datetimes are in.


## Replies

If a line has an `r` between the time and the text, it is a reply to whichever
post is on the line below it, so it will be posted "in reply to" that post.
If, for some reason, the previous post failed to post, the reply will still
be posted, but not as a reply.

Note: Replies do not currently work across month boundaries. i.e. if the very
earliest post in a month's file is an `r` it will be posted as a standard,
non-reply post.


## Testing

Use the included `tester.py` script to check the formatting of all post files.
It will list errors for any posts that are in the wrong order, or that are too
long, or that aren't of the correct format. eg:

	$ python tester.py

	FILE posts/1660/01.txt
	 1660-01-31 12:40: Time is after previous time (1660-01-31 11:00:00).

	FILE posts/1660/08.txt
	 1660-08-28 22:50: Post is 281 characters long.

	FILE posts/1660/09.txt
	 1660-08-29 14:12: Kind should be nothing or 'r'. It was: 'x'.


## Configuration

Configuration can either be set in a config file or in environment settings. If `config.cfg` is present, that is used, otherwise environment settings.

Whichever you use you should include the API settings for one or both of a Twitter app and Mastodon app. If you don't set the Twitter Consumer Key (or leave it empty), no tweets will be sent. If you don't set the Mastodon Client ID (or leave it empty), no toots will be sent.

All other settings are optional.

To use a config file, copy `config_example.cfg` to `config.cfg` to use that.

If using environment settings, they are listed below. If `REDIS_URL` or its config file equivalents are left out, the script tries to use a local, un-password-protected, database.

    # OAuth settings from your Twitter app at https://dev.twitter.com/apps/
    TWITTER_CONSUMER_KEY=YOURCONSUMERKEY
    TWITTER_CONSUMER_SECRET=YOURCONSUMERSECRET
    TWITTER_ACCESS_TOKEN=YOURACCESSTOKEN
    TWITTER_ACCESS_TOKEN_SECRET=YOURACCESSTOKENSECRET

    # Settings from your Mastodon app
    MASTODON_CLIENT_ID=YOURCLIENTID
    MASTODON_CLIENT_SECRET=YOURCLIENTSECRET
    MASTODON_ACCESS_TOKEN=YOURACCESSTOKEN
    # If this is left undefined, the default is 'https://mastodon.social'
    MASTODON_API_BASE_URL=YOURAPIBASEURL

    # Output extra debug text while running? 1 or 0 (Default).
    VERBOSE=1

    # How many years ahead of the dated posts are we? (Default: 0)
    YEARS_AHEAD=353

    # Regardless of when the script last ran, never send posts that are older than this many minutes. (Default: 20)
    MAX_TIME_WINDOW=20

    # Which timezone are the times of the posts in? (Default: 'Europe/London')
    TIMEZONE='Europe/London'

	# Example value:
	REDIS_URL = redis://rediscloud:sjPfErI4xocRopQW@pub-redis-18850.us-east-1-2.1.ec2.garantiadata.com:18850

See [Wikipedia's list](http://en.wikipedia.org/wiki/List_of_tz_database_time_zones) of TZ timezone strings for the `TIMEZONE` setting.


## Local setup

Use [pipenv](https://pipenv.readthedocs.io/en/latest/) to install required
packages by doing:

    $ pipenv install

Set up config values as above, either via a config file (probably best) or
environment settings.

Then just run the script:

    $ pipenv run ./poster.py

That will send a post if there is one with an appropriate date and time.


## Heroku setup

Set up a new Heroku app.

Set Heroku environment variables for all the environment variables, eg:

    $ heroku config:set MAX_TIME_WINDOW=20

Add a Redis database, eg:

	$ h addons:add rediscloud

Copy the Redis add-on's URL to the `REDIS_URL` environment variable:

	$ h config:get REDIS_CLOUD_URL
	[ copy that value ]
	$ h config:set REDIS_URL=redis://rediscloud:...

Push all the code and posts to your Heroku app:

    $ git push heroku master

There you go. I think that's it... The `Procfile` specifies a `clock` process
that runs `clock.py`. This sets up a scheduler to run the code in `poster.py`
every minute.


## Running on Heroku with Scheduler

Previously we didn't use the clock process but ran this using the Scheduler.
The downside is that it can only run up to once every 10 minutes.

To do it that way, remove the Procfile and push the code to Heroku.

Add the free [Heroku Scheduler](https://addons.heroku.com/scheduler) to your app:

    $ heroku addons:add scheduler:standard

Have it run `python poster.py` every 10 minutes.
