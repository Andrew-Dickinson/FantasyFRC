#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db, ndb
from google.appengine.api import users


import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

from customMechanize import _mechanize

home_url = "http://pvue.ghaps.org/pxp/Home_PXP.aspx"

def student_key(student_account_id):
    """Constructs a Datastore key for a Student entity with a user id."""
    return db.Key.from_path('Student', student_account_id)

class Student(db.Model):
    username = db.StringProperty(required=True)
    password = db.StringProperty(required=True)
    name = db.StringProperty(required=False)
    grades = db.FloatProperty(required=False)


class MainPage(webapp2.RequestHandler):

    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()
        user_id = user.user_id()

        if user is None:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            student_query = db.GqlQuery("SELECT * WHERE ANCESTOR IS :1", student_key(user_id))
            students = student_query.fetch(1)
            past_username = ''
            past_password = ''
            if len(students) == 1:
                self.getCurrentInfo(user_id)
                past_username = students[0].username
                for i in students[0].password: past_password += "*"

            template_values = {
                               'user':user.nickname(),
                               'user_id':user_id,
                               'logout_url':users.create_login_url(self.request.uri),
                               'username':past_username,
                               'password':past_password
                               }

            template = JINJA_ENVIRONMENT.get_template('index.html')
            self.response.write(template.render(template_values))

    def getCurrentInfo(self, user_id):
        student_query = db.GqlQuery("SELECT * WHERE ANCESTOR IS :1", student_key(user_id))
        students = student_query.fetch(1)
        username = students[0].username
        password = students[0].password

        br = _mechanize.Browser()
        br.addheaders = [('username', username), ('password', password)]
        br.set_handle_robots(False)
        response = br.open(home_url)
        self.response.write(response.read())

class UpdateInfo(webapp2.RequestHandler):

    def post(self):
        user_id = self.request.get('user_id')
        student_query = db.GqlQuery("SELECT * WHERE ANCESTOR IS :1", student_key(user_id))
        students = student_query.fetch(4)
        for student in students:
            old_password = student.password
            student.delete()

        new_password = self.request.get('password')
        for c in new_password:
            if c != "*":
                break;
            else:
                new_password = old_password

        student = Student(parent=student_key(user_id), username=self.request.get('username'), password=new_password)
        student.name = "Bob"
        student.put()

        self.redirect('/')

application = webapp2.WSGIApplication([
                                       ('/', MainPage),
                                       ('/updateuser', UpdateInfo)
                                       ], debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()