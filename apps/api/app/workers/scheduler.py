import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from app.workers.celery_tasks import refresh_all_active_endpoints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    scheduler = BlockingScheduler()
    # Run the cache refresh job once on startup, then every hour
    scheduler.add_job(
        lambda: refresh_all_active_endpoints.delay(),
        "interval",
        hours=1,
        id="refresh_active_endpoints"
    )
    logger.info("APScheduler worker beat scheduler started. Job configured: hourly refresh.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
