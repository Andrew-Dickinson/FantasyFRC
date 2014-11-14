from google.appengine.ext import ndb


#There are 5 root keys
def league_key(commissioner_id):
    """League keys are based off of the id of the person who commissions them"""
    return ndb.Key(League, commissioner_id)


def account_key(account_id):
    """Constructs a Datastore key for a account entity with a user id."""
    return ndb.Key(Account, account_id)


def team_key(team_number):
    """Constructs a Datastore key for a team given its number"""
    return ndb.Key('Team',  team_number)


def root_event_key(event_id):
    """Constructs the Datastore key for an event given its event_id"""
    return ndb.Key(Root_Event, event_id)


def root_team_key(team_number):
    """Constructs the Datastore key for a root team given its number"""
    return ndb.Key(Root_Team, team_number)


#Every other key is based off of the root keys
def team_event_key(team_key, event_id):
    """Constructs a Datastore key for a team_event entity with a team_key as parent and event_id as id"""
    return ndb.Key(Team_Event, event_id, parent=team_key)


def Choice_key(player_key, league_id):
    """Constructs a Datastore key for a Choice entity with a player_key as parent and league_id as id"""
    return ndb.Key(Choice, str(league_id), parent=player_key)


def lineup_key(choice_key, week_number):
    """Constructs a Datastore key for a week choice entity with a choice_key as parent and week_number as id"""
    return ndb.Key(Lineup, str(week_number), parent=choice_key)


def draft_pick_key(league_key, position):
    """Constructs a Datastore key for a draft pick entity with a league_key as parent and a position as id"""
    return ndb.Key(Draft_Pick, str(position), parent=league_key)


class League(ndb.Model):
    """Stores players in the league and the league specific settings"""
    players = ndb.IntegerProperty(repeated=True)
    name = ndb.StringProperty()
    draft_current_position = ndb.IntegerProperty()
    draft_current_timeout = ndb.DateTimeProperty()


class Root_Event(ndb.Model):
    """Stores the data for an entire event, differs from Team_Event by having a larger scope"""
    name = ndb.StringProperty()
    teams = ndb.IntegerProperty(repeated=True)
    week = ndb.IntegerProperty()


class Root_Team(ndb.Model):
    """Stores information such as scheduling and team name"""
    name = ndb.StringProperty()
    events = ndb.StringProperty(repeated=True)


class Account(ndb.Model):
    """Stores data for an individual account"""
    nickname = ndb.StringProperty()
    league = ndb.StringProperty()


class Team_Event(ndb.Model):
    """Stores a team's data for a single event"""
    rank = ndb.IntegerProperty()
#     qualification_score = ndb.IntegerProperty()
#     assist_points = ndb.IntegerProperty()
#     autonomous_points = ndb.IntegerProperty()
#     truss_and_catch_points = ndb.IntegerProperty()
#     teleop_points = ndb.IntegerProperty()
    win = ndb.IntegerProperty()
    loss = ndb.IntegerProperty()
    tie = ndb.IntegerProperty()
#     disqualified = ndb.IntegerProperty()
    played = ndb.IntegerProperty()
    awards = ndb.IntegerProperty(repeated=True)
    award_names = ndb.StringProperty(repeated=True)
    elimination_progress = ndb.IntegerProperty()


class Choice(ndb.Model):
    """Stores all of the draft data for a single account for a single league"""
    current_team_roster = ndb.IntegerProperty(repeated=True)


class Lineup(ndb.Model):
    """Stores the lineup for a single week for a single account"""
    active_teams = ndb.IntegerProperty(repeated=True)


class Draft_Pick(ndb.Model):
    """Stores all of the information about one draft pick for a single league"""
    player = ndb.StringProperty()
    team = ndb.IntegerProperty()
