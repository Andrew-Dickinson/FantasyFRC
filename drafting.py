#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import math
import json
import logging
from random import shuffle
import datetime
import calendar

import globals
from globals import get_team_list, maximum_roster_size, maximum_active_teams

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb
from google.appengine.api import users

from datastore_classes import RootTeam, league_key, Choice, Lineup, choice_key, account_key, Account, lineup_key, \
    DraftPick, draft_pick_key

import jinja2
import webapp2
import error_messages
# Constants to indicate the current direction of the draft
DRAFT_INCREASING = 1
DRAFT_DECREASING = 2
DRAFT_STATIONARY = 3

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def start_draft(league_id):
    """
        Set up to prepare for a draft

        :parameter league_id: The league to prepare for a draft
        Do the following:
            - Create a random order
            - Use this order to generate a single list of exactly what pick happens in what order
            - Use this to create the necessary pick objects with the correct order properties
            - Place the league in a position to begin the draft
    """
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    shuffle(league_players)  # Randomize the order of the draft

    number_of_players = len(league_players)
    number_of_picks = number_of_players * globals.draft_rounds

    snake_draft = league_key(league_id).get().snake_draft

    direction = DRAFT_INCREASING
    pick_of_round = 0
    display_number = 0
    number_of_drafts = 0
    while number_of_drafts < number_of_picks:
        if snake_draft:
            if direction == DRAFT_INCREASING:
                if pick_of_round == number_of_players:
                    direction = DRAFT_STATIONARY
            elif direction == DRAFT_DECREASING:
                if pick_of_round == 1:
                    direction = DRAFT_STATIONARY
            elif direction == DRAFT_STATIONARY:
                if pick_of_round == 1:
                    direction = DRAFT_INCREASING
                elif pick_of_round == number_of_players:
                    direction = DRAFT_DECREASING
        else:
            if pick_of_round == number_of_players:
                pick_of_round = 0  # 0 will become a 1 down below because direction = DRAFT_INCREASING

        if direction == DRAFT_INCREASING:
            pick_of_round += 1
            display_number += 1
        elif direction == DRAFT_DECREASING:
            pick_of_round -= 1
            display_number -= 1
        elif direction == DRAFT_STATIONARY:
            display_number += 4

        logging.info(display_number)
        player = league_players[pick_of_round - 1]
        pick_key = draft_pick_key(league_key(league_id), str(number_of_drafts + 1))
        pick = DraftPick.get_or_insert(pick_key.id(), parent=pick_key.parent())
        pick.display_number = display_number
        pick.player = player.key.urlsafe()
        pick.put()

        number_of_drafts += 1

    league = league_key(league_id).get()
    league.draft_current_position = 0
    league.put()


