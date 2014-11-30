#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import json
import logging
from random import shuffle
import datetime
import calendar

import globals
from globals import get_team_list

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.api import users

from datastore_classes import RootTeam, league_key, Choice, Lineup, Choice_key, account_key, Account, lineup_key, DraftPick, draft_pick_key

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def start_draft(league_id):
    """Sets up to prepare for a draft"""
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    shuffle(league_players)  # Randomize the order of the draft

    number_of_players = len(league_players)
    for draft_round in range(0, globals.alliance_size):
        for i, player in enumerate(league_players):
            pick_key = draft_pick_key(league_key(league_id), str(number_of_players * draft_round + i + 1))
            pick = DraftPick.get_or_insert(pick_key.id(), parent=pick_key.parent())
            pick.player = player.key.urlsafe()
            pick.put()
        league = league_key(league_id).get()
    league.draft_current_position = 0
    league.put()


def get_lat_lng_json():
    team_data = []
    teams = RootTeam.query().fetch()
    for team in teams:
        team_data.append({"number": team.key.id(),
                          "lat": float(team.latlon.split(',')[0]),
                          "lon": float(team.latlon.split(',')[1])})
    extra_stupid_layer = {'data': team_data}
    return json.dumps(extra_stupid_layer)

def make_schedule_fit(original_schedule):
    """Takes a schedule and truncates or expands it as necessary.
        Is only fair if the original schedule is randomly generated"""
    desired_length = globals.number_of_round_robin_weeks
    if len(original_schedule) < desired_length:
        return make_schedule_fit(original_schedule + original_schedule)
    elif len(original_schedule) > desired_length:
        del original_schedule[desired_length:]
        return original_schedule
    elif len(original_schedule) == desired_length:
        return original_schedule


def generate_schedule(league_id):
    """Generates and distributes a schedule based on a round robin system"""
    player_ids_list = []

    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    for player in league_players:
        player_ids_list.append(player.key.id())

    logging.info(player_ids_list)
    shuffle(player_ids_list)
    if len(player_ids_list) % 2 == 1:  # Check if the number of players is odd
        player_ids_list.insert(0, globals.schedule_bye_week)  # Add 0 to represent bye week, added to beginning to solve last player issue
    number_of_players = len(player_ids_list)

    if number_of_players > 2:
        #Now that there's an even number of teams, use a round robin system to assign teams to weeks
        for player_num, player_id in enumerate(player_ids_list, start=1):
            if player_id != '0' and player_num != number_of_players:
                player = account_key(player_id).get()
                schedule = []
                for week in range(1, number_of_players):
                    opponent = (week + (number_of_players - 1) - player_num) % (number_of_players - 1)
                    if opponent == player_num - 1:
                        opponent = number_of_players - 1

                    schedule.append(player_ids_list[opponent])

                #Confirm schedule length is appropriate
                schedule = make_schedule_fit(schedule)
                player.schedule = schedule
                player.put()

        #For the last player, whose schedule doesn't follow the same pattern
        last_player = account_key(player_ids_list[number_of_players - 1]).get()
        last_player_schedule = []
        for week in range(1, number_of_players + 1):
            #This equation comes from a mathematica document. Truss me about it - 2014 season
            last_player_schedule.append(player_ids_list[int(.25*((-1)**week) *
                                        ((number_of_players - 1) +
                                        (number_of_players - 3)*((-1)**week) +
                                        2*((-1)**week)*week))])
        last_player_schedule = make_schedule_fit(last_player_schedule)
        last_player.schedule = last_player_schedule
        logging.info(last_player_schedule)
        last_player.put()
    elif number_of_players == 2:
        #If there's only two players, they just constantly play each other
        player1 = league_players[0]
        schedule1 = []
        player2 = league_players[1]
        schedule2 = []
        for week in range(1, globals.number_of_round_robin_weeks + 1):
            schedule1.append(player_ids_list[0])
            schedule2.append(player_ids_list[1])
        player1.schedule = schedule1
        player2.schedule = schedule2
        player1.put()
        player2.put()


def get_taken_teams(league_id):
    """Returns a list of taken teams based on a league and event id"""
    taken_teams = []
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()

    for player in league_players:
        choice = choice = Choice.get_or_insert(league_id, parent=player.key)
        logging.info(choice)
        if choice:
            for team in choice.current_team_roster:
                taken_teams.append(str(team))
    return taken_teams

def isValidTeam(team, league_id):
        """Parses and returns whether a team exists and is not taken"""
        team_list = get_team_list()
        taken_list = get_taken_teams(league_id)
        try:
            number = int(team)
        except:
            return "Invalid number"
        if str(team) in taken_list:
            return "Team already taken"
        if not (str(number) in team_list):
            return "Team does not exist"
        return "Good" #Will indicate no errors

