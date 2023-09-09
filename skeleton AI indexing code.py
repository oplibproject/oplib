import os
import asyncio
import logging.config
import yaml
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
import signal

# Load and set up logging configuration from logging.yaml file
with open('logging.yaml', 'rt') as f:
    config = yaml.safe_load(f.read())
logging.config.dictConfig(config)

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    logging.info("Signal received for graceful shutdown.")
    # Implement graceful shutdown logic here
    exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class Initialization:
    def __init__(self):
        # Connection pooling and timeout for Elasticsearch
        self.es = Elasticsearch([{'host': 'localhost', 'port': 9200}],
                                connection_class=RequestsHttpConnection,
                                maxsize=10)

        self.producer = KafkaProducer(bootstrap_servers='localhost:9092')

        self.fasttext_model = fasttext.load_model("fasttext_model.bin")
        self.nlp = spacy.load("en_core_web_sm")
        self.tfidf_vectorizer = TfidfVectorizer()
        self.xgb_model = xgb.XGBClassifier()
        self.word2vec_model = Word2Vec.load("word2vec_model")

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
            async with session.get(url) as response:
                response.raise_for_status()  # Raise HTTP errors
                return await response.text()
        except Exception as e:
            logging.error(f"Failed to fetch {url}: {e}")
            return None

    async def index_webpage(self, url):
        connector = TCPConnector(limit=10)  # Limit simultaneous connections
        async with ClientSession(connector=connector) as session:
            html = await self.fetch(url, session)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                text = soup.get_text()
                features = self.feature_extractor.extract_features(text)
                self.init_object.producer.send('webpage_features', value=json.dumps({'url': url, 'features': features}))
                logging.info(f"Indexed {url}")

if __name__ == '__main__':
    init_object = Initialization()
    feature_extractor = FeatureExtraction(init_object)
    web_scraper = WebScraper(init_object, feature_extractor)

    with open("dataset_links.html", 'r') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    urls = [a['href'] for a in soup.find_all('a', href=True)]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*[web_scraper.index_webpage(url) for url in urls]))

    logging.info("Finished indexing.")
