import argparse
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


class Representabot:
    AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
    AWS_BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    MAX_TWEETS = os.environ.get("MAX_TWEETS", 4)
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

    def __init__(self, congress, session):
        self.congress = congress
        self.session = session
        self.twitter_api = self.__create_api()
        self.s3_client = self.__get_s3_client()
        self.tweets = self.__load()
        self.senate_obj = cd.SenateData(congress, session)
        self.senate_data = self.senate_obj.get_senate_list()

    def __create_api(self):
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

    def __get_s3_client(self):
        """Gets an S3 client from boto3"""
        if self.AWS_ACCESS_KEY:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.AWS_ACCESS_KEY,
                aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
            )
        else:
            s3_client = boto3.client("s3")
        return s3_client

    def __load(self):
        """Load previous tweet data file from Google Cloud"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.AWS_BUCKET_NAME, Key="tweets.csv"
            )
        except self.s3_client.exceptions.NoSuchKey as e:
            logging.error(
                "No Such Key: S3 bucket "
                f"{self.AWS_BUCKET}/{self.OBJ_FILENAME}"
            )
            raise e
        except self.s3_client.exceptions.InvalidObjectState as e:
            logging.error(
                "Invalid Object State: S3 bucket "
                f"{self.AWS_BUCKET}/{self.OBJ_FILENAME}"
            )
            raise e

        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")

        if status == 200:
            tweets = pd.read_csv(response.get("Body"), dtype=self.DTYPES)
        elif status == 403:
            logging.error(
                "Access Denied: S3 bucket "
                f"{self.AWS_BUCKET}/{self.OBJ_FILENAME}"
            )
            raise PermissionError("Access Denied")
        elif status == 404:
            logging.error(
                "No Such Key: S3 bucket "
                f"{self.AWS_BUCKET}/{self.OBJ_FILENAME}"
            )
            raise self.s3_client.exceptions.NoSuchKey("No Such Key")
        else:
            logging.warning(f"Status: {status}")
            raise RuntimeError("Unable to open resource")
        return tweets

    def __save(self, df):
        """Write tweet data back to Google Cloud"""
        try:
            with io.StringIO() as csv_buffer:
                df.sort_values(
                    by=["congress", "session", "vote"], inplace=True
                )
                df.to_csv(csv_buffer, index=False)
                response = self.s3_client.put_object(
                    Bucket=self.AWS_BUCKET_NAME,
                    Key=self.OBJ_FILENAME,
                    Body=csv_buffer.getvalue(),
                )

                status = response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )

                if status != 200:
                    raise Exception(
                        f"Unable to save file {self.AWS_BUCKET_NAME}/{self.OBJ_FILENAME}"
                    )
                return status
        except Exception as e:
            logging.error("Cloud Storage not configured for writing data… ")
            logging.error(e)
            # NOTE: Use this to fall back to local storage
            # df.to_csv(self.OBJ_FILENAME, index=False)

    def run(self):
        """Read a list of previous tweets from Cloud Storage
        and Senate roll call vote data. Tweets out any untweeted
        votes based on the functions contained in data.py.
        """
        new_tweets = pd.DataFrame(
            columns=["tweet_id", "congress", "session", "date", "vote"],
            dtype=str,
        )
        for item in self.senate_data["vote_summary"]["votes"]["vote"]:
            query = (
                "congress == @self.congress "
                "and session == @self.session "
                "and date == @item['vote_date'] "
                "and vote == @item['vote_number']"
            )

            # If the current vote isn't already processed, then process it
            if self.tweets.query(query).empty:
                try:
                    text, party_data, vote_data = self.senate_obj.process_vote(
                        item
                    )
                    status = self.twitter_api.update_status(text)
                    # Keep track of new tweets to be reconciled with old
                    # tweets later
                    new_tweets = new_tweets.append(
                        {
                            "tweet_id": status.id_str,
                            "congress": self.congress,
                            "session": self.session,
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

            # Only process a limited number of tweets in a single run
            if len(new_tweets) == self.MAX_TWEETS:
                break

        if not new_tweets.empty:
            logging.info(f"Tweeted {len(new_tweets)} new votes")
            self.__save(self.tweets.append(new_tweets))
            # Function needs to return something to work as a Cloud Function
            return new_tweets["tweet_id"].to_json()
        else:
            return "{}"  # Empty JSON object


def lambda_handler(event, context):
    try:
        repbot = Representabot(event["congress"], event["session"])
        result = repbot.run()
        return {"statusCode": 200, "body": json.dumps(result)}
    except KeyError as e:
        return {
            "statusCode": 404,
            "body": f'KeyError: {e}, must have "congress" and "session" keys in request',
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--congress",
        type=str,
        required=True,
        help="Congress to process, e.g. 117",
    )
    parser.add_argument(
        "--session",
        type=str,
        required=True,
        help="Session of the Senate to process, e.g. 1",
    )
    args = parser.parse_args()
    repbot = Representabot(args.congress, args.session)
    repbot.run()