def setup_lineup(id, choice):
    lineup = Lineup.get_or_insert(lineup_key(choice.key, id).id(), parent=choice.key)
    #Only initialize if its' empty
    if lineup.active_teams == None:
        lineup.active_teams = []
    lineup.put()

def setup_for_next_pick(league_id):
    league = league_key(league_id).get()
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    number_of_picks = len(league_players) * globals.alliance_size
    if league.draft_current_position == number_of_picks: #See if the draft is over
        close_draft(league_id)
    else:
        league.draft_current_position = league.draft_current_position + 1
        league.draft_current_timeout = datetime.datetime.utcnow() + datetime.timedelta(minutes = globals.draft_time_minutes)
        league.put()

def close_draft(league_id):
    league = league_key(league_id).get()
    league.draft_current_position = -1  # Indicate the draft is over
    league.draft_current_timeout = None
    league.put()

    #Build a schedule
    generate_schedule(league_id)

    #Initialize requirements for bench/active system and distribute a schedule
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    for player in league_players:
        #For the active system
        choice = Choice.get_or_insert(league_id, parent=player.key)
        for i in range(1, globals.number_of_official_weeks + 1):
            setup_lineup(i, choice)  # Initialize weekly lineups
            player.record.append('')
        player.put()

class Draft_Page(webapp2.RequestHandler):

    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        if league_id != '0':
            #Make check to see if the time for the current pick has expired
            current_time = datetime.datetime.utcnow()
            current_timeout = league_key(league_id).get().draft_current_timeout
            draft_pick = draft_pick_key(league_key(league_id), league_key(league_id).get().draft_current_position).get()
            if current_timeout:
                if current_time > current_timeout: #The time has expired
                    logging.info("Forefit")
                    draft_pick.team = 0 #Set the pick to indicate it was forefited
                    draft_pick.put()
                    setup_for_next_pick(league_id) #Move the pick along to the next person


            #Display update text for the status of the last choice update
            update_text = self.request.get('updated')
            if self.request.get('updated') == "Good":
                update_text = "Team added successfully"



            league_player_query = Account.query(Account.league == league_id)
            league_players = league_player_query.fetch()

            draft_board = []
            player_list = []
            for player in league_players:
                player_list.append(player.nickname)

            number_of_picks = len(league_players) * globals.alliance_size
            for position in range(1, number_of_picks + 1):
                pick = draft_pick_key(league_key(league_id), position).get()

                username = (((position % len(league_players)) - 1) % len(league_players))
                draft_round = int((position-1)/len(league_players))
                if username == 0:
                    draft_board.append([])
                    for i in range(0, len(league_players)):
                        draft_board[draft_round].append('-')
                if pick and pick.team != None:
                    draft_board[draft_round][username] = str(pick.team)
                    if pick.team == 0:
                        draft_board[draft_round][username] = "<i>Forfeited</i>"
                else:
                    draft_board[draft_round][username] = "<i>TBD</i>"


            if league_id != '0':
                league_name = league_key(league_id).get().name
            else:
                league_name = ""

            users_turn = False
            picking_user = ""
            draft_pick = draft_pick_key(league_key(league_id), league_key(league_id).get().draft_current_position).get()
            if draft_pick:
                users_turn = (draft_pick.player == account.key.urlsafe())
                picking_user = ndb.Key(urlsafe=draft_pick.player).get().nickname

            current_unix_timeout = None
            if current_timeout:
                current_unix_timeout = calendar.timegm(current_timeout.timetuple())

            current_position = league_key(league_id).get().draft_current_position
            draft_status = "Mid"
            if current_position == 0:
                draft_status = "Pre"
            elif current_position == -1:
                draft_status = "Post"
            else:
                draft_status = "Mid"

            team_map_data = get_lat_lng_json()

            #Send html data to browser
            template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'draft_board': draft_board,
                        'player_list': player_list,
                        'update_text': update_text,
                        'league_name': league_name,
                        'users_turn': users_turn,
                        'picking_user': picking_user,
                        'current_unix_timeout': current_unix_timeout,
                        'draft_status': draft_status,
                        'team_map_data': team_map_data,
                        }
            template = JINJA_ENVIRONMENT.get_template('templates/draft_main.html')
            self.response.write(template.render(template_values))
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
            self.response.write(template.render({'Message':'Must be a member of a league to perform this action'}))

