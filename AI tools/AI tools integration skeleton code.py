from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required
import logging
from elasticsearch import Elasticsearch
from redis import Redis
import pickle
from concurrent.futures import ThreadPoolExecutor

# Initialize Flask and plugins
app = Flask(__name__)
CORS(app)
limiter = Limiter(app)
jwt = JWTManager(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Elasticsearch
es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

# Initialize Redis for caching
redis = Redis(host='localhost', port=6379, db=0)

# Register default AI tools
ai_tools = {}

# Mock functions for AI tools
def summarize_tool(result, length="short"):
    result['summary'] = "This is a summary of the result."

def translate_tool(result, language="en"):
    result['translated_text'] = "This is the translated text."

# Registration function
def register_tool(name, func):
    ai_tools[name] = func

# Add default tools to ai_tools dictionary
register_tool('summarize', summarize_tool)
register_tool('translate', translate_tool)

# Function to perform search and return results
def perform_search(query):
    return [
        {'title': 'Sample Article 1', 'text': 'Sample text', 'url': 'http://example.com/1'},
        {'title': 'Sample Article 2', 'text': 'Another sample text', 'url': 'http://example.com/2'}
    ]

@app.route('/search', methods=['GET'])
@limiter.limit("5 per minute")
def search():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    tools = request.args.get('tools', "").split(",")

    cache_key = f"search:{query}:{','.join(tools)}"
    cached_results = redis.get(cache_key)
    if cached_results:
        return pickle.loads(cached_results)

    search_results = perform_search(query)

    for result in search_results:
        for tool_name in tools:
            if tool_name in ai_tools:
                ai_tools[tool_name](result)

    redis.set(cache_key, pickle.dumps(jsonify(search_results)))

    return jsonify(search_results)

@app.route('/apply_tool', methods=['POST'])
@jwt_required()
def apply_tool_endpoint():
    tool_name = request.json.get('name')
    tool_params = request.json.get('params')
    result = request.json.get('result')

    if tool_name not in ai_tools:
        return jsonify({'error': f'Tool {tool_name} is not registered'}), 400

    ai_tools[tool_name](result, **tool_params)
    cache_key = f"{tool_name}:{tool_params}:{result}"
    redis.set(cache_key, pickle.dumps(jsonify(result)))

    return jsonify(result)

@app.route('/register_tool', methods=['POST'])
@jwt_required()
def register_tool_endpoint():
    tool_name = request.json.get('name')
    tool_code = request.json.get('code')

    tool_func = pickle.loads(tool_code)
    register_tool(tool_name, tool_func)
    
    return jsonify({'message': f"Tool {tool_name} registered successfully"})

if __name__ == '__main__':
    app.run(debug=True)
