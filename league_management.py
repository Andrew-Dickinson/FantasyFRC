#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users
from google.appengine.ext import ndb

from datastore_classes import account_key, Account, League, league_key, Choice_key

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class create_League(webapp2.RequestHandler):
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        logout_url = users.create_logout_url('/')

        account = Account.get_or_insert(user_id)
        if account.nickname == None:
            account.nickname =  user.nickname()
            account.put()

        #Send html data to browser
        template_values = {
                        'user': user.nickname(),
                        'logout_url': logout_url,
                        'account_key': account_key(user_id).urlsafe(), #TODO Encrypt
                        }
        template = JINJA_ENVIRONMENT.get_template('templates/create_league.html')
        self.response.write(template.render(template_values))

class update_League(webapp2.RequestHandler):
    def post(self):
        #Get data from the post header
        commissioner_account_key = ndb.Key(urlsafe=self.request.get('account_key'))
        name = self.request.get('name')

        #Create/Update the league
        new_league = League.get_or_insert(commissioner_account_key.id())
        new_league.name = name
        new_league.put()

        #Make this the commissioner's league
        account = commissioner_account_key.get()
        account.league = new_league.key.id()
        account.put()

        self.redirect('/')

class leave_League(webapp2.RequestHandler):
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()

        #Current user's id, used to identify their data
        user_id = user.user_id()
        account = Account.get_or_insert(user_id)

        #Remove user's choices for the league
        Choice_key(account_key(user_id), account.league).delete()

        #Remove User's association with league
        account.league = '0'
        account.put()

        self.redirect('/')




application = webapp2.WSGIApplication([
                                       ('/leagueManagement/updateLeague', update_League),
                                       ('/leagueManagement/createLeague', create_League),
                                       ('/leagueManagement/leaveLeague', leave_League)
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()