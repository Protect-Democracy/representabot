import pytest

import data as cd


def test_senate_data():
    assert cd.SenateData("117", "1")
    assert cd.SenateData("117", "2")  # How does this fail?


def test_get_senate_list():
    senate_obj = cd.SenateData("116", "1")
    senate_data = senate_obj.get_senate_list()
    assert len(senate_data["vote_summary"]["votes"]["vote"]) == 428


def test_process_votes():
    senate_obj = cd.SenateData("117", "1")
    senate_data = senate_obj.get_senate_list()
    # TODO: Mock the parameter?
    tweet, party_data, vote_data = senate_obj.process_vote(
        senate_data["vote_summary"]["votes"]["vote"][0]
    )
    assert tweet
