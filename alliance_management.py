#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

import globals

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

from datastore_classes import account_key, Account, root_event_key, root_team_key, lineup_key, Lineup, Choice_key, league_key
from points import get_team_points_at_event

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def get_team_schedule(user_id, team_number):
    schedule = []
    for i in range(1, globals.number_of_offical_weeks + 1):
        schedule.append({'competition_name': "", 'tba_url': "", 'points': 0})

    event_list = root_team_key(str(team_number)).get().events
    for event_id in event_list:
        root_event = root_event_key(event_id).get()
        event_week = root_event.week
        points = 0
        if event_id == '2014txsa':
            points = get_team_points_at_event(team_number, event_id)
        schedule[event_week - 1]['competition_name'] = root_event.name
        schedule[event_week - 1]['tba_url'] = globals.public_event_url % root_event.key.id()
        schedule[event_week - 1]['points'] = points
    return schedule

class edit_alliance(webapp2.RequestHandler):
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league
        draft_over = league_key(league_id).get().draft_current_position == -1

        if league_id != '0':
            league_name = league_key(league_id).get().name
        else:
            league_name = ""

        if draft_over:
            active_lineup = lineup_key(Choice_key(account.key, league_id), globals.current_lineup_identifier).get().active_teams
            roster = Choice_key(account.key, league_id).get().current_team_roster

            current_lineup = []
            for number in active_lineup:
                team = {}
                team['number'] = number
                team['detail_url'] = '/allianceManagement/teamDetail/%s' % number
                team['schedule'] = get_team_schedule(user_id, number)
                current_lineup.append(team)

            current_bench = roster
            for number in active_lineup:
                current_bench.remove(number)

            logging.info(current_bench)
            #Send html data to browser
            template_values = {
                            'user': user.nickname(),
                            'logout_url': logout_url,
                            'league_name': league_name,
                            'Choice_Key': Choice_key(account.key, league_id).urlsafe(), #TODO Encrypt
                            'lineup': current_lineup,
                            'bench': current_bench
                            }

            template = JINJA_ENVIRONMENT.get_template('templates/alliance_management.html')
            self.response.write(template.render(template_values))
        else:
            self.response.write("This page requires that the draft be completed before accessing it")

class update_alliance(webapp2.RequestHandler):
    def post(self):
        """Updates the active teams for the user"""
        #The choice_key of the request
        post_Choice_key = ndb.Key(urlsafe=self.request.get('Choice_key'))
        team_roster = post_Choice_key.get().current_team_roster
        self.redirect('/allianceManagement/editAlliance')

class update_lineup(webapp2.RequestHandler):
    def get(self):
        """Updates the active teams for the user"""
        #The choice_key of the request
        action = self.request.get('action')
        team_number = self.request.get('team_number')

        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()

        account = globals.get_or_create_account(user)
        league_id = account.league



        active_lineup = lineup_key(Choice_key(account.key, league_id), globals.current_lineup_identifier).get()

        if action == "bench":
            active_lineup.active_teams.remove(int(team_number))
        elif action == "putin":
            active_lineup.active_teams.append(int(team_number))
        elif action == "drop":
            choice = Choice_key(account.key, league_id).get()
            choice.current_team_roster.remove(int(team_number))
            if int(team_number) in active_lineup.active_teams:
                active_lineup.active_teams.remove(int(team_number))
            choice.put()


        active_lineup.put()

        self.redirect('/allianceManagement/editAlliance')

class team_detail_page(webapp2.RequestHandler):
    def get(self, team_number):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league

        if league_id != '0':
            league_name = league_key(league_id).get().name
        else:
            league_name = ""

        team_data = {}
        team_data['number'] = team_number
        team_data['schedule'] = get_team_schedule(user_id, int(team_number))

        team_name = "Team " + str(team_number) + " - " + root_team_key(str(team_number)).get().name
        tba_team_url = globals.public_team_url % team_number

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'league_name': league_name,
                        'Choice_Key': Choice_key(account.key, account.league).urlsafe(), #TODO Encrypt
                        'team_data': team_data,
                        'team_name': team_name,
                        'tba_team_url': tba_team_url
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/team_detail.html')
        self.response.write(template.render(template_values))




application = webapp2.WSGIApplication([
                                       ('/allianceManagement/editAlliance', edit_alliance),
                                       ('/allianceManagement/updateAlliance', update_alliance),
                                       ('/allianceManagement/updateLineup', update_lineup),
                                       ('/allianceManagement/teamDetail/(.*)', team_detail_page)
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()