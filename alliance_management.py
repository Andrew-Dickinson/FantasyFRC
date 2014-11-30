#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

import globals

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

from UpdateDB import convert_date_time_to_week
from datastore_classes import account_key, Account, root_event_key, root_team_key, lineup_key, Lineup, Choice_key, league_key

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def get_team_schedule(team_number):
    schedule = []
    for i in range(1, globals.number_of_official_weeks + 1):
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
        schedule[event_week - 1]['tba_url'] = globals.public_event_url.format(root_event.key.id())
        schedule[event_week - 1]['points'] = points
    return schedule

def get_team_lists(user_id, week_number):
    account = account_key(user_id).get()
    choice = Choice_key(account.key, account.league).get()
    roster = choice.current_team_roster

    active_lineup = lineup_key(Choice_key(account.key, account.league), week_number).get().active_teams

    current_lineup = []
    for number in active_lineup:
        team = {}
        team['number'] = number
        team['detail_url'] = '/allianceManagement/teamDetail/%s' % number
        team['schedule'] = get_team_schedule(number)

        if is_week_editable(week_number):
            team['total_points'] = get_points_to_date(int(number))
        else:
            team['total_points'] = 0
            event_key = get_team_schedule(int(number))[int(week_number) - 1]['event_key']#-1 to convert to 0-based index
            if event_key: #Check if the team is competing that week
                team['total_points'] = get_team_points_at_event(int(number), event_key)
        current_lineup.append(team)

    bench_numbers = []
    for team in roster: #Just trust me on this one, don't mess with this
        bench_numbers.append(team)
    for number in active_lineup:
        if number in bench_numbers:
            bench_numbers.remove(number)

    current_bench = []
    for number in bench_numbers:
        if is_week_editable(week_number):
            total_points = get_points_to_date(int(number))
        else:
            total_points = 0
            event_key = get_team_schedule(int(number))[int(week_number) - 1]['event_key']#-1 to convert to 0-based index
            if event_key: #Check if the team is competing that week
                total_points = get_team_points_at_event(int(number), event_key)
        current_bench.append({'number':number, 'total_points': total_points})

    logging.info(current_bench)

    return [current_lineup, current_bench]

def is_week_editable(week_number):
    """Returns if the week is editable or not"""
    return globals.debug_current_editable_week <= int(week_number)

class alliance_portal(webapp2.RequestHandler):
    """The main dashboard for league info"""
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = globals.get_or_create_account(user)
        league_id = account.league
        draft_over = league_key(league_id).get().draft_current_position == -1

        if draft_over:
            if league_id != '0':
                league_name = league_key(league_id).get().name
            else:
                league_name = ""

            total_points = 0
            week_table = []
            for weeknum in range(1, globals.number_of_official_weeks + 1):
                teams = get_team_lists(user_id, weeknum)[0]
                points = 0
                lineup = []
                for team in teams:
                    event_key = get_team_schedule(int(team['number']))[int(weeknum) - 1]['event_key']#-1 to convert to 0-based index
                    if event_key: #Check if the team is competing that week
                        points += get_team_points_at_event(team['number'], event_key)
                    lineup.append(team['number'])

                if is_week_editable(weeknum):
                    points = "<i>No Data</i>"
                else:
                    total_points += points

                week_row = {'week': str(weeknum), 'active_lineup': lineup, 'points': points}
                week_table.append(week_row)

            leader_board = get_leader_board(league_id)
            league_schedule = get_readable_schedule(league_id)

            template_values = {
                            'user': user.nickname(),
                            'logout_url': logout_url,
                            'league_name': league_name,
                            'week_table': week_table,
                            'total_points': total_points,
                            'leader_board': leader_board,
                            'schedule': league_schedule,
                            }

            template = JINJA_ENVIRONMENT.get_template('templates/alliance_management_portal.html')
            self.response.write(template.render(template_values))
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
            self.response.write(template.render({'Message':"This page requires that the draft be completed before accessing it"}))

        
        
class update_lineup(webapp2.RequestHandler):
    def get(self, week_number):
        """Updates the active teams for the user"""
        #The choice_key of the request
        action = self.request.get('action')
        team_number = self.request.get('team_number')

        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()

        account = globals.get_or_create_account(user)
        league_id = account.league

        if is_week_editable(week_number):
            active_lineup = lineup_key(Choice_key(account.key, league_id), week_number).get()
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

        self.redirect('/allianceManagement/viewAlliance/' + str(week_number))

class view_alliance(webapp2.RequestHandler):
    """Handles the requests to see data for all alliances"""
    def get(self, week_number):
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
            team_lists = get_team_lists(user_id, week_number)
            point_total = 0
            for team in team_lists[0]:
                point_total += team['total_points']

            opponent_team_lists = get_team_lists(get_opponent(user_id, week_number), week_number)
            opponent_point_total = 0
            for team in opponent_team_lists[0]:
                opponent_point_total += team['total_points']



            #Send html data to browser
            template_values = {
                            'user': user.nickname(),
                            'logout_url': logout_url,
                            'league_name': league_name,
                            'week_number': int(week_number),
                            'point_totals': [point_total, opponent_point_total],
                            'team_listss': [team_lists, opponent_team_lists],
                            'opponent_name': get_opponent_name(user_id, week_number),
                            }

            if is_week_editable(week_number):
                template = JINJA_ENVIRONMENT.get_template('templates/alliance_management.html')
            else:
                template = JINJA_ENVIRONMENT.get_template('templates/past_alliances.html')
            self.response.write(template.render(template_values))
        else:
            template = JINJA_ENVIRONMENT.get_template('templates/error_page.html')
            self.response.write(template.render({'Message':"This page requires that the draft be completed before accessing it"}))


        

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
                        'team_data': team_data,
                        'team_name': team_name,
                        'tba_team_url': tba_team_url,
                        'pointbreakdown': point_breakdown,
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/team_detail.html')
        self.response.write(template.render(template_values))




application = webapp2.WSGIApplication([
                                       ('/allianceManagement/viewAlliance', alliance_portal),
                                       ('/allianceManagement/viewAlliance/(.*)', view_alliance),
                                       ('/allianceManagement/updateLineup/(.*)', update_lineup),
                                       ('/allianceManagement/teamDetail/(.*)', team_detail_page),
                                       
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

# Down here to resolve import issues
from league_management import get_leader_board, get_readable_schedule, get_opponent, get_opponent_name
from points import get_team_points_at_event, get_points_to_date, get_point_breakdown_display, humman_readable_point_categories, explanation_of_point_categories