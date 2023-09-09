from flask import Flask, jsonify, request
from dotenv import load_dotenv
from requests import get
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import os
import time
import ratelimiter

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    filename='app_advanced.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s'
)

# Set environment variables
QUEUE_SIZE = int(os.getenv('QUEUE_SIZE', 10))
THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', 4))

# Initialize Flask
app = Flask(__name__)

# Initialize Queue and ThreadPool
data_queue = Queue(maxsize=QUEUE_SIZE)
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

# Rate Limiter
rate_limit = ratelimiter.RateLimiter(max_calls=10, period=1)  # 10 requests per second

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"}), 200

def fetch_data_from_api():
    while True:
        try:
            with rate_limit:
                response = get('http://example.com/data')  # Mock API call
                if response.status_code == 200:
                    data_queue.put(response.json())
                    logging.info(f"Data added to queue: {response.json()}")
                else:
                    logging.error(f"Failed to fetch data: {response.status_code}")
        except Exception as e:
            logging.error(f"Exception occurred: {e}")
        time.sleep(1)

def process_data():
    while True:
        try:
            data = data_queue.get(timeout=10)  # Adjust timeout as needed
            # Insert data processing logic here
            logging.info(f"Processing data: {data}")
            # Simulate data processing delay
            time.sleep(2)
            data_queue.task_done()
        except Queue.Empty:
            logging.warning("Queue is empty! Waiting for new data.")
        except Exception as e:
            logging.error(f"Exception occurred: {e}")

if __name__ == '__main__':
    # Start health check endpoint
    executor.submit(app.run, host='0.0.0.0', port=5000)

    # Start data fetching and processing threads
    executor.submit(fetch_data_from_api)
    for _ in range(THREAD_POOL_SIZE - 1):  # One thread is for the API fetcher
        executor.submit(process_data)
