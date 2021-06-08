# representabot

<!--- TODO: add links! --> 

## About me

Hi, I am `representabot`. I am a Twitter Bot that tweets regular updates of the latest votes in the U.S. Senate. What makes me different from other places that list congressional votes is that I will also tweet the percentage of the U.S. population represented by yeas and nays. This way, I can track how often this democratic institution is anti-majoritarian. 

## Methodology

### Data sources 

All vote data and vote totals come from the [U.S. Senate](https://senate.gov) website. Data for state population comes from the [Census API](https://api.census.gov).

### Calculating representation

To calculate representation, a state's population is added each time a Senator from that state votes a specific way ("yea" or "nay"). The sum of these two numbers is divided by twice our calculated total of the U.S. population. (I do not include D.C. or Puerto Rico in this calculation, which means our statistic overestimates the percent of total people represented.)

I calculate the population in this way and calculate a "weighted average" so that our representation statistic adds up to 100% when you sum the percentage represented by yeas, nays, and other types of votes. 

### Calculation bipartianship percentage

The bipartisanship percentage is taken as the ratio of the number of yea votes from the minority party on a single vote to the number of yea votes from the majority party on a single vote. Minority and majority party are determined by the votes themselves, not the current or past standing of the U.S. Senate. Votes from Senators labeled as Independent are not concluded in this number. 

Votes where only one party votes "yea" are given a percentage of 0% and votes where every Senator votes "yea" are given a 100%. 

## Setting Me Up

### Requirements 
I can be run from a command line, but I prefer to be hosted somewhere. For no apparent reason, I recommend Google Cloud Functions. Feel free to fork me, tear out my guts, and replace them with your favorite cloud platform instead.

I also store a running memory of my tweets in a CSV file. By default, this file is hosted on a Google Cloud Storage bucket.

See [Google Cloud documentation](https://cloud.google.com/storage/docs/reference/libraries) for more details on setting up Google Cloud services.

### How to run
You can run me with the following command:

```
python bot.py
```
