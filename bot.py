import json

import tweepy

import bot_config

def get_last_tweet():
    pass

def run():

    api = bot_config.create_api()

    # Create a tweet
    #api.update_status("Hello World")

    me = api.me()
    timeline = api.home_timeline(trim_user=True, include_entities=False)
    print(f"USER ID: {me.id}")
    print(json.dumps(me._json, indent=2))
    for item in timeline:
        if item.user.id == me.id:
            print(json.dumps(item._json, indent=2))

if __name__ == "__main__":
    run()
