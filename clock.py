from apscheduler.schedulers.background import BackgroundScheduler
import logging
import tweeter

logging.basicConfig()
scheduler = BackgroundScheduler()

@scheduler.scheduled_job(minutes=1)
def timed_job():
    # Yes, this should add this stuff to a queue, rather than running it
    # directly. It doesn't.
    tw = tweeter.Tweeter()
    tw.start()

scheduler.start()

while True:
    pass
