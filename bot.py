import json
import logging
import os
import random  # TODO: REMOVE THIS

import dotenv
import pandas as pd
import tweepy

from google.cloud import storage

import data as cd


# Load all environment variables from `.env` file
dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)

GC_BUCKET_NAME = os.environ.get("GC_BUCKET_NAME")
GC_FILENAME = os.environ.get("GC_FILENAME")


def create_api():
    consumer_key = os.environ.get("CONSUMER_KEY")
    consumer_secret = os.environ.get("CONSUMER_SECRET")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.environ.get("ACCESS_TOKEN_SECRET")

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
    return api


def load():
    """ Load previous tweet data file from Google Cloud """
    try:
        tweets = pd.read_csv(f"gs://{GC_BUCKET_NAME}/{GC_FILENAME}", dtype=str)
    except Exception as e:
        # TODO: Adapt this so it does not automatically tweet if file isn't
        # found; need a better failover
        # Check for existence of Google Cloud Storage object first
        logging.warning("No datafile found… generating new one")
        tweets = pd.DataFrame(
            columns=["tweet_id", "congress", "session", "date", "vote"], dtype=str
        )
    return tweets


def save(df):
    """ Write tweet data back to Google Cloud """
    try:
        client = storage.Client()
        bucket = client.get_bucket(GC_BUCKET_NAME)

        bucket.blob(GC_FILENAME).upload_from_string(
            df.to_csv(index=False), 'text/csv'
        )
    except Exception as e:
        logging.warning(
            "Google Cloud Storage not configured for writing data… "
            "falling back to local file system"
        )
        logging.warning(e)
        df.to_csv(GC_FILENAME, index=False)


def generate_tweet_text(congress, session, vote):
    pass


def run():
    api = create_api()

    tweets = load()

    senate_data = cd.get_senate_list(cd.CONGRESS_NUMBER, cd.SENATE_SESSION)
    new_tweets = pd.DataFrame(
        columns=["tweet_id", "congress", "session", "date", "vote"], dtype=str
    )
    for item in senate_data["vote_summary"]["votes"]["vote"]:
        query = (
            "congress == @cd.CONGRESS_NUMBER "
            "and session == @cd.SENATE_SESSION "
            "and date == @item['vote_date'] "
            "and vote == @item['vote_number']"
        )

        if tweets.query(query).empty:
            try:
                # TODO: Tweet the tweet and save the tweet id
                #text = generate_tweet_text(
                #    cd.CONGRESS_NUMBER, cd.SENATE_SESSION, item["vote_number"]
                #)
                #api.update_status(text)
                logging.info("TWEETING…")
                new_tweets = tweets.append({
                    "tweet_id": random.randint(1, 10001),  # TODO: CHANGE THIS
                    "congress": cd.CONGRESS_NUMBER,
                    "session": cd.SENATE_SESSION,
                    "date": item["vote_date"],
                    "vote": item["vote_number"]
                }, ignore_index=True)
            except Exception as e:
                # Tweet failed for some reason
                logging.error("Tweet failed")
                logging.error(e)
    if not new_tweets.empty:
        save(tweets.append(new_tweets))


if __name__ == "__main__":
    run()
