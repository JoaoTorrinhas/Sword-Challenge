import asyncio
import json
import redis.asyncio as redis
import logging


logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/worker.log"),
        logging.StreamHandler()
    ],
    level=logging.INFO
)


async def handle_processing_worker(event_data):
    logger.info(f"Processing recommendation: {event_data['recommendation']} for patient {event_data['patient_id']}")
    
    # Simulate sending an email to the patient with the recommendation
    logger.info(f"Email sent to patient {event_data['patient_id']} with recommendation: {event_data['recommendation']}")
    

async def main():
    redis_worker = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)
    pubsub = redis_worker.pubsub()
    await pubsub.subscribe("recommendation_channel")
    logger.info("Worker started and listening for recommendation events...")
    
    while True:
        message = await pubsub.get_message()
        
        # Ensure message is not None and data is a string
        if message and isinstance(message["data"], str):
            try:
                logger.info(f"Received message: {message}")
                event_data = json.loads(message["data"])
                await handle_processing_worker(event_data)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
            
        await asyncio.sleep(1)
        
    
if __name__ == "__main__":
    asyncio.run(main())
    

