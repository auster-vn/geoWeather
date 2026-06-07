import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from services.ingestion.producer import WeatherProducer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ingestion_scheduler")

async def main():
    producer = WeatherProducer()
    await producer.start()
    
    scheduler = AsyncIOScheduler()
    
    async def job():
        logger.info("Executing weather ingestion job cycle...")
        try:
            await producer.produce_all_cities()
        except Exception as e:
            logger.error(f"Error in ingestion job: {e}")
            
    # Trigger job immediately
    await job()
    
    # Schedule job every 10 minutes
    scheduler.add_job(
        job,
        trigger=IntervalTrigger(minutes=10),
        id="weather_poll_job",
        name="Poll weather API for all cities and publish to Kafka"
    )
    
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("Shutting down ingestion scheduler...")
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(main())
