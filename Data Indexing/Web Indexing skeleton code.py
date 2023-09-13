import os
import asyncio
import logging.config
from aiohttp import ClientSession, TCPConnector
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch, helpers, RequestsHttpConnection
from kafka import KafkaProducer
import json
import fasttext
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
import xgboost as xgb
from gensim.models import Word2Vec
from webcrawler import WebCrawler  # Make sure you import your actual WebCrawler
from query_python import QueryProcessor  # Make sure you import your actual QueryProcessor
import configparser
import signal

# Read Configuration File
config = configparser.ConfigParser()
config.read('settings.ini')

# Initialize Logger
logging.config.fileConfig('logging.ini')

# Signal Handler for Graceful Shutdown
def signal_handler(signum, frame):
    logging.info("Signal received for graceful shutdown.")
    exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class Initialization:
    def __init__(self):
        self.es = Elasticsearch(
            [{'host': config.get('Elasticsearch', 'HOST'), 'port': config.getint('Elasticsearch', 'PORT')}],
            connection_class=RequestsHttpConnection,
            maxsize=25,
            timeout=30,
            retry_on_timeout=True
        )
        self.producer = KafkaProducer(
            bootstrap_servers=config.get('Kafka', 'BOOTSTRAP_SERVERS'),
            retries=5
        )
        self.fasttext_model = fasttext.load_model(config.get('Models', 'FASTTEXT_MODEL'))
        self.nlp = spacy.load(config.get('Models', 'SPACY_MODEL'))
        self.tfidf_vectorizer = TfidfVectorizer()

class FeatureExtraction:
    def __init__(self, init_object):
        self.init_object = init_object

    def extract_features(self, text):
        features = {}
        features['fasttext'] = self.init_object.fasttext_model.get_sentence_vector(text)
        doc = self.init_object.nlp(text)
        features['spacy'] = [token.vector for token in doc]
        features['tfidf'] = self.init_object.tfidf_vectorizer.transform([text]).toarray()
        return features

class WebScraper:
    def __init__(self, init_object, feature_extractor):
        self.init_object = init_object
        self.feature_extractor = feature_extractor

    async def fetch(self, url, session):
        try:
            async with session.get(url, timeout=60) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            logging.error(f"Failed to fetch {url}: {e}")
            return None

    async def index_webpage(self, url):
        async with ClientSession(connector=TCPConnector(limit=25)) as session:
            html = await self.fetch(url, session)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                text = soup.get_text()
                features = self.feature_extractor.extract_features(text)
                self.init_object.producer.send('webpage_features', value=json.dumps({'url': url, 'features': features}))
                logging.info(f"Successfully indexed {url}")

async def main():
    init_object = Initialization()
    feature_extractor = FeatureExtraction(init_object)
    web_scraper = WebScraper(init_object, feature_extractor)

    web_crawler = WebCrawler(init_object)
    query_processor = QueryProcessor(init_object)

    urls = web_crawler.get_urls()

    await asyncio.gather(*[web_scraper.index_webpage(url) for url in urls])
    logging.info("Finished indexing.")

    query_processor.process_query("some sample query")

if __name__ == '__main__':
    asyncio.run(main())
