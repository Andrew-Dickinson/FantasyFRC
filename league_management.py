#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

from datastore_classes import account_key, Account, League, Choice, choice_key, league_key, Lineup, lineup_key, DraftPick

import jinja2
import webapp2
import error_messages

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def get_opponent_name(user_id, week_number):
    """Return the name of the opponent of certain user_id on a specific week_number"""
    return account_key(get_opponent(user_id, week_number)).get().nickname


def get_opponent(user_id, week_number):
    """Return the account key of the opponent of a certain user_id on a specific week_number"""
    return account_key(user_id).get().schedule[int(week_number) - 1]  # -1 for conversion to 0 based


def get_schedule(league_id):
    """Return the league master schedule for a league id"""
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    master_schedule = []

    for player in league_players:
        master_schedule.append({'user': player.key.id(), 'schedule': player.schedule})

    return master_schedule


def get_readable_schedule(league_id):
    """Return the league master schedule for a league id in a readable format"""
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    master_schedule = []

    for player in league_players:
        schedule = player.schedule

        #Convert to nicknames
        for i, opponent in enumerate(schedule):
            if opponent != globals.schedule_bye_week:
                schedule[i] = account_key(opponent).get().nickname
            else:
                schedule[i] = "Bye"

        master_schedule.append({'name': player.nickname, 'schedule': schedule})

    return master_schedule

def get_readable_user_schedule(user_id):
    """Return the schedule of a single person in readable format"""
    player = account_key(user_id).get()
    schedule = player.schedule

    #Convert to nicknames
    for i, opponent in enumerate(schedule):
        if opponent != globals.schedule_bye_week:
            schedule[i] = opponent
        else:
            schedule[i] = "Bye"

    return schedule

def get_player_record(player_id):
    """Access the data store to return a player's record"""
    account = account_key(player_id).get()
    record_WLT = [0, 0, 0, 0]
    for week in range(0, globals.number_of_official_weeks):
        week_result = account.record[week]
        if week_result == globals.record_win:
            record_WLT[0] += 1
        elif week_result == globals.record_loss:
            record_WLT[1] += 1
        elif week_result == globals.record_tie:
            record_WLT[2] += 1
        elif week_result == globals.record_bye:
            record_WLT[3] += 1
    return record_WLT


def get_league_points(player_id):
    """Use constants in globals and the data store record to calculate league points for a player"""
    record_WLT = get_player_record(player_id)
    total_points = 0
    total_points += record_WLT[0] * globals.league_points_per_win
    total_points += record_WLT[1] * globals.league_points_per_loss
    total_points += record_WLT[2] * globals.league_points_per_tie
    total_points += record_WLT[3] * globals.league_points_per_bye

    return total_points


def get_leader_board(league_id):
    """Return an array of dictionaries with leader board data for a league"""
    leader_board = []
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    rank_list = []

    #Create a list to sort by league points
    for player in league_players:
        rank_list.append({'id': player.key.id(),
                          'nickname': player.nickname,
                          'points': get_league_points(player.key.id())
                          })

    sorted_by_points = sorted(rank_list, key=lambda account: account['points'], reverse=True)

    #Build the leader board
    for i, player in enumerate(sorted_by_points):
        leader_board.append({'name': player['nickname'],
                             'rank': i + 1,
                             'record': get_player_record(player['id']),
                             'points': get_person_total_points(player['id']),
                            })

    # Remove bye week
    for player in leader_board:
        player['record'].pop()

    return leader_board


def finish_week(league_id, past_week_num):
    """
        Preform the operations necessary to move on to the next week. Called around Monday-ish

        :param league_id: The league to finish
        :param past_week_num: The week number to finish
        This function will
            - Calculate winners and loosers
            - Update player records with this information
    """
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    for player in league_players:
        opponent = get_opponent(player.key.id(), past_week_num)
        if opponent != globals.schedule_bye_week:
            opponent_points = get_total_week_points(opponent, past_week_num)
            player_points = get_total_week_points(player.key.id(), past_week_num)
            if opponent_points < player_points:
                player.record[past_week_num - 1] = globals.record_win  # -1 for conversion to 0 based index
            elif opponent_points == player_points:
                #We have to consider tiebreakers, notably bench points
                if get_bench_points(player.key.id(), past_week_num) > get_bench_points(opponent, past_week_num):
                    player.record[past_week_num - 1] = globals.record_win  # -1 for conversion to 0 based index
                elif get_bench_points(player.key.id(), past_week_num) < get_bench_points(opponent, past_week_num):
                    player.record[past_week_num - 1] = globals.record_loss # -1 for conversion to 0 based index
                else:
                    #Bench points and active points tie, mark it as an actual tie
                    player.record[past_week_num - 1] = globals.record_tie # -1 for conversion to 0 based index
            elif opponent_points > player_points:
                player.record[past_week_num - 1] = globals.record_loss # -1 for conversion to 0 based index
        else:  # Bye week
            player.record[past_week_num - 1] = globals.record_bye  # -1 for conversion to 0 based index
        player.put()

