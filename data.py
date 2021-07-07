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
CENSUS_POPULATION_CODE = "B01003_001E"


def flatten(current: dict, key: str = None, result: dict = {}):
    """Recursively flatten a dictionary based on its key values"""
    if isinstance(current, dict):
        for k in current:
            new_key = f"{key}_{k}" if key else k
            flatten(current[k], new_key, result)
    else:
        result[key] = current
    return result


class DoNotTweetException(Exception):
    pass


class SenateData:
    QUESTIONS = [
        "motion",
        "bill",
        "amendment",
        "resolution",
        "nomination",
        "veto",
    ]

    def __init__(self, congress_num, session_num):
        c = Census(CENSUS_API_KEY)
        state_pop_data = c.acs5.state(
            ("NAME", CENSUS_POPULATION_CODE), Census.ALL
        )
        state_pop_data = pd.DataFrame.from_dict(state_pop_data)
        # will need the state abbreviation for the senate.gov data
        state_pop_data.loc[:, "state"] = state_pop_data["NAME"].map(
            lambda x: states.lookup(x).abbr
        )
        # if we want to change back to including DC later for reasons
        # self.us_pop_data = c.acs5.us(("NAME", CENSUS_POPULATION_CODE))[0][CENSUS_POPULATION_CODE]
        self.state_pop_data = state_pop_data
        self.us_pop_data = self.state_pop_data.loc[
            lambda x: ~x["state"].isin(["DC", "PR"]), CENSUS_POPULATION_CODE
        ].sum()

        self.congress_num = congress_num
        self.session_num = session_num

    def get_senate_list(self):
        """Gets a list of all Senate roll call votes from senate.gov"""
        url = (
            "https://www.senate.gov/legislative/LIS/roll_call_lists/"
            f"vote_menu_{self.congress_num}_{self.session_num}.xml"
        )
        resp_data = requests.get(url)
        return xmltodict.parse(resp_data.content)

    def get_senate_vote(self, vote_num):
        """Gets detailed data on a particular Senate vote"""
        url = (
            "https://www.senate.gov/legislative/LIS/roll_call_votes/"
            f"vote{self.congress_num}{self.session_num}/"
            f"vote_{self.congress_num}_{self.session_num}_{vote_num}.xml"
        )
        resp_data = requests.get(url)
        return xmltodict.parse(resp_data.content)

    def get_voters(self, vote_members):
        """Takes a list of members from vote_detail JSON."""
        voters = pd.json_normalize(vote_members, "member")
        voters = voters.join(
            self.state_pop_data.set_index("state")[[CENSUS_POPULATION_CODE]],
            on="state",
        )
        return voters

    def get_vote_rep(self, voters):
        """Gets the % of the population represented in the vote."""
        votes = voters.groupby("vote_cast")[[CENSUS_POPULATION_CODE]].sum()
        votes.loc[:, "rep"] = votes[CENSUS_POPULATION_CODE] / (
            int(self.us_pop_data) * 2
        )
        votes = votes[["rep"]].to_dict()["rep"]
        for v in ["Yea", "Nay", "Abstain"]:
            if v not in votes:
                votes[v] = 0.0
        return votes

    def get_party_rep(self, voters):
        """Returns the vote count on a measure and the major party breakdown of those votes."""
        idx = "lis_member_id"
        yea_votes = voters.loc[lambda x: x["vote_cast"] == "Yea"]
        nay_votes = voters.loc[lambda x: x["vote_cast"] == "Nay"]
        abstain_votes = voters.loc[
            lambda x: ~x["vote_cast"].isin(["Yea", "Nay"])
        ]

        vote_dict = {}

        vote_dict["yea_vote"] = {}
        vote_dict["yea_vote"]["total"] = yea_votes[idx].count()

        vote_dict["nay_vote"] = {}
        vote_dict["nay_vote"]["total"] = nay_votes[idx].count()

        vote_dict["abstain_vote"] = {}
        vote_dict["abstain_vote"]["total"] = abstain_votes[idx].count()

        for p in ["D", "R"]:
            vote_dict["yea_vote"][p] = yea_votes.query("party == @p")[
                idx
            ].count()
            vote_dict["nay_vote"][p] = nay_votes.query("party == @p")[
                idx
            ].count()
            vote_dict["abstain_vote"][p] = abstain_votes.query("party == @p")[
                idx
            ].count()

        return vote_dict

    def process_detail_text(self, vote_rep, party_rep):
        """Takes representation and party counts and cleans them for text."""
        text = ""

        for v in ["yea", "nay", "abstain"]:
            p = "{0:.1%}".format(vote_rep[v.title()])
            total_vote = party_rep[f"{v}_vote"]["total"]
            d_vote = party_rep[f"{v}_vote"]["D"]
            r_vote = party_rep[f"{v}_vote"]["R"]
            i_vote = total_vote - (d_vote + r_vote)

            if total_vote == 1:
                votes = "vote"
            else:
                votes = "votes"

            if v == "abstain":
                li = f"😶 No vote: {p} ... {total_vote} {votes} ({d_vote}-D, {r_vote}-R, {i_vote}-I)"
            elif v == "nay":
                li = f"❎ {v.title()}s: {p} ... {total_vote} {votes} ({d_vote}-D, {r_vote}-R, {i_vote}-I)"
            else:
                li = f"✅ {v.title()}s: {p} of the country represented by {total_vote} {votes} ({d_vote}-D, {r_vote}-R, {i_vote}-I)"

            text += f"{li}\n\n"

        return text

    def process_link_text(self, vote_number):
        """Creates a source link to the senate.gov website."""
        url = (
            "https://www.senate.gov/legislative/LIS/roll_call_lists/roll_call_vote_cfm.cfm?"
            f"congress={self.congress_num}&session={self.session_num}&vote={vote_number}"
        )
        return url

    def process_vote_text(self, question, vote_question, vote, vote_detail):
        """Processes a vote into the relevant syntax for tweeting."""

        def process_name(name):
            """Helper function for process_measure."""
            name = name[: name.find(",")]
            name = name.split()
            return name[0][0] + ". " + name[-1]

        def process_measure():
            """Helper function for process_vote_text."""
            text = ""
            # TODO: make these separate functions?
            if question == "motion":
                if len(vote_question.split()) > 3:
                    if "PN" in vote_issue:
                        nominee = process_name(
                            vote_detail["roll_call_vote"]["vote_document_text"]
                        )
                        text += f"{vote_question.capitalize()} the {nominee} nomination was {vote_result}"
                    elif (
                        "amdt"
                        in vote_detail["roll_call_vote"]["vote_title"].lower()
                    ):
                        text += f"{vote_question.capitalize()} (an amendment to {vote_issue}) was {vote_result}"
                    else:
                        text += f"{vote_question.capitalize()} ({vote_issue}) was {vote_result}"
                else:
                    text += f"{vote_question.capitalize()}"
                    if "PN" in vote_issue:
                        nominee = process_name(
                            vote_detail["roll_call_vote"]["vote_document_text"]
                        )
                        text += f" on nominating {nominee} "
                    elif (
                        "waive"
                        in vote_detail["roll_call_vote"]["vote_title"].lower()
                    ):
                        text += " to waive "
                        if (
                            "amdt"
                            in vote_detail["roll_call_vote"][
                                "vote_title"
                            ].lower()
                        ):
                            text += f"re: an Amdt. to {vote_issue} "
                        else:
                            text += f""
                    else:
                        text += f" for {vote_issue} "
                    text += f"was {vote_result}"
            elif question == "bill":
                text += f"The bill {vote_issue} was {vote_result}"
            elif question == "amendment":
                amend = vote["question"]["measure"]
                text += (
                    f"The amendment {amend} for {vote_issue} was {vote_result}"
                )
            elif question == "resolution":
                text += f"{vote_question.capitalize()} for {vote_issue} was {vote_result}"
            elif question == "nomination":
                nominee = process_name(
                    vote_detail["roll_call_vote"]["vote_document_text"]
                )
                text += f"The nomination for {nominee} was {vote_result}"
            elif question == "veto":
                text += f"The veto on {vote_issue} was {vote_result[5:]}"

            return text

        vote_issue = vote["issue"]
        vote_result = vote["result"].lower()
        vote_number = vote["vote_number"]

        return process_measure()

    def process_vote(self, vote):
        """Process a vote into tweet text form"""

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
        voters.loc[
            lambda x: ~x["vote_cast"].isin(["Yea", "Nay"]), "vote_cast"
        ] = "Abstain"
        date = process_date(vote_detail["roll_call_vote"]["vote_date"])

        if isinstance(vote_question, dict):
            vote_question = vote_question["#text"]
        else:
            vote_question = vote_question

        if vote_question is None:
            raise DoNotTweetException

        vote_question = vote_question.lower()[3:]
        vote_question = (
            vote_question[: vote_question.find("(") - 1]
            if vote_question.find("(") > 0
            else vote_question
        )
        vote_question = (
            "the " + vote_question
            if vote_question[:3] != "the"
            else vote_question
        )

        # votes without an "issue" don't have a subject
        # this was an odd edge case that's accounted for here
        # these votes are not voting on anything, or else they would have an "issue"
        # of the few cases that fit here, I think they're procedural votes
        if len(vote["issue"]) < 1:
            raise DoNotTweetException
        elif vote["issue"] == "n/a":
            raise DoNotTweetException
        else:
            q = [
                question
                for question in self.QUESTIONS
                if (question in vote_question)
            ]
            if q:
                # might change in future
                # tweet_text += f"Vote #{int(vote_number)} on {date}: "
                tweet_text += self.process_vote_text(
                    q[0], vote_question, vote, vote_detail
                )
                tweet_text += ".\n\n"

                party_rep = self.get_party_rep(voters)
                vote_rep = self.get_vote_rep(voters)
                tweet_text += self.process_detail_text(vote_rep, party_rep)

                link = self.process_link_text(vote_number)
                tweet_text += f"src: {link}"
                party_rep = flatten(party_rep, result={})
                vote_rep = flatten(vote_rep, result={})
                return tweet_text, party_rep, vote_rep
            else:
                # Vote does not match any of the desired questions
                raise DoNotTweetException


