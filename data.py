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
        # if we want to change back to including DC later for reasons
        # self.us_pop_data = c.acs5.us(("NAME", CENSUS_POPULATION_CODE))[0][CENSUS_POPULATION_CODE]
        self.state_pop_data = state_pop_data
        self.us_pop_data = self.state_pop_data.loc[
            lambda x: x["state"] != "DC", CENSUS_POPULATION_CODE
        ].sum()

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
            / (int(self.us_pop_data) * 2)
        )
        votes = votes[["rep"]].to_dict()["rep"]
        for v in ["Yea", "Nay"]:
            if v not in votes:
                votes[v] = 0.0
        return votes

    def get_party_rep(self, voters):
        """ Returns the vote count on a measure and the major party breakdown of those votes. """
        idx = "lis_member_id"
        yea_votes = voters.loc[lambda x: x["vote_cast"] == "Yea"]
        nay_votes = voters.loc[lambda x: x["vote_cast"] == "Nay"]  
        
        vote_dict = {}
        
        vote_dict["yea_vote"] = {}
        vote_dict["yea_vote"]["total"] = yea_votes[idx].count()
         
        vote_dict["nay_vote"] = {}
        vote_dict["nay_vote"]["total"] = nay_votes[idx].count()
        
        for p in ["D", "R"]:
            vote_dict["yea_vote"][p] = yea_votes.query("party == @p")[idx].count()
            vote_dict["nay_vote"][p] = nay_votes.query("party == @p")[idx].count() 
                                  
        return vote_dict
    
    def process_counts(self, voters, vote_result):
        """ Takes representation and party counts and cleans them for text. """
        text = ""
        v = "yea"
        rep = self.get_vote_rep(voters)
        party = self.get_party_rep(voters)
        
        per = "{0:.1%}".format(rep[v.title()])
        text += f"{per} of the country represented by {v} votes"
        
        if (rep[v.title()] >= 0.5) & (vote_result == "REJECTED"): 
            text += f", but the measure was still rejected. ⚠️"
        else:
            text += f". The measure was {vote_result.lower()}."
        
        return text
            
    def process_vote(self, vote):
        """ Process a vote into tweet text form """
        tweet_text = ""
        vote_number = vote["vote_number"]
        vote_tally = vote["vote_tally"]
        vote_detail = self.get_senate_vote(vote_number)

        if isinstance(vote["question"], dict):
            vote_question = vote["question"]["#text"]
        else:
            vote_question = vote["question"]
        vote_question += (" " + vote["issue"])
        vote_result = vote["result"].upper()
        bill = f"{vote_question} (vote #{int(vote_number)}): "
        tweet_text += bill
        voters = self.get_voters(vote_detail["roll_call_vote"]["members"])
        tweet_text += self.process_counts(voters, vote_result)
        
        return tweet_text

if __name__ == "__main__":
    senate_obj = SenateData(CONGRESS_NUMBER, SENATE_SESSION)
    senate_data = senate_obj.get_senate_list()

    for item in senate_data["vote_summary"]["votes"]["vote"][:10]:
        print(senate_obj.process_vote(item))
