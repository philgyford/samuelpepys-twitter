# Samuel Pepys Twitter

A Python 3 script for posting Twitter tweets and/or Mastodon posts at specific
times. Used for the ~~[@samuelpepys](http://twitter.com/samuelpepys) Twitter
account and~~ [@samuelpepys@mastodon.social](https://mastodon.social/@samuelpepys)
Mastodon account.

You could replace the included tweets/posts with your own, for your own
schedule.

Uses Redis to store the time the script last ran.

It can send only Twitter tweets, or only Mastodon posts, or send identical
updates to both simultaneously.

It needs to be run automatically, ideally once per minute, e.g. via `cron`.
Every minute, this should be run:

    python poster.py

See below for installation instructions, including for Heroku.


## Post files

There are files of posts in dated yearly directories and monthly files, eg,
`posts/1660/01.txt`. Most recent posts at the top of each file. The years
should be `YEARS_AHEAD` years ago. eg, if `YEARS_AHEAD` is set to `363`, then
posts in the `1660` directory will be used in 2023.

For your own project, replace the contents of the `posts/` directory with your
own dated folders and files.

You could set `YEARS_AHEAD` to `0` and then posts will be sent on the day
they're dated for. Possibly a more useful and common requirement!

Posts should be in time order, with most recent first. Each post should be on
a single line, preceded by its date and time,  and an optional 'r' (to indicate
the post's "kind". `r`, a reply, is currently the only option, see below). Valid
formats:

    1660-01-02 11:20   This is post 3

    1660-01-02 11:18 r This is a reply to post 1.

    1660-01-02 11:16   This is post 1.

Any lines that aren't of that format will be ignored. So feel free to comment
out any posts to be ignored by prepending them with a different character, and
leave blank lines to make reading easier.

The script doesn't check for length of post, so any posts longer than 280
characters will be submitted and (depending on the service) possibly rejected.


## What gets posted

The script looks through all the posts and grabs any whose time (adjusted with
`YEARS_AHEAD`) fulfills all three conditions:

1. It is earlier than *now* (ie, not in the future).
2. It is since the script last ran.
3. It is also since `MAX_TIME_WINDOW` minutes ago.

The last condition is to catch the following scenario: Something goes wrong with
the server or script and it isn't run successfully for, say, 12 hours. The next
time it's run it would instantly post all posts set for the last 12 hours.
Assuming we don't want this, set `MAX_TIME_WINDOW` to how many minutes back we'd
want to check.

If you *would* want to post all the past 12 hours worth of posts, set
`MAX_TIME_WINDOW` to a very large number.

Any posts that match those conditions will be posted a couple of seconds apart,
in the order their datetimes are in.


## Replies

If a line has an `r` between the time and the text, it is a reply to whichever
post is on the line below it, so it will be posted "in reply to" that post.
If, for some reason, the previous post failed to post, the reply will still
be posted, but not as a reply.

NOTE: Replies do not currently work across month boundaries. i.e. if the very
earliest post in a month's file is an `r` it will be posted as a standard,
non-reply post.


## Testing your posts

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

    FILE posts/1660/09.txt
    1660-09-26 20:40: Post ends with lowercase character ("...eography for a while")


## Configuration

Configuration can either be set in a config file or in environment variables.
If `config.cfg` is present, that is used, otherwise environment variables.

Whichever you use you should include the API settings for one or both of a
Twitter app (API v2) and Mastodon app. If you don't set the Twitter Consumer Key (or
leave it empty), no tweets will be sent. If you don't set the Mastodon Client
ID (or leave it empty), no posts will be sent.

All other settings are optional.

If the environment variable `REDIS_URL` – or its config file equivalent – is
left out, the script tries to use a local, un-password-protected, database.

See [Wikipedia's list](http://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
of TZ timezone strings for the `TIMEZONE` setting.

### Config file

To use a config file, copy `config_example.cfg` to `config.cfg`. Then change the
values appropriately for your project.

### Environment variables

To use environment variables, *don't* create a `config.cfg` file.

You can copy `.env_example` to `.env`, and change its values appropriately. This
will set environment variables during local development with Docker, and might
work with however you choose to deploy to production.

Or, if using a service like Heroku, set the environment variables as the service
requires, using `.env_example` as a guide for what to set (see below).


## Local development

You could run it in a local virtual environment, installing python requirements
from the `requirements.txt` file. Then set up either a `config.cfg` or `.env`
file (see above). Then run the script:

    $ ./poster.py

That will send a post if there is one with an appropriate date and time.

Or you can use Docker, which includes a Redis database, and which will run the
`clock.py` process to check for tweets/posts every minute. Install Docker,
set up a `.env` file (see above), and then:

    $ docker-compose build
    $ docker-compose up

If you need to access Redis CLI in its Docker container:

    $ docker exec -it poster_redis bash
    # redis-cli

## Heroku setup

To run this on Heroku (these instructions haven't been tried for years):

1. Set up a new Heroku app.

2. Set Heroku environment variables for all the environment variables, eg:

        $ heroku config:set MAX_TIME_WINDOW=20

3. Add a Redis database, eg:

        $ heroku addons:add rediscloud

4. Copy the Redis add-on's URL to the `REDIS_URL` environment variable:

        $ heroku config:get REDIS_CLOUD_URL
        [ copy that value ]
        $ heroku config:set REDIS_URL=redis://rediscloud:...

5. Push all the code and posts to your Heroku app:

        $ git push heroku master

There you go. I think that's it... The `Procfile` specifies a `clock` process
that runs `clock.py`. This sets up a scheduler to run the code in `poster.py`
every minute.


## Running on Heroku with Scheduler

Previously we didn't use the clock process but ran this using the Scheduler.
The downside is that it can only run up to once every 10 minutes.

To do it that way, remove the `Procfile` and push the code to Heroku.

Add the free [Heroku Scheduler](https://addons.heroku.com/scheduler) to your
app:

    $ heroku addons:add scheduler:standard

Have it run `python poster.py` every 10 minutes.


## Credits

By Phil Gyford

* phil@gyford.com
* https://www.gyford.com
* https://mastodon.social/@philgyford
