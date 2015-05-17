#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging
import error_messages


from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

from datastore_classes import account_key, RootTeam, Account, root_event_key, root_team_key, lineup_key, Lineup, choice_key, league_key

import jinja2
import webapp2
from operator import itemgetter

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def get_team_schedule(team_number):
    """
        Get the schedule data for a particular team over the whole season

        :parameter team_number: The number of the team whose data to return
        :type str or int
        :return: An array containing, for each week the team competes, a dictionary:
            - competition_name: The name of the event (string)
            - event_key: The datastore key for the root_event for this event (string)
            - tba_url: The link to tba page for this event (string)
            - points: The number of points(our system) this team scored at this event (int)
        If the team is not competing in a particualar week, the following defualt data is returned:
            - competition_name: ""
            - tba_url: ""
            - points: 0
            - event_key: ''
    """
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
        schedule[event_week - 1]['event_key'] = root_event.key.id()
        schedule[event_week - 1]['tba_url'] = globals.public_event_url.format(root_event.key.id())
        schedule[event_week - 1]['points'] = points
    return schedule


def get_team_lists(user_id, week_number):
    """
        Return the bench and active team lists for a particular user on a particular week

        :parameter user_id: The id of the user to gather lists from
        :type str or int
        :parameter week_number: The week to gather data on
        :type str or int
        :return: An array of two arrays(lineup, bench) containing, for each team in the lineup, a dictionary:
            - number: The number of the team (int)
            - detail_url: A link to the team's individual page (string)
            - schedule: An array containing scheduling data (schedule) (See get_team_schedule())
            - total_points: The number of points(our system) this team scored in total.  (int)
                If week_number is not editable, this is actually the points scored this week, not total
            - disabled: Is 'True' if team is locked because of good performance (string(bool))
        For each team in the bench list, the dictionary contains the following:
            - number: The number of the team (int)
            - total_points: The number of points(our system) this team scored in total.  (int)
                If week_number not is editable, this is actually the points scored this week, not total
            - disabled: Is 'True' if team is locked because of good performance (string(bool))
    """
    account = account_key(user_id).get()
    choice = choice_key(account.key, account.league).get()

    lineup = lineup_key(choice_key(account.key, account.league), week_number).get()
    active_lineup = lineup.active_teams

    if week_number < globals.get_current_editable_week():
        roster = lineup.weekly_roster
    else:
        roster = choice.current_team_roster

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
            event_key = get_team_schedule(int(number))[int(week_number) - 1]['event_key']  # -1 convert to 0-based index
            if event_key:  # Check if the team is competing that week
                team['total_points'] = get_team_points_at_event(int(number), event_key)

        if str(number) in get_top_teams(globals.number_of_locked_teams):
            team['disabled'] = 'True'
        current_lineup.append(team)

    bench_numbers = []
    for team in roster:  # Just trust me on this one, don't mess with this
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
            event_key = get_team_schedule(int(number))[int(week_number) - 1]['event_key']  # -1 convert to 0-based index
            if event_key:  # Check if the team is competing that week
                total_points = get_team_points_at_event(int(number), event_key)
        disabled = ''
        if str(number) in get_top_teams(globals.number_of_locked_teams):
            disabled = 'True'
        current_bench.append({'number':number, 'total_points': total_points, 'disabled': disabled})


    return [current_lineup, current_bench]


def get_current_roster(user_id):
    """
        Return the list of teams currently on the roster

        :parameter user_id: The id of the user to gather list from
        :type str or int
        :return: An array containing, for each team in the roster, a dictionary:
            - number: The team number(int)
            - name: The team name (string)
            - detail_url: A link to the team's individual page (string)
            - total_points: The number of points(our system) this team scored in total.  (int)
            - disabled: Is 'True' if team is locked because of good performance (string(bool))
    """
    account = account_key(user_id).get()
    choice = choice_key(account.key, account.league).get()
    roster = choice.current_team_roster

    current_roster = []
    for number in roster:
        team = {}
        team['number'] = number
        team['name'] = root_team_key(str(number)).get().name
        team['detail_url'] = '/allianceManagement/teamDetail/%s' % number
        team['total_points'] = get_points_to_date(int(number))

        if str(number) in get_top_teams(globals.number_of_locked_teams):
            team['disabled'] = 'True'

        current_roster.append(team)

    return sorted(current_roster, key=itemgetter('total_points'), reverse=True)

