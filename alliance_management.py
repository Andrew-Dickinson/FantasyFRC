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

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def get_team_schedule(team_number):
    schedule = []
    for i in range(1, globals.number_of_offical_weeks + 1):
        schedule.append({'competition_name': "", 'tba_url': "", 'points': 0, 'event_key':''})

    event_list = root_team_key(str(team_number)).get().events
    for event_id in event_list:
        root_event = root_event_key(event_id).get()
        event_week = root_event.week
        points = 0
        points = get_team_points_at_event(team_number, event_id)
        schedule[event_week - 1]['competition_name'] = root_event.name
        # logging.info(root_event.key.id())
        schedule[event_week - 1]['event_key'] = root_event.key.id()
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
                team['schedule'] = get_team_schedule(number)
                team['total_points'] = get_points_to_date(int(number))
                current_lineup.append(team)

            bench_numbers = roster
            for number in active_lineup:
                bench_numbers.remove(number)

            current_bench = []
            for number in bench_numbers:
                current_bench.append({'number':number, 'total_points': get_points_to_date(int(number))})

            logging.info(current_bench)
            #Send html data to browser
            template_values = {
                            'user': user.nickname(),
                            'logout_url': logout_url,
                            'league_name': league_name,
                            'Choice_Key': Choice_key(account.key, league_id).urlsafe(), #TODO Encrypt
                            'team_lists': [current_lineup, current_bench]
                            }

            template = JINJA_ENVIRONMENT.get_template('templates/alliance_management.html')
            self.response.write(template.render(template_values))
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
            self.response.write(template.render({'Message':"This page requires that the draft be completed before accessing it"}))

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
        team_data['schedule'] = get_team_schedule(int(team_number))

        team_name = "Team " + str(team_number) + " - " + root_team_key(str(team_number)).get().name
        tba_team_url = globals.public_team_url % team_number

        event_breakdowns = []
        point_breakdown = []
        for event in get_team_schedule(int(team_number)):
            if event['competition_name'] != '' and event['competition_name']:
                event_breakdowns.append(get_point_breakdown_display(int(team_number), event['event_key']))
        
        for i, name in enumerate(humman_readable_point_categories):
            point_breakdown.append([]) #Create the new row
            title = {'title':name, 'explanation': explanation_of_point_categories[i]} #Build the data neccessary for the title/tooltip
            point_breakdown[i].append(title) #Add the tile for the first column
            category_total = 0
            for event in event_breakdowns:
                #Event is a value in the form [cat1,cat2...] 
                category_total += event[i]['points'] #Build the total for the end of the row
                event_text = ""
                if 'tooltip' in event[i]: #If there's a tooltip, pass it on to the page
                    point_breakdown[i].append({'points': event[i]['display'], 'tooltip': event[i]['tooltip']})
                else:
                    point_breakdown[i].append(event[i]['display']) #For each event, add the point display
            point_breakdown[i].append(category_total) #Finally, add the total

        point_breakdown.append([]) #For totals 
        index_of_totals_row = len(humman_readable_point_categories)
        overall_total = 0
        point_breakdown[index_of_totals_row].append('Overall Total:') #Left column row title
        for event in get_team_schedule(int(team_number)):
            if event['competition_name'] != '' and event['competition_name']:
                overall_total += event['points']
                point_breakdown[index_of_totals_row].append("") #For each event, add the total value
        point_breakdown[index_of_totals_row].append(overall_total) #Finally, add the total

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'league_name': league_name,
                        'Choice_Key': Choice_key(account.key, account.league).urlsafe(), #TODO Encrypt
                        'team_data': team_data,
                        'team_name': team_name,
                        'tba_team_url': tba_team_url,
                        'pointbreakdown': point_breakdown,
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

# Down here to resolve import issues
from points import get_team_points_at_event, get_points_to_date, get_point_breakdown_display, humman_readable_point_categories, explanation_of_point_categories