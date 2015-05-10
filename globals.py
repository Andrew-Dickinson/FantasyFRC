#!/usr/bin/python
# -*- coding: utf-8 -*-

from datastore_classes import RootTeam, Account, GlobalSettings
from datetime import date
import logging
import jinja2
import os

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

year = "2014"  # Used by tba api calls
first_event_wednesday = date(2014, 2, 26)  # used to convert timestamps to week numbers
mechanize_timeout = 30.0  # Seconds to wait for mechanize to gather data from tba
overestimate_of_frc_teams = 6000  # Makes getting all the teams in FRC slightly more efficient

draft_rounds = 5  # Number of rounds in a particular draft
draft_time_minutes = 2  # Time per person per round
number_of_locked_teams = 5  # Number of non-transferable teams to have at the top of the rankings

maximum_roster_size = 30  # The maximum number of teams a player can have on their roster
maximum_active_teams = 6  # The maximum number of teams a player can have active at once

number_of_official_weeks = 6  # Used in general to iterate over schedule
number_of_round_robin_weeks = 6  # Used to create the schedule

#Used to store information for each player's success in each week
record_win = 'W'
record_loss = 'L'
record_tie = 'T'
record_bye = 'B'

#Used internally to give points to each player based on their performance in a given week
league_points_per_win = 2
league_points_per_tie = 1
league_points_per_loss = 0
league_points_per_bye = 0

#Used as the name of a league to indicate that the league name and leave league button should not be displayed
draft_started_sentinel = "f35f0a1295224ac2a1d21c8ce9768a70" #UUID generated from uuidgenerator.net

#The character used to denote a bye week in schedules
schedule_bye_week = '0'

#Used to access tba
app_id = "frc3546:FantasyFRC:v0.1"

#Used to access google's geocode system
google_api_key = "AIzaSyAfJd7wBMespDYqfmMivW7GtMDe1ZRkKbc"

#Number of teams to list on the free agent page
free_agent_pagination = 50

#Used to link to tba.com
public_event_url = "http://www.thebluealliance.com/event/{0}"
public_team_url = "http://www.thebluealliance.com/team/{0}/" + year

#Used to access the tba api
team_url = "http://www.thebluealliance.com/api/v2/team/frc{0}"
teams_url = "http://www.thebluealliance.com/api/v2/event/{0}/teams"
event_url = "http://www.thebluealliance.com/api/v2/event/{0}"
events_url = "http://www.thebluealliance.com/api/v2/events/{0}"
rankings_url = "http://www.thebluealliance.com/api/v2/event/{0}/rankings"
team_events_url = "http://www.thebluealliance.com/api/v2/team/frc{0}/" + year + "/events"
team_event_awards_url = "http://www.thebluealliance.com/api/v2/team/frc{0}/event/{1}/awards"
event_matches_url = "http://www.thebluealliance.com/api/v2/event/{0}/matches"

#Used to access google's geocode service
gecode_url = "https://maps.googleapis.com/maps/api/geocode/json?key=" + google_api_key + "&address={0}"


def get_team_list():
    """Accesses the datastore to return a team list"""
    team_list = RootTeam.query().fetch(overestimate_of_frc_teams)
    team_numbers = []
    for team in team_list:
        team_numbers.append(team.key.id())
    return team_numbers

def get_team_list_per_event(event_id):
    """Accesses the datastore to return a team list for an event"""
    team_list = RootTeam.query().filter(RootTeam.events == event_id).fetch()
    team_numbers = []
    for team in team_list:
        team_numbers.append(team.key.id())
    return team_numbers

def get_or_create_account(user):
    """Called periodically (all pages) to get the current user, or to create a new one if null"""
    account = Account.get_or_insert(user.user_id(), nickname=user.nickname(), league='0')
    if not account.league:  # Makes compiler happy. Equivalent to "if account.league == None:"
        account.league = '0'
        account.put()
    return account

def display_error_page(self, referrer, message):
    template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
    self.response.write(template.render({'Message': message, 'Back_Link': referrer}))

def get_current_editable_week():
    global_settings = GlobalSettings.get_or_insert('0', editable_week=None)
    if not global_settings.editable_week:
        global_settings.editable_week = 1
        global_settings.put()
    return global_settings.editable_week

def set_current_editable_week(week_num):
    global_settings = GlobalSettings.get_or_insert('0')
    global_settings.editable_week = week_num
    global_settings.put()