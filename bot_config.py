import logging
import os

import tweepy

def create_api():
    consumer_key = os.environ.get(
        "CONSUMER_KEY", "M6IetCvtvfbCZNdgkQC0WBSTN"
    )
    consumer_secret = os.environ.get(
        "CONSUMER_SECRET",
        "ktAtCa6sAGAvoKMyaJOBebRzpHsuy8kPInqLIElwOAHkOKqLrQ"
    )
    access_token = os.getenv(
        "ACCESS_TOKEN",
        "1374098610619617282-qCvUfbowpQ5RF2rmj9A4GcnzxgpExT"
    )
    access_token_secret = os.environ.get(
        "ACCESS_TOKEN_SECRET",
        "5jfvy2lPjihSz2xNmdhkKObeXO0vZIeBkkSR0TR1yufqU"
    )

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(
        auth,
        compression=True,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True
    )
    try:
        api.verify_credentials()
    except Exception as e:
        logging.error("Error creating API", exc_info=True)
        raise e
    logging.info("API created")
    return api