def get_lat_lng_json(league_id):
    """
        Return the latitude and longitude data for all available teams in a league

        :parameter league_id: The league used to determine which teams are available
        :type: string
        :return: A json object containing all of the information.
                This is intended to be read by the javascript on the browser side
    """
    team_data = []
    teams = RootTeam.query().fetch()
    taken_teams = get_taken_teams(league_id)
    for team in teams:
        if team.key.id() in taken_teams:
            teams.remove(team)

    for team in teams:
        team_data.append({"number": team.key.id(),
                          "name": team.name,
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
    """
        Generate and distribute a schedule based on a round robin system where team members play each other fairly

        :parameter  league_id: The id of the league to generate the schedule for
        :type: string
        Generate a random schedule in which all members play each other at least once before playing each other again
        Take this schedule and use to assign an individual schedule to each player
    """
    player_ids_list = []

    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    for player in league_players:
        player_ids_list.append(player.key.id())

    logging.info(player_ids_list)
    shuffle(player_ids_list)
    if len(player_ids_list) % 2 == 1:  # Check if the number of players is odd
        # Add 0 to represent bye week, added to beginning to solve last player issue
        player_ids_list.insert(0, globals.schedule_bye_week)
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
        for week in range(1, number_of_players):
            #This equation comes from a mathematica document. Truss me about it - 2014 season
            last_player_schedule.append(player_ids_list[int(.25 * ((-1) ** week) *
                                                            ((number_of_players - 1) +
                                                             (number_of_players - 3) * ((-1) ** week) +
                                                             2 * ((-1) ** week) * week))])
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
    """Return a list of teams that have already been drafted based on a league and event id"""
    taken_teams = []
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()

    for player in league_players:
        choice = Choice.get_or_insert(league_id, parent=player.key)
        if choice:
            for team in choice.current_team_roster:
                taken_teams.append(str(team))
    return taken_teams


def is_valid_team(team, league_id):
    """
            Parse and return whether a team is a valid choice in the draft.
            :parameter team: the number of the team
            :type: string or int
            :parameter league_id: the id of the league this draft is being conducted in
            :type: string
            :return: An error message if the team is not a valid choice, if valid choice, return 'Good'
        """
    team_list = get_team_list()
    taken_list = get_taken_teams(league_id)
    try:
        number = int(team)
    except ValueError:
        return "Invalid number"
    if str(team) in taken_list:
        return "Team already taken"
    if not (str(number) in team_list):
        return "Team does not exist"
    return "Good"  # Will indicate no errors


def initialize_lineup(lineup_id, choice):
    """
        Creates a lineup for a given id
        :param lineup_id: The week number used to identify the lineup
        :param choice: The parent for this lineup item
    """
    lineup = Lineup.get_or_insert(lineup_key(choice.key, lineup_id).id(), parent=choice.key)
    #Only initialize if its' empty
    if lineup.active_teams:  # If active_teams == None,
        lineup.active_teams = []  # Initialize it to an empty array
    lineup.put()


def setup_for_next_pick(league_id):
    """
        Set the database so that the next person can make a selection

        :param league_id: League to do this in
        If the draft is finished, appropriately call lose_draft
        If the draft is still in progress, increase the current draft_position by one and reset the timeout
    """
    league = league_key(league_id).get()
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    number_of_picks = len(league_players) * globals.draft_rounds
    if league.draft_current_position == number_of_picks:  # See if the draft is over
        close_draft(league_id)
    else:
        league.draft_current_position += 1
        league.draft_current_timeout = datetime.datetime.utcnow() \
                                       + datetime.timedelta(minutes=globals.draft_time_minutes)
        league.put()


def close_draft(league_id):
    """
        Preform all of the operations necessary to finish the drafting process
        :param league_id: The league to do this in

        Called at the end of the draft
        Initialize lineup items
        Generate schedule
    """
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
            initialize_lineup(i, choice)  # Initialize weekly lineups
            player.record.append('')
        player.put()


def get_max_free_agent_pages(league_id):
    """
        Return the maximum number of free agent pages possible in a specific league

        :param league_id: The league to calculate this in
        :return: The maximum number of pages in the free agent list
    """
    query = RootTeam.query().order(-RootTeam.total_points)
    extra_teams = query.fetch()

    taken_teams = get_taken_teams(league_id)

    #Get rid of the taken teams from the list
    for team in extra_teams:
        if team.key.id() in taken_teams:
            extra_teams.remove(team)
            taken_teams.remove(team.key.id())  # Not necessary, but improves efficiency

    number_of_teams = len(extra_teams)
    if number_of_teams % globals.free_agent_pagination == 0:
        return number_of_teams / globals.free_agent_pagination
    else:
        return math.floor(number_of_teams / globals.free_agent_pagination) + 1


def get_free_agent_list(league_id, page):
    """
        Return the list of free agents for a given league. Only return those on a certain page

        :param league_id: The league to generate the list for
        :param page: The number of the page to get
        :return: A list of dictionaries with the following information for each team:
            - rank: Rank in the free agent list
            - name: The name of the team
            - number: The team numer
            - total points: The total number of points(our system) that this team has accumulated
    """
    taken_teams = get_taken_teams(league_id)
    query = RootTeam.query().order(-RootTeam.total_points)
    extra_teams = query.fetch(globals.free_agent_pagination * page * 4)

    free_agent_teams = []
    #Get rid of the taken teams from the list
    for team in extra_teams:
        if not (team.key.id() in taken_teams):  # If this team has not been taken
            free_agent_teams.append(team)
        else:  # This team has been taken
            taken_teams.remove(team.key.id())  # Not necessary, but improves efficiency

    free_agent_list = []
    for i, team in enumerate(free_agent_teams[(page - 1) * globals.free_agent_pagination: page
            * globals.free_agent_pagination]):
        free_agent_list.append({
            'rank': i + ((page - 1) * globals.free_agent_pagination) + 1,
            'name': team.name,
            'number': team.key.id(),
            'total_points': team.total_points
        })

    return free_agent_list


class FreeAgentListPage(webapp2.RequestHandler):
    def get(self, page):
        """
            Display a certain page of the free agent list

            :param page: The page to display

            The free agent list is a list of teams that have not been drafted by any player.
            They are sorted by the total points of each team
            Users have the option to pick up teams or "flag" them to get updates about them
        """
        # Checks for active Google account session
        user = users.get_current_user()

        logout_url = users.create_logout_url('/')

        #Display update text for the status of the last choice update
        update_text = self.request.get('updated')

        account = globals.get_or_create_account(user)
        league_id = account.league

        if league_id != '0':
            if not page:
                page = 1
            else:
                page = int(page)

            league_name = league_key(league_id).get().name

            free_agent_list = get_free_agent_list(league_id, page)

            #Send html data to browser
            template_values = {
                'user': user.nickname(),
                'logout_url': logout_url,
                'league_name': league_name,
                'update_text': update_text,
                'free_agent_list': free_agent_list,
                'page': page,
                'max_page': get_max_free_agent_pages(league_id),
            }
            template = JINJA_ENVIRONMENT.get_template('templates/falist.html')
            self.response.write(template.render(template_values))

        else:
            globals.display_error_page(self, self.request.referer, error_messages.need_to_be_a_member_of_a_league)


class Draft_Page(webapp2.RequestHandler):
    def get(self):
        """
            The draft page contains the draft board, a timer, and a map; all that is necessary for the draft process
        """
        # Checks for active Google account session
        user = users.get_current_user()

        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        if league_id != '0':
            #Make check to see if the time for the current pick has expired
            current_time = datetime.datetime.utcnow()
            current_timeout = league_key(league_id).get().draft_current_timeout
            draft_pick = draft_pick_key(league_key(league_id), league_key(league_id).get().draft_current_position).get()
            if current_timeout:
                if current_time > current_timeout:  # The time has expired
                    logging.info("Forefit")
                    draft_pick.team = 0  # Set the pick to indicate it was forefited
                    draft_pick.put()
                    setup_for_next_pick(league_id)  # Move the pick along to the next person

            #Display update text for the status of the last choice update
            update_text = self.request.get('updated')
            if self.request.get('updated') == "Good":
                update_text = "Team added successfully"

            league_player_query = Account.query(Account.league == league_id)
            players_for_the_sake_of_number = league_player_query.fetch()
            league_players = []

            if draft_pick_key(league_key(league_id), 1).get():  # != None
                for i in range(1, len(players_for_the_sake_of_number) + 1):
                    pick = draft_pick_key(league_key(league_id), i).get()
                    league_players.append(ndb.Key(urlsafe=pick.player).get())
            else:
                league_players = players_for_the_sake_of_number

            draft_board = []
            player_list = []
            for player in league_players:
                player_list.append(player.nickname)

            number_of_picks = len(league_players) * globals.draft_rounds
            for position in range(1, number_of_picks + 1):
                pick_query = DraftPick.query().filter(DraftPick.display_number == position)
                query_results = pick_query.fetch(1)
                pick = DraftPick()
                if len(query_results) != 0:
                    pick = query_results[0]

                username = (((position % len(league_players)) - 1) % len(league_players))
                draft_round = int((position - 1) / len(league_players))
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

            if current_position == 0:
                draft_status = "Pre"
            elif current_position == -1:
                draft_status = "Post"
            else:
                draft_status = "Mid"

            team_map_data = get_lat_lng_json(league_id)

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
            globals.display_error_page(self, self.request.referer,error_messages.need_to_be_a_member_of_a_league)


class Start_Draft(webapp2.RequestHandler):
    def get(self):
        """
            When visited by the league commissioner, the draft is started
            The commissioner is then redirected to the draft page
        """
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()

        account = globals.get_or_create_account(user)
        league_id = account.league
        league = league_key(league_id).get()

        league_comissioner = league.key.id()
        if league_comissioner == user_id:
            league_player_query = Account.query(Account.league == league_id)
            league_players = league_player_query.fetch()
            if len(league_players) > 1:
                if league.draft_current_position == 0:
                    start_draft(league_id)
                    setup_for_next_pick(league_id)
                    self.redirect('/draft/')
                else:
                    globals.display_error_page(self, self.request.referer, error_messages.draft_already_completed)
            else:
                globals.display_error_page(self, self.request.referer, error_messages.league_too_small)
        else:
            globals.display_error_page(self, self.request.referer,error_messages.access_denied)


class Submit_Draft_Pick(webapp2.RequestHandler):
    """
        Take the field data from the draft page and process it
    """
    def post(self):
        # Checks for active Google account session
        user = users.get_current_user()

        account = globals.get_or_create_account(user)
        league_id = account.league

        league_entity = league_key(league_id).get()
        current_position = league_entity.draft_current_position
        current_timeout = league_entity.draft_current_timeout
        current_time = datetime.datetime.utcnow()

        if current_position != 0 and current_position != -1:  #Don't process if draft is over or yet to begin
            current_pick = draft_pick_key(league_entity.key, current_position).get()
            if current_pick.player == account.key.urlsafe():  #Check that the calling player is actually within their turn
                if current_time < current_timeout:  #Check that the calling player is within their time constraints
                    #Get the new team from the post header
                    new_team = self.request.get('team')

                    #Validate the selection
                    selection_error = is_valid_team(new_team, league_id)
                    if selection_error == "Good":
                        #S'all good, update the datastore
                        current_pick.team = int(new_team)
                        current_pick.put()
                        #Add the team to the user's roster
                        user_choice = Choice.get_or_insert(league_id, parent=account.key)
                        if not user_choice.current_team_roster:  # Make sure to use [] for an empty roster, not None
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
    """
        Allows a user to pick up a single team after the draft has completed
    """
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
            find_choice_key = choice_key(account_key(user_id), str(league_id))
            found_choice = find_choice_key.get()

            #Display update text for the status of the last choice update
            update_text = self.request.get('updated')
            if self.request.get('updated') == "Good":
                update_text = "Team added successfully"

            #Display the user's current roster
            user_roster = []
            if found_choice:
                user_roster = found_choice.current_team_roster


            #Get list of players in the league and their choices
            league_table = [{'player_team': 'Roster', 'player_name': 'Player'}]
            league_player_query = Account.query(Account.league == league_id)
            league_players = league_player_query.fetch()  #league_player_query.order(Account.nickname).fetch()
            for player in league_players:
                choice = choice_key(account_key(player.key.id()), league_id).get()
                if choice:
                    league_table.append(
                        {'player_team': str(choice.current_team_roster), 'player_name': player.nickname})
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
                'default_team': self.request.get('team'),
            }
            template = JINJA_ENVIRONMENT.get_template('templates/pick_up_main.html')
            self.response.write(template.render(template_values))


class Submit_Pick(webapp2.RequestHandler):
    """
        Adds a team to the roster of the account who visits the page. Has appropriate checks for validity
        Expects a field, 'team' to be the team number to pick up
    """
    def get(self):
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        find_Choice_key = choice_key(account_key(user_id), str(league_id))
        post_Choice_key = find_Choice_key

        new_team = self.request.get('team')

        selection_error = is_valid_team(new_team, post_Choice_key.parent().get().league)
        logging.info(selection_error)
        #Form data into entity and submit
        post_Choice = Choice.get_or_insert(post_Choice_key.id(), parent=post_Choice_key.parent())
        if selection_error == "Good":
            if len(choice_key(account_key(user_id), league_id).get().current_team_roster) < maximum_roster_size:
                post_Choice.current_team_roster.append(int(new_team))
                str(post_Choice.put())
            else:
                selection_error = "Your roster is full"

        #Send them back to the previous page
        self.redirect(str(self.request.referer.split('?', 1)[0] + '?updated=' + selection_error))

    def post(self):
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        find_Choice_key = choice_key(account_key(user_id), str(league_id))
        post_Choice_key = find_Choice_key

        new_team = self.request.get('team')

        selection_error = is_valid_team(new_team, post_Choice_key.parent().get().league)

        #Form data into entity and submit
        post_Choice = Choice.get_or_insert(post_Choice_key.id(), parent=post_Choice_key.parent())
        if selection_error == "Good":
            if len(choice_key(account_key(user_id), league_id).get().current_team_roster) < maximum_roster_size:
                post_Choice.current_team_roster.append(int(new_team))
                str(post_Choice.put())
            else:
                selection_error = "You have reached the maximum capacity for teams on your roster"
            #             close_draft(post_Choice_key.parent().get().league)

        #Display the homepage
        self.redirect('/draft/pickUp/?updated=' + selection_error)


application = webapp2.WSGIApplication([('/draft/freeAgentList/(.*)', FreeAgentListPage),  # Page number
                                       ('/draft/pickUp/submitPick', Submit_Pick),
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