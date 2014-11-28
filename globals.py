#!/usr/bin/python
# -*- coding: utf-8 -*-

from datastore_classes import RootTeam, Account
from datetime import date
import logging

year = "2014"
first_event_wednesday = date(2014, 2, 26)
mechanize_timeout = 30.0 #Seconds
debug_current_editable_week = 1
overestimate_of_frc_teams = 6000

alliance_size = 5
draft_time_minutes = 2

number_of_official_weeks = 7
number_of_round_robin_weeks = 7

record_win = 'W'
record_loss = 'L'
record_tie = 'T'
record_bye = 'B'

league_points_per_win = 2
league_points_per_tie = 1
league_points_per_loss = 0
league_points_per_bye = 0

schedule_bye_week = '0'

app_id = "frc3546:FantasyFRC:v0.1"

no_data_display = "<i>No Data</i>"

public_event_url = "http://www.thebluealliance.com/event/%s"
public_team_url = "http://www.thebluealliance.com/team/%s/" + year

team_url = "http://www.thebluealliance.com/api/v2/team/frc%s"
teams_url = "http://www.thebluealliance.com/api/v2/event/%s/teams"
event_url = "http://www.thebluealliance.com/api/v2/event/%s"
events_url = "http://www.thebluealliance.com/api/v2/events/%s"
rankings_url = "http://www.thebluealliance.com/api/v2/event/%s/rankings"
team_events_url = "http://www.thebluealliance.com/api/v2/team/frc%s/" + year + "/events"
team_event_awards_url = "http://www.thebluealliance.com/api/v2/team/frc%s/event/%s/awards"
event_matches_url = "http://www.thebluealliance.com/api/v2/event/%s/matches"



def get_team_list():
    """Accesses the datastore to return a team list"""
    team_list = RootTeam.query().fetch(overestimate_of_frc_teams)
    logging.info(team_list)
    team_numbers = []
    for team in team_list:
        team_numbers.append(team.key.id())
    logging.info(team_numbers)
    return team_numbers

def get_team_list_per_event(event_id):
    """Accesses the datastore to return a team list for an event"""
    team_list = RootTeam.query().filter(RootTeam.events == event_id).fetch()
    team_numbers = []
    for team in team_list:
        team_numbers.append(team.key.id())
    return team_numbers

def get_or_create_account(user):
    account = Account.get_or_insert(user.user_id(), nickname=user.nickname(), league='0')
    if account.league == None:
        account.league = '0'
        account.put()
    return account