def run_week_begin(begin_week_num):
    """
        Called around Wednesday-ish. Starts things off for a new competition week

        This function:
            - restricts editing to the previous week
            - Seals rosters in the books so benches and such will work correctly
    """

    #Seal rosters
    all_choice_entities = Choice.query().fetch()
    for choice in all_choice_entities:
        lineup_object = lineup_key(choice.key, begin_week_num).get()
        roster = choice.current_team_roster
        for team_number in roster:
            lineup_object.weekly_roster.append(team_number)

    #Restrict editing
    globals.set_current_editable_week(int(begin_week_num) + 1)


def remove_from_league(user_id):
    """
        Remove a certain user_id from their league, only if the draft hasn't already started
    """
    #Current user's id, used to identify their data
    account = Account.get_or_insert(user_id)

    if league_key(account.league).get() and league_key(account.league).get().draft_current_position == 0:
        remove_from_league_indiscriminately(user_id)

def remove_from_league_indiscriminately(user_id):
    """
        Remove a certain user_id from their league, doesn't care if the draft has already started
        To be called directly only on the destruction of a league
    """
    #Current user's id, used to identify their data
    account = Account.get_or_insert(user_id)

    if league_key(account.league).get():
        #Remove user's choices and lineup for the league
        choice = choice_key(account_key(user_id), account.league).get()
        if choice:
            lineup_query = Lineup.query(ancestor=choice.key).fetch()
            for lineup in lineup_query:
                lineup.key.delete()
            choice.key.delete()

        #If this is the last person in the league, or this is the commissioner, delete it after they leave
        players = Account.query().filter(Account.league == account.league).fetch()
        if len(players) == 1 or account.league == account.key.id():
            past_league = account.league
            #Remove User's association with league
            account.league = '0'
            account.put()
            delete_league(past_league)

        #Remove User's association with league
        account.league = '0'
        account.put()


def add_to_league(user_id, league_id):
    """
        Add a certain user_id to a certain league_id
    """
    account = Account.get_or_insert(user_id)

    #Add choice key for league
    choice = Choice.get_or_insert(str(league_id), parent=account.key)
    choice.put()

    #Add user to league
    account.league = league_id
    account.put()

def delete_league(league_id):
    """Delete a particular league"""
    if league_id != '0': #Don't ever delete the default league
        league = league_key(league_id).get()
        players = Account.query().filter(Account.league == league_id).fetch()
        draft_picks = DraftPick.query(ancestor=league.key).fetch()
        for player in players:
            remove_from_league(player.key.id())
        for draft_pick in draft_picks:
            draft_pick.key.delete()
        league.key.delete()



class Show_Leagues(webapp2.RequestHandler):
    """
        Show a page which lists all of the leagues and includes options to join them
    """
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        league_query = League.query()
        league_list = league_query.fetch()

        league_output = []
        for league in league_list:
            number_of_players = len(Account.query().filter(Account.league == league.key.id()).fetch())
            commissioner = "None"
            if account_key(league.key.id()).get():
                commissioner = account_key(league.key.id()).get().nickname
            if league.key.id() != '0':
                league_output.append({'name': league.name,
                                      'id': league.key.id(),
                                      'size': number_of_players,
                                      'commissioner': commissioner,
                                      'join_url': '/leagueManagement/joinLeague/' + league.key.id()
                                      })

        if league_id != '0':
            league_name = league_key(league_id).get().name
        else:
            league_name = ""

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'league_list': league_output,
                        'league_name': league_name,
                        'draft_state': globals.get_draft_state(account),
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/league_list.html')
        self.response.write(template.render(template_values))

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


