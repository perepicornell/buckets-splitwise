"""
Create .env file from .env.example to set up your configuration
"""
from dotenv import load_dotenv
import os

load_dotenv()
BUCKETS_BUDGET_FILE_PATH = os.getenv('BUCKETS_BUDGET_FILE_PATH')
BUCKETS_SPLITWISE_ACCOUNT_NAME = os.getenv('BUCKETS_SPLITWISE_ACCOUNT_NAME')
BUCKETS_PAYMENTS_ACCOUNT = os.getenv('BUCKETS_PAYMENTS_ACCOUNT')
SPLITWISE_CONSUMER_KEY = os.getenv('SPLITWISE_CONSUMER_KEY')
SPLITWISE_CONSUMER_SECRET = os.getenv('SPLITWISE_CONSUMER_SECRET')
SPLITWISE_LAST_VALID_TOKEN = {
    'access_token': os.getenv('SPLITWISE_LAST_VALID_TOKEN'),
    'token_type': os.getenv('SPLITWISE_LAST_VALID_TOKEN_TYPE')
}
# Using 90 days by default, still have to check the hard limit from the API.
SPLITWISE_EXPENSES_DAYS_AGO = os.getenv('SPLITWISE_EXPENSES_DAYS_AGO', int)
# The dated_after will override the days_ago setting, so at the beginning of
# using the script, set the dated_after to the last day you already have your
# Splitwise expenses registered so it will not include that day or the prior.
SPLITWISE_EXPENSES_DATED_AFTER = os.getenv('SPLITWISE_EXPENSES_DATED_AFTER')
# By default (and without mentioning it in the docs) the API returns a limit
# of 20 expenses. Set it to a limit that you think will cover the amount of
# expenses you'll have in the last 3 months.
SPLITWISE_EXPENSES_LIMIT = os.getenv('SPLITWISE_EXPENSES_LIMIT', int)
SPLITWISE_CALLBACK_URL = "http://localhost:1337/generate_token/"