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
QUESTIONS = [
    "motion", "bill", "amendment", "resolution", "nomination", "veto", 
    ]

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
    
    def process_detail_text(self, vote_rep, party_rep):
        """ Takes representation and party counts and cleans them for text. """
        text = ""
        
        v = "yea"
        p = "{0:.1%}".format(vote_rep[v.title()])
        
        total_vote = party_rep[f"{v}_vote"]["total"]
        d_vote = party_rep[f"{v}_vote"]["D"]
        r_vote = party_rep[f"{v}_vote"]["R"]
        
        percent = f"{p} of the country represented by {total_vote} {v} vote(s)."
        party = f"{d_vote} Democrat(s) and {r_vote} Republican(s) voted {v}."
        
        text += f"🚻  {percent}"
        text += "\n\n"
        text += f"🗳  {party}"
        
        return text
        
    def process_link_text(self, vote_number):
        """ Creates a source link to the senate.gov website. """
        url = (
            "https://www.senate.gov/legislative/LIS/roll_call_lists/roll_call_vote_cfm.cfm?"
            f"congress={CONGRESS_NUMBER}&session={SENATE_SESSION}&vote={vote_number}"
            )
        return url

    def process_vote_text(self, question, vote_question, vote, vote_detail):
        """ Processes a vote into the relevant syntax for tweeting. """
        
        def process_name(name):
            """ Helper function for process_measure. """
            name = name[:name.find(",")]
            name = name.split()
            return name[0][0] + ". " + name[-1]
        
        def process_measure():
            """ Helper function for process_vote_text. """
            text = ""
            # TODO: make these separate functions? 
            if question == "motion":
                if len(vote_question.split()) > 3:
                    text += f"{vote_question} was {vote_result}"
                else:
                    text += f"{vote_question} for {vote_issue}"
                    if "PN" in vote_issue:
                        nominee = process_name(vote_detail["roll_call_vote"]["vote_document_text"])
                        text += f" (nomination of {nominee}) "
                    else:
                        text += " "
                    text += f"was {vote_result}"
            elif question == "bill":
                text += f"the bill {vote_issue} was {vote_result}"
            elif question == "amendment":
                amend = vote["question"]["measure"]
                text += f"the amendment {amend} for {vote_issue} was {vote_result}"
            elif question == "resolution":
                text += f"{vote_question} for {vote_issue} was {vote_result}"
            elif question == "nomination":
                nominee = process_name(vote_detail["roll_call_vote"]["vote_document_text"])
                text += f"the nomination for {nominee} ({vote_issue}) was {vote_result}"
            elif question == "veto":
                text += f"the veto on {vote_issue} was {vote_result[6:]}"
                
            return text
        
        vote_issue = vote["issue"]
        vote_result = vote["result"].lower()
        vote_number = vote["vote_number"]
        
        return process_measure()
        
            
    def process_vote(self, vote):
        """ Process a vote into tweet text form """
        
        def process_date(date_str):
            date = pd.to_datetime(date_str)
            return date.strftime("%B %d, %Y")
        
        tweet_text = ""
        vote_number = vote["vote_number"]
        vote_tally = vote["vote_tally"]
        vote_question = vote["question"]
        vote_result = vote["result"]
        vote_detail = self.get_senate_vote(vote_number)
        voters = self.get_voters(vote_detail["roll_call_vote"]["members"])
        date = process_date(vote_detail["roll_call_vote"]["vote_date"])

        if isinstance(vote_question, dict):
            vote_question = vote_question["#text"]
        else:
            vote_question = vote_question
            
        vote_question = vote_question.lower()[3:]
        vote_question = vote_question[:vote_question.find('(')] if vote_question.find('(') > 0 else vote_question
        
        if len(vote["issue"]) < 1:
            raise Exception
        else:
            for q in QUESTIONS:
                if q in vote_question:
                    # TODO: how to save data for db? pass row as a list?
                    tweet_text += f"Vote #{int(vote_number)} on {date}: "
                    tweet_text += self.process_vote_text(q, vote_question, vote, vote_detail)
                    tweet_text += ".\n\n"
                    
                    party_rep = self.get_party_rep(voters)
                    vote_rep = self.get_vote_rep(voters)
                    tweet_text += self.process_detail_text(vote_rep, party_rep)
                    tweet_text += "\n\n"
                    
                    link = self.process_link_text(vote_number)
                    tweet_text += f"Source: {link}"
                    return tweet_text
                else: 
                    pass
        # TODO: make exception for invalid measures 
        raise Exception
        

if __name__ == "__main__":
    senate_obj = SenateData(CONGRESS_NUMBER, SENATE_SESSION)
    senate_data = senate_obj.get_senate_list()

    for item in senate_data["vote_summary"]["votes"]["vote"][:10]:
        print(senate_obj.process_vote(item))
        print("\n")
