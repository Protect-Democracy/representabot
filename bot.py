import json
import logging
import os
import random  # TODO: REMOVE THIS

import pandas as pd
import tweepy

from google.cloud import storage

import bot_config
import congress_data as cd

# Need to set up Google Cloud Storage.
# See: https://cloud.google.com/storage/docs/reference/libraries
GC_BUCKET_NAME = "representabot-bucket-1"
GC_FILENAME = "tweets.csv"


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


def run():
    api = bot_config.create_api()

    tweets = load()

    senate_data = cd.get_senate_list(cd.CONGRESS_NUMBER, cd.SENATE_SESSION)
    for item in senate_data["vote_summary"]["votes"]["vote"]:
        query = (
            "congress == @cd.CONGRESS_NUMBER "
            "and session == @cd.SENATE_SESSION "
            "and date == @item['vote_date'] "
            "and vote == @item['vote_number']"
        )

        if tweets.query(query).empty:
            # TODO: Tweet the tweet and save the tweet id
            # Create a tweet
            #api.update_status("Hello World")
            print("TWEETING…")
            tweets = tweets.append({
                "tweet_id": random.randint(1, 10001),  # TODO: CHANGE THIS
                "congress": cd.CONGRESS_NUMBER,
                "session": cd.SENATE_SESSION,
                "date": item["vote_date"],
                "vote": item["vote_number"]
            }, ignore_index=True)
    save(tweets)


if __name__ == "__main__":
    run()
