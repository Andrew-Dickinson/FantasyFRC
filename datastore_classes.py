from google.appengine.ext import ndb


#There are 6 root keys
def league_key(commissioner_id):
    """League keys are based off of the id of the person who commissions them"""
    return ndb.Key(League, commissioner_id)


def account_key(account_id):
    """Constructs a Datastore key for a account entity with a user id."""
    return ndb.Key(Account, str(account_id))


def team_key(team_number):
    """Constructs a Datastore key for a team given its number"""
    return ndb.Key('Team',  team_number)


def root_event_key(event_id):
    """Constructs the Datastore key for an event given its event_id"""
    return ndb.Key(RootEvent, event_id)


def root_team_key(team_number):
    """Constructs the Datastore key for a root team given its number"""
    return ndb.Key(RootTeam, team_number)

def global_settings_key():
    """Constructs the key for the global settings entity"""
    return ndb.Key(GlobalSettings, '0')


#Every other key is based off of the root keys
def team_event_key(team_key_val, event_id):
    """Constructs a Datastore key for a team_event entity with a team_key as parent and event_id as id"""
    return ndb.Key(TeamEvent, event_id, parent=team_key_val)


def choice_key(player_key, league_id):
    """Constructs a Datastore key for a Choice entity with a player_key as parent and league_id as id"""
    return ndb.Key(Choice, str(league_id), parent=player_key)


def lineup_key(choice_key_val, week_number):
    """Constructs a Datastore key for a week choice entity with a choice_key as parent and week_number as id"""
    return ndb.Key(Lineup, str(week_number), parent=choice_key_val)


def draft_pick_key(league_key_val, position):
    """Constructs a Datastore key for a draft pick entity with a league_key as parent and a position as id"""
    return ndb.Key(DraftPick, str(position), parent=league_key_val)


class League(ndb.Model):
    """Stores players in the league and the league specific settings"""
    players = ndb.IntegerProperty(repeated=True)  # Deprecated?
    name = ndb.StringProperty()
    snake_draft = ndb.BooleanProperty()
    draft_current_position = ndb.IntegerProperty()
    draft_current_timeout = ndb.DateTimeProperty()
    auto_start_draft_time = ndb.DateProperty()
    time_per_draft_pick = ndb.FloatProperty() #Minutes
    league_access_type = ndb.StringProperty()
    league_player_size_limit = ndb.IntegerProperty()
    number_of_locked_teams = ndb.IntegerProperty()
    number_of_draft_rounds = ndb.IntegerProperty()
    roster_size = ndb.IntegerProperty()
    active_lineup_size = ndb.IntegerProperty()



class RootEvent(ndb.Model):
    """Stores the data for an entire event, differs from TeamEvent by having a larger scope"""
    name = ndb.StringProperty()
    teams = ndb.IntegerProperty(repeated=True)
    week = ndb.IntegerProperty()


class RootTeam(ndb.Model):
    """Stores information such as scheduling and team name"""
    name = ndb.StringProperty()
    events = ndb.StringProperty(repeated=True)
    address = ndb.StringProperty()
    latlon = ndb.StringProperty()
    total_points = ndb.IntegerProperty()


class Account(ndb.Model):
    """Stores data for an individual account"""
    nickname = ndb.StringProperty()
    league = ndb.StringProperty()

    #In the form described in https://github.com/smarthimandrew/FantasyFRC/issues/12
    schedule = ndb.StringProperty(repeated=True)
    record = ndb.StringProperty(repeated=True)  # Uses the record variables in globals

    watchlist = ndb.IntegerProperty(repeated=True)


class GlobalSettings(ndb.Model):
    """Stores dynamic global settings"""
    editable_week = ndb.IntegerProperty()


class TeamEvent(ndb.Model):
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
    weekly_roster = ndb.IntegerProperty(repeated=True)

class DraftPick(ndb.Model):
    """Stores all of the information about one draft pick for a single league"""
    player = ndb.StringProperty()
    team = ndb.IntegerProperty()
    display_number = ndb.IntegerProperty()
