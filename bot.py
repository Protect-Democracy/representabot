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

AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
OBJ_FILENAME = os.environ.get("OBJ_FILENAME")

DTYPES = {
    "tweet_id": str,
    "congress": str,
    "session": str,
    "date": str,
    "vote": str,
    "yea_vote_total": "Int64",
    "yea_vote_D": "Int64",
    "yea_vote_R": "Int64",
    "nay_vote_total": "Int64",
    "nay_vote_D": "Int64",
    "nay_vote_R": "Int64",
    "abstain_vote_total": "Int64",
    "abstain_vote_D": "Int64",
    "abstain_vote_R": "Int64",
    "Nay": float,
    "Yea": float,
    "Abstain": float,
}


def create_api():
    """Creates Tweepy API object for use later"""
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
        wait_on_rate_limit_notify=True,
    )
    try:
        api.verify_credentials()
    except Exception as e:
        logging.error("Error creating API", exc_info=True)
        raise e
    return api


def get_s3_client():
    if AWS_ACCESS_KEY:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
    else:
        s3 = boto3.client("s3")
    return s3_client


def load():
    """Load previous tweet data file from Google Cloud"""
    s3 = get_s3_client()

    response = s3.get_object(Bucket=AWS_BUCKET_NAME, Key="tweets.csv")

    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

    if status == 200:
        tweets = pd.read_csv(response.get("Body"), dtype=DTYPES)
    else:
        # TODO: Improve exception handling by breaking out various
        # potential errors.
        logging.warning(f"Status: {status}")
        raise Exception("Unable to open resource")
    return tweets


def save(df):
    """Write tweet data back to Google Cloud"""
    try:
        s3 = get_s3_client()
        with io.StringIO() as csv_buffer:
            df.sort_values(by=["congress", "session", "vote"], inplace=True)
            df.to_csv(csv_buffer, index=False)
            response = s3.put_object(
                Bucket=AWS_BUCKET_NAME,
                Key=OBJ_FILENAME,
                Body=csv_buffer.getvalue(),
            )

            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

            if status != 200:
                raise Exception(
                    f"Unable to save file {AWS_BUCKET_NAME}/{OBJ_FILENAME}"
                )
            return status
    except Exception as e:
        logging.error("Cloud Storage not configured for writing data… ")
        logging.error(e)
        # NOTE: Use this to fall back to local storage
        # df.to_csv(OBJ_FILENAME, index=False)


def run(congress, session):
    """Read a list of previous tweets from Cloud Storage
    and Senate roll call vote data. Tweets out any untweeted
    votes based on the functions contained in data.py.
    """
    api = create_api()
    tweets = load()
    senate_obj = cd.SenateData(congress, session)
    senate_data = senate_obj.get_senate_list()
    new_tweets = pd.DataFrame(
        columns=["tweet_id", "congress", "session", "date", "vote"], dtype=str
    )
    for item in senate_data["vote_summary"]["votes"]["vote"]:
        query = (
            "congress == @congress "
            "and session == @session "
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
                new_tweets = new_tweets.append(
                    {
                        "tweet_id": status.id_str,
                        "congress": congress,
                        "session": session,
                        "date": item["vote_date"],
                        "vote": item["vote_number"],
                        **party_data,
                        **vote_data,
                    },
                    ignore_index=True,
                )
            except Exception as e:
                # Tweet failed for some reason
                logging.error("Tweet failed")
                logging.error(text)
                logging.error(e)

        # Only process a maximum of four (4) tweets in a single run
        if len(new_tweets) == 4:
            break
    if not new_tweets.empty:
        logging.info(f"Tweeted {len(new_tweets)} new votes")
        save(tweets.append(new_tweets))
        # Function needs to return something to work as a Google Cloud Function
        return new_tweets["tweet_id"].to_json()
    else:
        return "{}"  # Empty JSON object


def lambda_handler(event, context):
    try:
        result = run(event["congress"], event["session"])
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logging.error("Error in processing request")
        logging.error(e)
        raise e


if __name__ == "__main__":
    run(cd.CONGRESS_NUMBER, cd.SENATE_SESSION)
