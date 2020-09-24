"""
Create .env file from .env.example to set up your configuration
"""
from dotenv import load_dotenv
import os

load_dotenv()
BUCKETS_BUDGET_FILE_PATH = os.getenv('BUCKETS_BUDGET_FILE_PATH')
BUCKETS_SPLITWISE_ACCOUNT_NAME = os.getenv('BUCKETS_SPLITWISE_ACCOUNT_NAME')
SPLITWISE_CONSUMER_KEY = os.getenv('SPLITWISE_CONSUMER_KEY')
SPLITWISE_CONSUMER_SECRET = os.getenv('SPLITWISE_CONSUMER_SECRET')
SPLITWISE_OAUTH2_TOKEN_URL = os.getenv('SPLITWISE_OAUTH2_TOKEN_URL')
SPLITWISE_OAUTH2_AUTH_URL = os.getenv('SPLITWISE_OAUTH2_AUTH_URL')
SPLITWISE_LAST_VALID_TOKEN = {
    'access_token': os.getenv('SPLITWISE_LAST_VALID_TOKEN'),
    'token_type': 'bearer'
}
SPLITWISE_CALLBACK_URL = "http://localhost:1337/generate_token/"