class Start_Draft(webapp2.RequestHandler):
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league
        league = league_key(league_id).get()

        league_comissioner = league.key.id()
        if league_comissioner == user_id:
            if league.draft_current_position == 0:
                start_draft(league_id)
                setup_for_next_pick(league_id)
                self.redirect('/draft/')
            else:
                template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
                self.response.write(template.render({'Message':"Draft is already completed or is in progress"}))
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
            self.response.write(template.render({'Message':"Only the league commissioner may perform this action"}))

class Submit_Draft_Pick(webapp2.RequestHandler):

    def post(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        selection_error = ""
        league_entity = league_key(league_id).get()
        current_position = league_entity.draft_current_position
        current_timeout = league_entity.draft_current_timeout
        current_time = datetime.datetime.utcnow()

        if current_position != 0 and current_position != -1: #Don't process if draft is over or yet to begin
            current_pick = draft_pick_key(league_entity.key, current_position).get()
            if current_pick.player == account.key.urlsafe(): #Check that the calling player is actually within their turn
                if current_time < current_timeout: #Check that the calling player is within their time constraints
                    #Get the new team from the post header
                    new_team = self.request.get('team')

                    #Validate the selection
                    selection_error = isValidTeam(new_team, league_id)
                    if selection_error == "Good":
                        #S'all good, update the datastore
                        current_pick.team = int(new_team)
                        current_pick.put()
                        #Add the team to the user's roster
                        user_choice = Choice.get_or_insert(league_id, parent=account.key)
                        if user_choice.current_team_roster == None:
                            user_choice.current_team_roster = []
                        user_choice.current_team_roster.append(int(new_team))
                        user_choice.put()
                        #Move the draft along
                        setup_for_next_pick(league_id)
                else:
                    selection_error = "The time for your selection has expired"
            else:
                selection_error = "It is not your turn to make a selection"
        else:
            selection_error = "Draft is not currently in session"

        #Display the draft main page with status
        self.redirect('/draft/?updated=' + selection_error)


class Pick_up_Page(webapp2.RequestHandler):

    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Force user login
        if user is None:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            #Current user's id, used to identify their data
            user_id = user.user_id()
            logout_url = users.create_logout_url('/')

            account = globals.get_or_create_account(user)
            league_id = account.league

            #Get user's choices for the current league
            find_Choice_key = Choice_key(account_key(user_id), str(league_id))
            found_Choice = find_Choice_key.get()

            #Display update text for the status of the last choice update
            update_text = self.request.get('updated')
            if self.request.get('updated') == "Good":
                update_text = "Team added successfully"

            #Display the user's current roster
            user_roster = []
            if found_Choice:
                user_roster = found_Choice.current_team_roster


            #Get list of players in the league and their choices
            league_table = [{'player_team': 'Roster', 'player_name': 'Player'}]
            league_player_query = Account.query(Account.league == league_id)
            league_players = league_player_query.fetch() #league_player_query.order(Account.nickname).fetch()
            for player in league_players:
                choice = Choice_key(account_key(player.key.id()), league_id).get()
                if choice:
                    league_table.append({'player_team': str(choice.current_team_roster), 'player_name': player.nickname})
                else:
                    league_table.append({'player_team': 'None', 'player_name': player.nickname})

            if league_id != '0':
                league_name = league_key(league_id).get().name
            else:
                league_name = ""

            #Send html data to browser
            template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'update_text': update_text,
                        'league_table': league_table,
                        'league_name': league_name,
                        'roster': user_roster,
                        }
            template = JINJA_ENVIRONMENT.get_template('templates/pick_up_main.html')
            self.response.write(template.render(template_values))

class Submit_Pick(webapp2.RequestHandler):


    def post(self):
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        find_Choice_key = Choice_key(account_key(user_id), str(league_id))
        post_Choice_key = find_Choice_key

        new_team = self.request.get('team')

        selection_error = isValidTeam(new_team, post_Choice_key.parent().get().league)

        #Form data into entity and submit
        post_Choice = Choice.get_or_insert(post_Choice_key.id(), parent=post_Choice_key.parent())
        if selection_error == "Good":
            post_Choice.current_team_roster.append(int(new_team))
            str(post_Choice.put())
#             close_draft(post_Choice_key.parent().get().league)

        #Display the homepage
        self.redirect('/draft/pickUp/?updated=' + selection_error)


application = webapp2.WSGIApplication([('/draft/pickUp/submitPick', Submit_Pick),
                                       ('/draft/pickUp/', Pick_up_Page),
                                       ('/draft/submitPick', Submit_Draft_Pick),
                                       ('/draft/startDraft', Start_Draft),
                                       ('/draft/', Draft_Page)

                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()