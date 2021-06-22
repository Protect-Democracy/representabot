import io
import json
import logging
import os

import boto3
import dotenv
import pandas as pd
import tweepy

import data as cd


# Load all environment variables from `.env` file
dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)

AWS_BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
OBJ_FILENAME = os.environ.get("OBJ_FILENAME")


def create_api():
    """ Creates Tweepy API object for use later """
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
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )

        response = s3.get_object(Bucket=AWS_BUCKET_NAME, Key="tweets.csv")

        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

        if status == 200:
            tweets = pd.read_csv(response.get("Body"), dtype=str)
        else:
            logging.warning(f"Status: {status}")
            raise Exception("Unable to open resource")
    except Exception as e:
        logging.error("No datafile found…")
        raise e
    return tweets


def save(df):
    """ Write tweet data back to Google Cloud """
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        with io.StringIO() as csv_buffer:
            df.sort_values(by=["congress", "session", "vote"], inplace=True)
            df.to_csv(csv_buffer, index=False)
            response = s3.put_object(
                Bucket=AWS_BUCKET_NAME,
                Key=OBJ_FILENAME,
                Body=csv_buffer.getvalue()
            )

            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

            if status != 200:
                raise Exception(
                    f"Unable to save file {AWS_BUCKET_NAME}/{OBJ_FILENAME}"
                )
            return status
    except Exception as e:
        logging.error(
            "Cloud Storage not configured for writing data… "
        )
        logging.error(e)
        # NOTE: Use this to fall back to local storage
        #df.to_csv(OBJ_FILENAME, index=False)


def run(request):
    """ Read a list of previous tweets from Google Cloud Storage
        and Senate roll call vote data. Tweets out any untweeted
        votes based on the functions contained in data.py.
        Parameter is required by Google Cloud Functions and not
        used.
    """
    api = create_api()
    tweets = load()
    senate_obj = cd.SenateData(cd.CONGRESS_NUMBER, cd.SENATE_SESSION)
    senate_data = senate_obj.get_senate_list()
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

        # If the current vote isn't already processed, then process it
        if tweets.query(query).empty:
            try:
                text, party_data, vote_data = senate_obj.process_vote(item)
                status = api.update_status(text)
                # Keep track of new tweets to be reconciled with old
                # tweets later
                new_tweets = new_tweets.append({
                    "tweet_id": status.id_str,
                    "congress": cd.CONGRESS_NUMBER,
                    "session": cd.SENATE_SESSION,
                    "date": item["vote_date"],
                    "vote": item["vote_number"],
                    **party_data,
                    **vote_data
                }, ignore_index=True)
            except Exception as e:
                # Tweet failed for some reason
                logging.error("Tweet failed")
                logging.error(text)
    if not new_tweets.empty:
        logging.info(f"Tweeted {len(new_tweets)} new votes")
        save(tweets.append(new_tweets))
        # Function needs to return something to work as a Google Cloud Function
        return json.dumps(new_tweets["tweet_id"].to_json())
    else:
        return "{}"  # Empty JSON object


if __name__ == "__main__":
    run(None)
