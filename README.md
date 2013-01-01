# @samuelpepys scheduler

There are files of tweets in dated yearly and monthly directories in `tweets/`. Most recent tweets at the top of each file.

Set Heroku environment variables for all the settings that `send-tweet.py` requires. eg:

    $ heroku config:set SCRIPT_FREQUENCY=10

Add the scheduler to your Heroku app:

    $ heroku addons:add scheduler:standard

Go to your [Scheduler dashboard](https://heroku-scheduler.herokuapp.com/dashboard) and add a task like `python send-tweet.py` to run every 10 (or whatever `SCRIPT_FREQUENCY` you've set) minutes.

Push all the code to your Heroku app:

    $ git push heroku master

There you go.

**Note:** The script is quite simple. It looks for the most recent tweet with today's date that's within `SCRIPT_FREQUENCY` minutes. This means that:

1. Tweets in the last `SCRIPT_FREQUENCY` minutes of yesterday might not be sent, depending on when your script runs.

2. All tweets should be scheduled more than `SCRIPT_FREQUENCY` minutes apart, or some will never get tweeted.

