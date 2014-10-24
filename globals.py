#!/usr/bin/python
# -*- coding: utf-8 -*-

from datastore_classes import Root_Team, Account
from datetime import date

year = "2014"
first_event_wednesday = date(2014, 2, 26)
mechanize_timeout = 30.0 #Seconds

alliance_size = 2
draft_time_minutes = 0.5

number_of_offical_weeks = 7

app_id = "frc3546:FantasyFRC:v0.1"

public_event_url = "http://www.thebluealliance.com/event/%s"
public_team_url = "http://www.thebluealliance.com/team/%s/" + year

team_url = "http://www.thebluealliance.com/api/v2/team/frc%s"
teams_url = "http://www.thebluealliance.com/api/v2/event/%s/teams"
events_url = "http://www.thebluealliance.com/api/v2/events/%s"
rankings_url = "http://www.thebluealliance.com/api/v2/event/%s/rankings"
team_events_url = "http://www.thebluealliance.com/api/v2/team/frc%s/" + year + "/events"
team_event_awards_url = "http://www.thebluealliance.com/api/v2/team/frc%s/event/%s/awards"
event_matches_url = "http://www.thebluealliance.com/api/v2/event/%s/matches"

current_lineup_identifier = 'c'



def get_team_list():
    """Accesses the datastore to return a team list for an event"""
    team_list = Root_Team.query().fetch()
    team_numbers = []
    for team in team_list:
        team_numbers.append(team.key.id())
    return team_numbers

def get_team_list_per_event(event_id):
    """Accesses the datastore to return a team list for an event"""
    team_list = Root_Team.query().filter(Root_Team.events == event_id).fetch()
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
