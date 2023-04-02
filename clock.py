from apscheduler.schedulers.background import BackgroundScheduler
import logging
import poster

logging.basicConfig()
scheduler = BackgroundScheduler()


@scheduler.scheduled_job('interval', minutes=1)
def timed_job():
    # Yes, this should add this stuff to a queue, rather than running it
    # directly. It doesn't.
    p = poster.Poster()
    p.start()


scheduler.start()

while True:
    pass