def get_top_teams(number):
    """Return a list of the top teams"""
    query = RootTeam.query().order(-RootTeam.total_points)
    teams = query.fetch(number)
    teamlist = []
    for team in teams:
        teamlist.append(team.key.id())
    return teamlist


def is_week_editable(week_number):
    """Return if the week is editable or not"""
    return globals.get_current_editable_week() <= int(week_number)


class alliance_portal(webapp2.RequestHandler):
    def get(self):
        """
            The main dashboard for league + personal info

            Contains information on the following:
                - The league schedule, including bye weeks and who plays who
                - The leader board, showing bench points and league points for each player, ranked
                - The current user's lineup for each week, including the points scored for past weeks
                - The current user's current roster
         """
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        #Make global call to get user information
        account = globals.get_or_create_account(user)
        league_id = account.league
        if league_id != '0':
            draft_over = league_key(league_id).get().draft_current_position == -1

            #Only allow access to this page after the draft has completed
            if draft_over:
                #Proccess league info
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

                current_roster = get_current_roster(user_id)

                user_schedule = get_readable_user_schedule(user_id)

                watchlist_raw = account.watchlist
                watch_list = get_watchlist(watchlist_raw)

                template_values = {
                                'user': user.nickname(),
                                'logout_url': logout_url,
                                'league_name': league_name,
                                'draft_state': globals.get_draft_state(account),
                                'week_table': week_table,
                                'total_points': total_points,
                                'leader_board': leader_board,
                                'schedule': league_schedule,
                                'roster': current_roster,
                                'watch_list': watch_list,
                                'week_number': globals.get_current_editable_week(),
                                'user_schedule': user_schedule
                                }

                template = JINJA_ENVIRONMENT.get_template('templates/alliance_management_portal.html')
                self.response.write(template.render(template_values))
            else:
                globals.display_error_page(self, self.request.referer, error_messages.draft_needs_to_be_completed)
        else:
            globals.display_error_page(self, self.request.referer, error_messages.need_to_be_a_member_of_a_league)


class update_lineup(webapp2.RequestHandler):
    def get(self, week_number):
        """
            Update the active teams for the user and redirects them to /viewAlliance/ for the week number
            Expects a post parameter: 'action' to be one of the following:
                - bench: Takes a team off the active lineup
                - putin: Adds a team to the lineup
                - drop: Drops a team from the user's roster
            Expects a post parameter: 'team_number' to be the number of the team to perform this action on

            :parameter week_number: Taken from the url, in string form
        """
        action = self.request.get('action')
        team_number = self.request.get('team_number')

        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()

        account = globals.get_or_create_account(user)
        league_id = account.league

        choice = choice_key(account_key(user_id), league_id).get()
        roster = []

        for team in choice.current_team_roster:
            roster.append(int(team))

        #Only allow changes to the lineup if the week is editable
        error = False
        if is_week_editable(week_number):
            active_lineup = lineup_key(choice_key(account.key, league_id), week_number).get()
            if action == "bench":
                active_lineup.active_teams.remove(int(team_number))
            elif action == "putin":
                if len(active_lineup.active_teams) < maximum_active_teams:
                    if int(team_number) in roster:
                        active_lineup.active_teams.append(int(team_number))
                    else:
                        error = True
                else:
                    error = True
                    globals.display_error_page(self, self.request.referer,  error_messages.maximum_active_teams_reached)
            elif action == "drop":
                if not str(team_number) in get_top_teams(globals.number_of_locked_teams):
                    choice = choice_key(account.key, league_id).get()
                    choice.current_team_roster.remove(int(team_number))

                    for week_num in range(int(week_number), globals.number_of_official_weeks):
                        lineup = lineup_key(choice.key, week_num).get()
                        if int(team_number) in lineup.active_teams:
                            active_lineup.active_teams.remove(int(team_number))

                    choice.put()
            active_lineup.put()
        if not error:
            self.redirect(self.request.referer)


