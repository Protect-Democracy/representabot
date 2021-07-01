# representabot

## About me

Hi, I am `representabot`. I am a Twitter Bot that tweets regular updates of the latest votes in the U.S. Senate. What makes me different from other places that list congressional votes is that I will also tweet the percentage of the U.S. population represented by yeas and nays. This gives the world more information about how much the Senate’s votes align with the majority interests of the U.S.

## Methodology

### Data sources

All vote data and vote totals come from the [U.S. Senate](https://senate.gov) website. Data for state population comes from the [Census API](https://api.census.gov).

### Calculating representation

To calculate representation, a state's population is added each time a Senator from that state votes a specific way ("yea" or "nay"). The sum of these two numbers is divided by twice our calculated total of the U.S. population. (I do not include D.C. or Puerto Rico in this calculation, which means our statistic overestimates the percent of total people represented.)

I calculate the population in this way and calculate a "weighted average" so that our representation statistic adds up to 100% when you sum the percentage represented by yeas, nays, and other types of votes.

## Setting Me Up

### Requirements
I can be run from a command line, but I prefer to be hosted somewhere. I’m currently configured by my maker to use Amazon Web Services. Feel free to fork me, tear out my guts, and replace them with your favorite cloud platform instead.

I also store a running memory of my tweets in a CSV file. By default, this file is hosted on an AWS S3 bucket.

See [AWS documentation](https://docs.aws.amazon.com/index.html) for more details on setting up AWS. You’ll need to look at [Lambda](https://docs.aws.amazon.com/lambda/) and [S3](https://docs.aws.amazon.com/s3/) in particular.

I also need access to a Twitter account and their developer API. This comes in the form of four tokens: a consumer key, a consumer secret, an access token, and an access token secret. You can generate these for me from the [Twitter Developer Platform](https://developer.twitter.com).

Finally, I also require access to US Census data via their [Census API](https://www.census.gov/data/developers.html). You can [request a key](https://api.census.gov/data/key_signup.html) from the [US Census website](https://www.census.gov).

### Configuration
I use environment variables to run, which can be set in the AWS Lambda setup. Here's what I need. (See `env.sample` in the repo as well)

```
# AWS
AWS_ACCESS_KEY=<AWS access key>
AWS_SECRET_ACCESS_KEY=<AWS secret access key>
AWS_BUCKET_NAME=<AWS bucket name>
OBJ_FILENAME=<CSV filename, e.g. tweets.csv>

# Census data
CENSUS_API_KEY=<API key from the US Census API>
CONGRESS_NUMBER=<Congress number you wish to process, e.g. 117>
SENATE_SESSION=<Senate session you wish to process, e.g. 1>

# Twitter
CONSUMER_KEY=<First of four keys provided by Twitter’s API>
CONSUMER_SECRET=<Second Twitter key>
ACCESS_TOKEN=<Third Twitter key>
ACCESS_TOKEN_SECRET=<Fourth and final Twitter key, whew>
MAX_TWEETS=<Any integer, defaults to 4>
```

### Usage
You can run me with the following command:

```
python bot.py --congress <congress number> --session <senate session>
```

E.g.

```
python bot.py --congress 117 --session 1
```

Assuming everything is properly configured, I should tweet summaries of votes taken in the Senate for the current session.

### Advanced config/features
I’m not really a bot if I don’t run without a human instructing me what to do. In order to bring me to life, you will need to set up AWS Lambda and deploy me to that service. That is beyond the scope of this document, so please see the AWS Lambda documentation for more details.

You can also fool me into skipping votes by adding details to the CSV "database". If you don't want me to tweet about certain votes, just add fake entries to the database. I won’t be mad.

## Getting Help
If you have questions, concerns, bug reports, etc., please file an issue in this repository's [Issue Tracker](https://github.com/Protect-Democracy/representabot/issues).

## Getting Involved
See my instructions in [CONTRIBUTING](CONTRIBUTING.md).


----

## Open source licensing info
1. [TERMS](TERMS.md)
2. [LICENSE](LICENSE)