class create_League(webapp2.RequestHandler):
    """
        Setup information page for creating a league
    """
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        if league_id != '0':
            league_name = league_key(league_id).get().name
        else:
            league_name = ""

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'league_name': league_name,
                        'draft_state': globals.get_draft_state(account),
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/create_league.html')
        self.response.write(template.render(template_values))

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


class update_League(webapp2.RequestHandler):
    """
        The post handler for the creation and update of leagues
    """
    def post(self):
        user = users.get_current_user()
        account = globals.get_or_create_account(user)

        commissioner_account_key = account.key

        current_league = league_key(commissioner_account_key.get().league).get()

        #Get data from the post header
        name = self.request.get('name')
        snake = self.request.get('snake_draft') == 'on'

        if not current_league or current_league.draft_current_position == 0:
            #Create/Update the league
            new_league = League.get_or_insert(commissioner_account_key.id())
            new_league.name = name
            new_league.snake_draft = snake
            new_league.draft_current_position = 0
            new_league.put()

            add_to_league(user.user_id(), new_league.key.id())

            self.redirect('/')
        else:
            globals.display_error_page(self, self.request.referer, error_messages.league_already_started_leaving)

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


class leave_League(webapp2.RequestHandler):
    """
        A page which, when visited, will remove a user from their current league
        The user is redirected to '/'
    """
    def get(self):
        user_id = users.get_current_user().user_id()
        if league_key(account_key(user_id).get().league).get().draft_current_position == 0:
            remove_from_league(user_id)
            self.redirect('/')
        else:
            globals.display_error_page(self, self.request.referer, error_messages.league_already_started_leaving)

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


class Join_League(webapp2.RequestHandler):
    def get(self, league_id):
        """
            Adds a user to the specified league
            :param league_id: Collected from url, the league to join
        """
        user_id = users.get_current_user().user_id()
        current_league = league_key(account_key(user_id).get().league).get()
        if not current_league or current_league.draft_current_position == 0:
            if league_key(league_id).get().draft_current_position == 0:
                remove_from_league(user_id) #Remove from old league
                add_to_league(user_id, league_id) #Add to new one
                self.redirect('/')
            else:
                globals.display_error_page(self, self.request.referer, error_messages.league_already_started)
        else:
            globals.display_error_page(self, self.request.referer, error_messages.league_already_started_leaving)

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


class manage_league(webapp2.RequestHandler):
    def get(self):
        """
            Allows deletion of a league and the modification of settings
        """
        # Checks for active Google account session
        user = users.get_current_user()

        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        if league_id == account.key.id():
            if league_id != '0':
                league_name = league_key(league_id).get().name
            else:
                league_name = ""

            #Send html data to browser
            template_values = {
                            'user': user.nickname(),
                            'logout_url': logout_url,
                            'league_name': league_name,
                            'draft_state': globals.get_draft_state(account),
                            'snake_draft': league_key(league_id).get().snake_draft
                            }
            template = JINJA_ENVIRONMENT.get_template('templates/manage_league.html')
            self.response.write(template.render(template_values))
        else:
            globals.display_error_page(self, self.request.referer,error_messages.access_denied)

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


class delete_League(webapp2.RequestHandler):
    """
        The post handler for the deletion of leagues
    """
    def get(self):
        user = users.get_current_user()
        account = globals.get_or_create_account(user)

        league = league_key(account.league).get()
        league_id = league.key.id()

        commissioner_account_id = league.key.id()

        if account.key.id() == commissioner_account_id:
            #Only the commissioner may delete a league
            league_player_query = Account.query(Account.league == league_id)
            league_players = league_player_query.fetch()
            for player in league_players:
                remove_from_league_indiscriminately(player.key.id())  # We can only do this because we're about to destroy the league
            league.key.delete()

            self.redirect('/')
        else:
            globals.display_error_page(self, self.request.referer, error_messages.access_denied)

    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())


application = webapp2.WSGIApplication([
                                       ('/leagueManagement/updateLeague', update_League),
                                       ('/leagueManagement/createLeague', create_League),
                                       ('/leagueManagement/showLeagues', Show_Leagues),
                                       ('/leagueManagement/joinLeague/(.*)', Join_League),  # The id of the league
                                       ('/leagueManagement/leaveLeague', leave_League),
                                       ('/leagueManagement/manageLeague', manage_league),
                                       ('/leagueManagement/deleteLeague', delete_League),
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

#Down here to fix import bug
from points import get_total_week_points, get_person_total_points, get_bench_points
import globals