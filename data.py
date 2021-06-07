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

class SenateData():

    def __init__(self, congress_num, session_num):
        c = Census(CENSUS_API_KEY)
        state_pop_data = c.acs5.state(
            ("NAME", CENSUS_POPULATION_CODE), Census.ALL
        )
        state_pop_data = pd.DataFrame.from_dict(state_pop_data)
        # will need the state abbreviation for the senate.gov data 
        state_pop_data.loc[:, "state"] = (
            state_pop_data["NAME"].map(lambda x: states.lookup(x).abbr)
        )

        self.us_pop_data = c.acs5.us(("NAME", CENSUS_POPULATION_CODE))
        self.state_pop_data = state_pop_data

        self.congress_num = congress_num
        self.session_num = session_num

    def get_senate_list(self):
        """ Gets a list of all Senate roll call votes from senate.gov """
        url = (
            "https://www.senate.gov/legislative/LIS/roll_call_lists/"
            f"vote_menu_{self.congress_num}_{self.session_num}.xml"
        )
        resp_data = requests.get(url)
        return xmltodict.parse(resp_data.content)


    def get_senate_vote(self, vote_num):
        """ Gets detailed data on a particular Senate vote """
        url = (
            "https://www.senate.gov/legislative/LIS/roll_call_votes/"
            f"vote{self.congress_num}{self.session_num}/"
            f"vote_{self.congress_num}_{self.session_num}_{vote_num}.xml"
        )
        resp_data = requests.get(url)
        return xmltodict.parse(resp_data.content)


    def get_voters(self, vote_members):
        """ Takes a list of members from vote_detail JSON. """
        voters = pd.json_normalize(vote_members, "member")
        voters = voters.join(
            self.state_pop_data.set_index("state")[[CENSUS_POPULATION_CODE]],
            on="state"
        )
        return voters

    def get_vote_rep(self, voters):
        """ Gets the % of the population represented in the vote. """
        votes = voters.groupby("vote_cast")[[CENSUS_POPULATION_CODE]].sum()
        votes.loc[:, "rep"] = (
            votes[CENSUS_POPULATION_CODE]
            / (int(self.us_pop_data[0][CENSUS_POPULATION_CODE]) * 2)
        )
        votes = votes[["rep"]].to_dict()["rep"]
        for v in ["Yea", "Nay"]:
            if v not in votes:
                votes[v] = 0.0
        return votes

    def get_party_rep(self, voters):
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

    def process_vote(self, vote):
        """ Process a vote into tweet text form """
        tweet_text = ""
        vote_number = vote["vote_number"]
        vote_tally = vote["vote_tally"]
        vote_detail = self.get_senate_vote(vote_number)
        # TODO: Truncate vote_question / vote_result
        if isinstance(vote["question"], dict):
            vote_question = vote["question"]["#text"].lower()
        else:
            vote_question = vote["question"].lower()
        vote_question += (" " + vote["issue"])
        vote_result = vote["result"].upper()
        bill = f"Vote {int(vote_number)} {vote_question}: {vote_result}"
        tweet_text += bill

        voters = self.get_voters(vote_detail["roll_call_vote"]["members"])
        rep = self.get_vote_rep(voters)
        tweet_text += "\n% represented by… "

        for v in ["Yea", "Nay"]:
            per = "{0:.1%}".format(rep[v])
            tally = vote_tally[v.lower() + "s"]
            tweet_text += f"{v.lower()}: {per} ({tally}); "
        party = self.get_party_rep(voters)
        tweet_text += "% bipartisan… {0:.1%}".format(party)
        return tweet_text

if __name__ == "__main__":
    senate_obj = SenateData(CONGRESS_NUMBER, SENATE_SESSION)
    senate_data = senate_obj.get_senate_list()

    for item in senate_data["vote_summary"]["votes"]["vote"][:10]:
        print(senate_obj.process_vote(item))
