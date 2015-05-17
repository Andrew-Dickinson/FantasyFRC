#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

import globals

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users

from datastore_classes import league_key, Account, DraftPick, draft_pick_key
from alliance_management import get_team_lists
from league_management import get_leader_board

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class MainPage(webapp2.RequestHandler):

    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Check if user is logged in
        if user is None:
            #Send html data to browser
            template_values = {'logged_out': users.create_login_url('/')}
            template = JINJA_ENVIRONMENT.get_template('templates/index.html')
            self.response.write(template.render(template_values))
        else:
            logout_url = users.create_logout_url('/')

            account = globals.get_or_create_account(user)
            league_id = account.league

            league_members = []
            draft_board = []
            users_turn = False
            leader_board = None
            if league_id != '0':
                league_name = league_key(league_id).get().name
                members = Account.query(Account.league == league_id).fetch()
                for member in members:
                    if member.key.id() == league_id and globals.get_draft_state(account) == 0:
                        league_members.append(member.nickname + " - League Commissioner")
                    else:
                        league_members.append(member.nickname)
                if globals.display_league_standings(account):
                    leader_board = get_leader_board(league_id)

                draft_pick = draft_pick_key(league_key(league_id), league_key(league_id).get().draft_current_position).get()
                if draft_pick:
                    users_turn = (draft_pick.player == account.key.urlsafe())

                if globals.get_draft_state(account) != 0:
                    number_of_picks = len(league_members) * globals.draft_rounds
                    for position in range(1, number_of_picks + 1):
                        pick = draft_pick_key(league_key(league_id), position).get()

                        username = (((position % len(league_members)) - 1) % len(league_members))
                        draft_round = int((position - 1) / len(league_members))
                        if username == 0:
                            draft_board.append([])
                            for i in range(0, len(league_members)):
                                draft_board[draft_round].append('-')
                        if pick and pick.team != None:
                            draft_board[draft_round][username] = str(pick.team)
                            if pick.team == 0:
                                draft_board[draft_round][username] = "<i>Forfeited</i>"
                        else:
                            draft_board[draft_round][username] = "<i>TBD</i>"
            else:
                league_name = ""

            week_number = globals.get_current_editable_week()
            point_totals = None
            team_listss = None
            if globals.get_draft_state(account) == -1:
                team_lists = get_team_lists(account.key.id(), week_number)
                point_totals = []
                for team_list in team_lists:
                    point_total = 0
                    for team in team_list:
                        point_total += team['total_points']
                    point_totals.append(point_total)

                team_listss = [team_lists]

            #Send html data to browser
            template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'league_name': league_name,
                        'draft_state': globals.get_draft_state(account),
                        'show_league_standings': globals.display_league_standings(account),
                        'league_members': league_members,
                        'draft_board': draft_board,
                        'users_turn': users_turn,
                        'week_number': int(week_number),
                        'point_totals': [point_totals],
                        'team_listss': team_listss,
                        'leader_board': leader_board,
                        }
            template = JINJA_ENVIRONMENT.get_template('templates/index.html')
            self.response.write(template.render(template_values))


    def handle_exception(self, exception, debug_mode):
        if debug_mode:
            super(type(self), self).handle_exception(exception, debug_mode)
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/500.html')
            self.response.write(template.render())

class PageNotFoundHandler(webapp2.RequestHandler):
    def get(self):
        self.error(404)
        template = JINJA_ENVIRONMENT.get_template('templates/404.html')
        self.response.write(template.render())

application = webapp2.WSGIApplication([
                                       ('/', MainPage),
                                       ('/.*', PageNotFoundHandler)
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()