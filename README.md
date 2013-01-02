# Samuel Pepys Twitter

Python script for posting tweets at specific times. Used for the [@samuelpepys](http://twitter.com/samuelpepys) Twitter account.


## Tweet files

There are files of tweets in dated yearly directories and monthly files, eg, `tweets/1660/01.txt`. Most recent tweets at the top of each file. The years shoul be `YEARS_AHEAD` years ago. eg, if `YEARS_AHEAD` is set to `353`, then tweets in the `1660` directory will be used in 2013.

Tweets should be in time order, with most recent first. Each tweet should be on a single line, preceded by its date and time, eg:

    1660-01-02 11:20 Great talk that many places have declared for a free Parliament; it is believed they will be forced to fill up the House with old members. 

Any lines that aren't of that format (ie, with that datetime format at the start, followed by a tweet) will be ignored. So feel free to comment out any tweets to be ignored by prepending them with a different character, and leave blank lines to make reading easier.

The script doesn't check for length of tweet, so any tweets longer than 140 characters will be submitted and, I expect, rejected. Having a line like this:

    YYYY-MM-DD HH:MM 12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890

at the start of each file, and setting your window to be exactly as wide as the line, makes it easy to get tweet length correct.

**NOTE:** The script is quite simple. It looks for the most recent tweet with today's date that's within `SCRIPT_FREQUENCY` minutes. This means that:

1. Tweets in the last `SCRIPT_FREQUENCY` minutes of yesterday might not be sent, depending on when your script runs. So avoid having tweets then.

2. All tweets should be scheduled more than `SCRIPT_FREQUENCY` minutes apart, or some will never get tweeted.


## Configuration 

The script relies on environment variables for configuration. These are the possible settings:

    # Output extra debug text while running? 1 or 0 (Default).
    VERBOSE=1

    # How many years ahead of the dated tweets are we? (Default: 0)
    YEARS_AHEAD=353

    # How many minutes apart will the script be run? (Default: 10)
    SCRIPT_FREQUENCY=10

    # Which timezone are the times of the tweets in? (Default: 'Europe/London')
    TIMEZONE='Europe/London'

    # OAuth settings from your Twitter app at https://dev.twitter.com/apps/
    TWITTER_CONSUMER_KEY=YOURCONSUMERKEY
    TWITTER_CONSUMER_SECRET=YOURCONSUMERSECRET
    TWITTER_ACCESS_TOKEN=YOURACCESSTOKEN
    TWITTER_ACCESS_TOKEN_SECRET=YOURACCESSTOKENSECRET

See [Wikipedia's list](http://en.wikipedia.org/wiki/List_of_tz_database_time_zones) of TZ timezone strings for the `TIMEZONE` setting.


## Local setup

Use [pip](http://www.pip-installer.org/) to install required packages by doing:

    $ pip install -r requirements.txt

Using [virtualenv](http://www.virtualenv.org/) and [virtualenvwrapper](http://virtualenvwrapper.readthedocs.org/), you can set the environment variables by having `$VIRTUAL_ENV/bin/postactivate` something like this:

    #!/bin/bash
    # This hook is run after this virtualenv is activated.

    export VERBOSE=1
    export YEARS_AHEAD=353
    export SCRIPT_FREQUENCY=10
    export TIMEZONE=Europe/London
    export TWITTER_CONSUMER_KEY=YOURCONSUMERKEY
    export TWITTER_CONSUMER_SECRET=YOURCONSUMERSECRET
    export TWITTER_ACCESS_TOKEN=YOURACCESSTOKEN
    export TWITTER_ACCESS_TOKEN_SECRET=YOURACCESSTOKENSECRET

Then just run the script:

    $ python send-tweet.py


## Heroku setup

Obviously, set up a new app.

Set Heroku environment variables for all the environment variables, eg:

    $ heroku config:set SCRIPT_FREQUENCY=10

Add the free [Heroku Scheduler](https://addons.heroku.com/scheduler) to your app:

    $ heroku addons:add scheduler:standard

Go to your [Scheduler dashboard](https://heroku-scheduler.herokuapp.com/dashboard) and add a task like `python send-tweet.py` to run every 10 (or whatever `SCRIPT_FREQUENCY` you've set) minutes.

Push all the code  and tweets to your Heroku app:

    $ git push heroku master

There you go.

