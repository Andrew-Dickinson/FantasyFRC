#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

import globals
from datastore_classes import account_key, Account, League, Choice, Choice_key, league_key, Lineup, DraftPick

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def get_player_record(player_id):
    """Accesses the data store to return a player's record"""
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
    """Uses constants in globals and the data store record to calculate league points for a player"""
    record_WLT = get_player_record(player_id)
    total_points = 0
    total_points += record_WLT[0] * globals.league_points_per_win
    total_points += record_WLT[1] * globals.league_points_per_loss
    total_points += record_WLT[2] * globals.league_points_per_tie
    total_points += record_WLT[3] * globals.league_points_per_bye

    return total_points


def get_leader_board(league_id):
    """Returns an array of dictionaries with leader board data for a league"""
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
        leader_board.append({'name': player['nickname'], 'rank': i + 1, 'record': get_player_record(player['id'])})

    # Remove bye week
    for player in leader_board:
        player['record'].pop()

    return leader_board


def finish_week(league_id, past_week_num):
    league_player_query = Account.query(Account.league == league_id)
    league_players = league_player_query.fetch()
    for player in league_players:
        opponent = player.schedule[past_week_num - 1]  # -1 for conversion to 0 based index
        if opponent != globals.schedule_bye_week:
            opponent_points = get_total_week_points(opponent, past_week_num)
            player_points = get_total_week_points(player.key.id(), past_week_num)
            logging.info(player_points)
            logging.info(opponent_points)
            if opponent_points < player_points:
                player.record[past_week_num - 1] = globals.record_win  # -1 for conversion to 0 based index
            elif opponent_points == player_points:
                player.record[past_week_num - 1] = globals.record_tie # -1 for conversion to 0 based index
            elif opponent_points > player_points:
                player.record[past_week_num - 1] = globals.record_loss # -1 for conversion to 0 based index
        else:  # Bye week
            player.record[past_week_num - 1] = globals.record_bye  # -1 for conversion to 0 based index
        player.put()


def remove_from_league(user_id):
    #Current user's id, used to identify their data
    account = Account.get_or_insert(user_id)

    #Remove user's choices and lineup for the league
    choice = Choice_key(account_key(user_id), account.league).get()
    if choice:
        lineup_query = Lineup.query(ancestor=choice.key).fetch()
        for lineup in lineup_query:
            lineup.key.delete()
        choice.key.delete()

    #If this is the last person in the league, delete it after they leave
    players = Account.query().filter(Account.league == account.league).fetch()
    if len(players) == 1:
        past_league = account.league
        #Remove User's association with league
        account.league = '0'
        account.put()
        delete_league(past_league)

    #Remove User's association with league
    account.league = '0'
    account.put()


def add_to_league(user_id, league_id):
    account = Account.get_or_insert(user_id)

    #Add choice key for league
    choice = Choice.get_or_insert(str(league_id), parent=account.key)
    choice.put()

    #Add user to league
    account.league = league_id
    account.put()

def delete_league(league_id):
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
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
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
            league_output.append({'name': league.name,
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
                        'league_name': league_name
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/league_list.html')
        self.response.write(template.render(template_values))

class create_League(webapp2.RequestHandler):
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/create_league.html')
        self.response.write(template.render(template_values))

class update_League(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        account = globals.get_or_create_account(user)

        commissioner_account_key = account.key

        #Get data from the post header
        name = self.request.get('name')

        #Create/Update the league
        new_league = League.get_or_insert(commissioner_account_key.id())
        new_league.name = name
        new_league.draft_current_position = 0
        new_league.put()

        add_to_league(user.user_id(), new_league.key.id())

        self.redirect('/')

class leave_League(webapp2.RequestHandler):
    def get(self):
        id = users.get_current_user().user_id()
        remove_from_league(id)
        self.redirect('/')



class Join_League(webapp2.RequestHandler):
    def get(self, league_id):
        user_id = users.get_current_user().user_id()

        if league_key(league_id).get().draft_current_position == 0:
            remove_from_league(user_id) #Remove from old league
            add_to_league(user_id, league_id) #Add to new one
            self.redirect('/')
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
            self.response.write(template.render({'Message':'This league has already begun, or has finished its draft'}))

application = webapp2.WSGIApplication([
                                       ('/leagueManagement/updateLeague', update_League),
                                       ('/leagueManagement/createLeague', create_League),
                                       ('/leagueManagement/showLeagues', Show_Leagues),
                                        ('/leagueManagement/joinLeague/(.*)', Join_League),
                                       ('/leagueManagement/leaveLeague', leave_League)
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

#Down here to fix import bug
from points import get_total_week_points