#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

import globals
from datastore_classes import account_key, Account, League, Choice, Choice_key, league_key, Lineup, Draft_Pick

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

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
        draft_picks = Draft_Pick.query(ancestor=league.key).fetch()
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
            self.response.write('This league has already begun, or has finished its draft')

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