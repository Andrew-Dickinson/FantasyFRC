#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import logging

import globals

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users

from datastore_classes import league_key

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
                        'show_league_standings': globals.display_league_standings(account),
                        }
            template = JINJA_ENVIRONMENT.get_template('templates/index.html')
            self.response.write(template.render(template_values))

application = webapp2.WSGIApplication([
                                       ('/', MainPage)
                                       ], debug=True)

def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()