import json
import requests

import pandas as pd
import xmltodict

from census import Census
from us import states


CENSUS_API_KEY = "dc5b0c9e8a915b1671f4afb3ac607d4805d62bfc"
CENSUS_POPULATION_CODE = "B01003_001E"
CONGRESS_NUMBER = "117"
SENATE_SESSION = "1"


def get_population_data():
    """ Gets population data from the Census using the Census API """
    c = Census(CENSUS_API_KEY)

    state_pop_data = c.acs5.state(("NAME", CENSUS_POPULATION_CODE), Census.ALL)
    state_pop_data = pd.DataFrame.from_dict(state_pop_data)

    # will need the state abbreviation for the senate.gov data 
    state_pop_data.loc[:, "state"] = (
        state_pop_data["NAME"].map(lambda x: states.lookup(x).abbr)
    )

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


def get_voters(vote_members):
    """ Takes a list of members from vote_detail JSON. """
    voters = pd.json_normalize(vote_members, "member")
    state_pop_data, us_pop_data = get_population_data()
    voters = voters.join(
        state_pop_data.set_index("state")[[CENSUS_POPULATION_CODE]],
        on="state"
    )
    return voters


def get_vote_rep(voters):
    """ Gets the % of the population represented in the vote. """
    votes = voters.groupby("vote_cast")[[CENSUS_POPULATION_CODE]].sum()
    votes.loc[:, "rep"] = (
        votes[CENSUS_POPULATION_CODE]
        / (int(us_pop_data[0][CENSUS_POPULATION_CODE]) * 2)
    )
    votes = votes[["rep"]].to_dict()["rep"]
    for v in ["Yea", "Nay"]:
        if v not in votes:
            votes[v] = 0.0
    return votes


def get_party_rep(voters):
    """ Gets the ratio of Yea votes made by the non-majority party
        to the majority party.
    """
    votes = voters.loc[
        lambda x: (x["party"].isin(["D", "R"])) & (x["vote_cast"] == "Yea")
    ]
    votes = votes.groupby("party")[["lis_member_id"]].count()
    if len(votes) < 2:
        return 0.0
    else:
        return (votes["lis_member_id"].min() / votes["lis_member_id"].max())


if __name__ == "__main__":
    senate_data = get_senate_list(CONGRESS_NUMBER, SENATE_SESSION)
    state_pop_data, us_pop_data = get_population_data()

    for item in senate_data["vote_summary"]["votes"]["vote"][:10]:
        vote_detail = get_senate_vote(
            CONGRESS_NUMBER, SENATE_SESSION, item["vote_number"]
        )
        vote_question = vote_detail["roll_call_vote"]["vote_question_text"]
        vote_result = vote_detail["roll_call_vote"]["vote_result"].upper()
        bill = f"{vote_question}: {vote_result}"
        print(bill)
        voters = get_voters(vote_detail["roll_call_vote"]["members"])
        rep = get_vote_rep(voters)
        print("% represented by...", end=" ")
        for v in ["Yea", "Nay"]:
            per = "{0:.1%}".format(rep[v])
            print(f"{v.lower()}: {per};", end=" ")
        party = get_party_rep(voters)
        print(f"% bipartisan...", "{0:.1%}".format(party))
        print("\n")