if __name__ == "__main__":
    senate_obj = SenateData("117", "1")
    senate_data = senate_obj.get_senate_list()
    examples = []
    tweets = []

    for item in senate_data["vote_summary"]["votes"]["vote"]:
        try:
            tweet, party_data, vote_data = senate_obj.process_vote(item)
            if isinstance(item["question"], dict):
                q = item["question"]["#text"]
            else:
                q = item["question"]
            if q not in examples:
                tweets = tweets + [tweet]
                examples = examples + [q]
                result = f"[{q}]:\n\n{tweet}\n\n"
                print(result)
        except DoNotTweetException:
            pass
    # check to see if format meets current length limits on twitter
    # and if longest tweet fits
    sample_tweet = pd.DataFrame({"question": examples, "tweet": tweets})
    sample_tweet["tweet_len"] = sample_tweet["tweet"].map(len)
    longest_tweet = sample_tweet["tweet"][sample_tweet.tweet_len.argmax()]
    result = (
        "maximum tweet character length: ~365\n"
        f"mean length: {round(sample_tweet.tweet_len.mean())}\n"
        f"max length: {sample_tweet.tweet_len.max()}\n"
        f"min length: {sample_tweet.tweet_len.min()}\n"
        f"longest tweet from this group:\n\n{longest_tweet}"
    )
    print(result)
