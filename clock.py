from apscheduler.schedulers import Scheduler
import logging
import tweeter

logging.basicConfig()
sched = Scheduler()

@sched.interval_schedule(minutes=1)
def timed_job():
    # Yes, this should add this stuff to a queue, rather than running it
    # directly. It doesn't.
    tw = tweeter.Tweeter()
    tw.start()

sched.start()

while True:
    pass