class view_alliance(webapp2.RequestHandler):
    def get(self, week_number):
        """
            Handle the requests to see data for all alliances. Displays a past_alliance or alliance_management tab appropriately.

            :parameter week_number: Week number taken from the url, string form
            For each team on the bench and active lineup: displays information about each team's past performance
            Also displays opponent's active and bench lineup
        """
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
            point_totals = []
            for team_list in team_lists:
                point_total = 0
                for team in team_list:
                    point_total += team['total_points']
                point_totals.append(point_total)

            opponent_name = ""
            opponent_point_totals = []
            team_listss = [team_lists]
            if get_opponent(user_id, week_number) != globals.schedule_bye_week:
                opponent_team_lists = get_team_lists(get_opponent(user_id, week_number), week_number)
                opponent_point_totals = []
                for team_list in opponent_team_lists:
                    opponent_point_total = 0
                    for team in team_list:
                        opponent_point_total += team['total_points']
                    opponent_point_totals.append(opponent_point_total)

                opponent_name = get_opponent_name(user_id, week_number)
                team_listss.append(opponent_team_lists)


            #Send html data to browser
            template_values = {
                            'user': user.nickname(),
                            'logout_url': logout_url,
                            'league_name': league_name,
                            'draft_state': globals.get_draft_state(account),
                            'week_number': int(week_number),
                            'point_totals': [point_totals, opponent_point_totals],
                            'team_listss': team_listss,
                            'opponent_name': opponent_name,
                            }

            if is_week_editable(week_number):
                template = JINJA_ENVIRONMENT.get_template('templates/alliance_management.html')
            else:
                template = JINJA_ENVIRONMENT.get_template('templates/past_alliances.html')
            self.response.write(template.render(template_values))
        else:
            globals.display_error_page(self, self.request.referer, error_messages.draft_needs_to_be_completed)


class team_detail_page(webapp2.RequestHandler):
    def get(self, team_number):
        """
            Display detailed information on a single team

            :param team_number: The team number, gathered from the url, in string form
            Includes the following information:
                - Schedule: Which events is this team attending. Also gives the points scored (for past events)
                - Point breakdown: For each event, a detailed breakdown of where all of their points came
        """
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
        tba_team_url = globals.public_team_url.format(team_number)

        event_breakdowns = []
        point_breakdown = []
        for event in get_team_schedule(int(team_number)):
            if event['competition_name'] != '' and event['competition_name']:
                event_breakdowns.append(get_point_breakdown_display(int(team_number), event['event_key']))
        
        for i, name in enumerate(humman_readable_point_categories):
            point_breakdown.append([])  # Create the new row

            #Build the data neccessary for the title/tooltip
            title = {'title':name, 'explanation': explanation_of_point_categories[i]}

            point_breakdown[i].append(title)  # Add the tile for the first column
            category_total = 0
            for event in event_breakdowns:
                #Event is a value in the form [cat1,cat2...] 
                category_total += event[i]['points']  # Build the total for the end of the row
                event_text = ""
                if 'tooltip' in event[i]:  # If there's a tooltip, pass it on to the page
                    point_breakdown[i].append({'points': event[i]['display'], 'tooltip': event[i]['tooltip']})
                else:
                    point_breakdown[i].append(event[i]['display'])  # For each event, add the point display
            point_breakdown[i].append(category_total)  # Finally, add the total

        point_breakdown.append([])  # For totals
        index_of_totals_row = len(humman_readable_point_categories)
        overall_total = 0
        point_breakdown[index_of_totals_row].append('Overall Total:')  # Left column row title
        for event in get_team_schedule(int(team_number)):
            if event['competition_name'] != '' and event['competition_name']:
                overall_total += event['points']
                point_breakdown[index_of_totals_row].append("")  # For each event, add the total value
        point_breakdown[index_of_totals_row].append(overall_total)  # Finally, add the total

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'league_name': league_name,
                        'draft_state': globals.get_draft_state(account),
                        'team_data': team_data,
                        'team_name': team_name,
                        'tba_team_url': tba_team_url,
                        'pointbreakdown': point_breakdown,
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/team_detail.html')
        self.response.write(template.render(template_values))


application = webapp2.WSGIApplication([('/allianceManagement/viewAlliance', alliance_portal),
                                       ('/allianceManagement/viewAlliance/(.*)', view_alliance),  # Week number
                                       ('/allianceManagement/updateLineup/(.*)', update_lineup),  # Week number
                                       ('/allianceManagement/teamDetail/(.*)', team_detail_page),  # Team number
                                       ], debug=True)


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

# Down here to resolve import issues
from points import get_team_points_at_event, get_points_to_date, get_point_breakdown_display, \
    humman_readable_point_categories, explanation_of_point_categories
from league_management import get_leader_board, get_readable_schedule, get_opponent, get_opponent_name, get_readable_user_schedule
from drafting import get_watchlist
from globals import maximum_active_teams
import globals