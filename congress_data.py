import json
import os
import requests

import dotenv
import pandas as pd
import xmltodict

from census import Census
from us import states


dotenv.load_dotenv()
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY")
CONGRESS_NUMBER = os.environ.get("CONGRESS_NUMBER")
SENATE_SESSION = os.environ.get("SENATE_SESSION")
CENSUS_POPULATION_CODE = "B01003_001E"


def get_population_data():
    """ Gets population data from the Census using the Census API """
    c = Census(CENSUS_API_KEY)
    state_pop_data = c.acs5.state(("NAME", CENSUS_POPULATION_CODE), Census.ALL)
    us_pop_data = c.acs5.us(("NAME", CENSUS_POPULATION_CODE))
    return state_pop_data, us_pop_data


def get_senate_list(congress_num, session_num):
    """ Gets a list of all Senate roll call votes from senate.gov """
    url = (
        "https://www.senate.gov/legislative/LIS/roll_call_lists/"
        f"vote_menu_{congress_num}_{session_num}.xml"
    )
    resp_data = requests.get(url)
    return xmltodict.parse(resp_data.content)


def get_senate_vote(congress_num, session_num, vote_num):
    """ Gets detailed data on a particular Senate vote """
    url = (
        "https://www.senate.gov/legislative/LIS/roll_call_votes/"
        f"vote{congress_num}{session_num}/"
        f"vote_{congress_num}_{session_num}_{vote_num}.xml"
    )
    resp_data = requests.get(url)
    return xmltodict.parse(resp_data.content)


if __name__ == "__main__":
    senate_data = get_senate_list(CONGRESS_NUMBER, SENATE_SESSION)
    state_pop_data, us_pop_data = get_population_data()

    for item in senate_data["vote_summary"]["votes"]["vote"]:
        vote_detail = get_senate_vote(
            CONGRESS_NUMBER, SENATE_SESSION, item["vote_number"]
        )
        print(json.dumps(vote_detail["roll_call_vote"]["vote_question_text"], indent=2))
