import os
from apify_client import ApifyClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_apify_scraping():
    """Test Apify scraping connection using environment variable for API token."""
    # Get API token from environment
    API_TOKEN = os.getenv("APIFY_API_TOKEN")
    if not API_TOKEN:
        raise ValueError("APIFY_API_TOKEN environment variable not set. Please set it before running this test.")
    
    ACTOR_ID = "oJMZe85C0opC0xcx2"
    
    # Initialize client
    client = ApifyClient(token=API_TOKEN)
    
    # Test URL - Bill Gates
    test_urls = ["https://www.linkedin.com/in/williamhgates/"]
    
    # Prepare input as per user description
    run_input = {
        "profiles": test_urls
    }
    
    logger.info(f"Starting Actor {ACTOR_ID} with input: {run_input}")
    
    try:
        # Call the actor
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        if run:
            logger.info(f"Actor run started. ID: {run.get('id')}")
            logger.info(f"Run status: {run.get('status')}")
            
            # Get dataset items
            dataset_id = run.get("defaultDatasetId")
            logger.info(f"Fetching results from dataset: {dataset_id}")
            
            dataset_items = client.dataset(dataset_id).list_items().items
            
            if dataset_items:
                logger.info(f"Successfully retrieved {len(dataset_items)} items.")
                logger.info("First item sample:")
                logger.info(dataset_items[0])
            else:
                logger.warning("No items returned in dataset.")
        else:
            logger.error("Actor run failed to start or returned None.")
            
    except Exception as e:
        logger.error(f"Error running Apify test: {e}")

if __name__ == "__main__":
    test_apify_scraping()