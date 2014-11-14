import logging

from globals import no_data_display
from award_classification import AwardType
from alliance_management import get_team_schedule
from datastore_classes import Team_Event, team_event_key, team_key
from progress_through_elimination_classification import UNDETERMINED, DIDNTQUALIFY, QUARTERFINALIST, SEMIFINALIST, FINALIST, WINNER
"""Uses point system described in http://www.chiefdelphi.com/media/papers/2574"""

points_per_qual_win = 2
points_per_qual_tie = 1
points_per_qual_loss = 0

elemination_progress_points = {
    UNDETERMINED: 0,
    DIDNTQUALIFY: 0,
    QUARTERFINALIST: 4,
    SEMIFINALIST: 10,
    FINALIST: 20,
    WINNER: 30
}

elimination_progress_names = {
    UNDETERMINED: "Unknown",
    DIDNTQUALIFY: "Did not qualify",
    QUARTERFINALIST: "Quarterfinalist",
    SEMIFINALIST: "Semifinalist",
    FINALIST: "Finalist",
    WINNER: "Winner"
}

humman_readable_point_categories = [
    "Matches won in qualification", 
    "Matches tied in qualification", 
    "Matches lost in qualification", 
    "Progress in elemination", 
    "Seed",  
    "Awards"
]

point_breakdown_display_style = [
    "%s wins",
    "%s ties",
    "%s losses",
    "%s",
    "Rank %s",
    "%s   " #Awards are treated special becauase they're given a hyperlink
]

explanation_of_point_categories = [
    "Every match won in the qualification rounds earns a team 2 points",
    "Every match lost in the qualification rounds earns a team 1 point",
    "Teams get no points for matches lost during the qualification rounds",
    "Teams get points for their progress through elemination rounds as follows: Quarterfinalist: 4, Semifinalist: 10, Finalist: 20, Winner: 30",
    "Teams seeded 1st get 20, 2nd-3rd get 12, 4th-8th get 6, 9th-12th get 3, 13th-16th get 2",
    "Awards are assigned points based off this document"
]

points_for_seed_1 = 20
points_for_seed_2to3 = 12
points_for_seed_4to8 = 6
points_for_seed_9to12 = 3
points_for_seed_13to16 = 2

def get_seed_points(seed):
    if seed == 1:
        return points_for_seed_1
    elif seed >= 2 and seed <= 3:
        return points_for_seed_2to3
    elif seed >= 4 and seed <= 8:
        return points_for_seed_4to8
    elif seed >= 9 and seed <= 12:
        return points_for_seed_9to12
    elif seed >= 13 and seed <= 16:
        return points_for_seed_13to16
    else:
        return 0

'''
Returns both the raw data values(number of wins) and the points for each category
'''
def get_category_and_value_breakdown(team_number, event_id):
    team_event = Team_Event.get_or_insert(team_event_key(team_key(str(team_number)), event_id).id(), parent=team_key(str(team_number)))
    
    # Defualt values if event doesn't exist
    qual_win_points = 0
    qual_tie_points = 0
    qual_loss_points = 0
    elimination_points = 0
    seed_points = 0
    award_points = 0

    event_wins = 0
    event_ties = 0
    event_losses = 0
    elimination_progress_name = ""
    event_rank = 0
    event_award_names_colon_points = []

    #If there is no data for this event, represent it by Sending a blank breakdown
    breakdown = []

    if team_event.win: #For debug purposes, so unloaded events don't raise exceptions
        qual_win_points = team_event.win * points_per_qual_win
        event_wins = team_event.win
        qual_tie_points = team_event.tie * points_per_qual_tie
        event_ties = team_event.tie
        qual_loss_points = team_event.loss * points_per_qual_loss
        event_losses = team_event.loss
        elimination_points = elemination_progress_points[team_event.elimination_progress]
        elimination_progress_name = elimination_progress_names[team_event.elimination_progress]
        seed_points = get_seed_points(team_event.rank)
        event_rank = team_event.rank
        award_points = 0
        for i, award in enumerate(team_event.awards):
            if award != AwardType.WINNER and award != AwardType.FINALIST: #Don't give double points for winners/finalists
                award_points += award_points_by_TBA_id[award]
                event_award_names_colon_points.append(team_event.award_names[i] + ": " + str(award_points_by_TBA_id[award]))
        breakdown = [
        {'points':qual_win_points, 'raw_value': event_wins},
        {'points':qual_tie_points, 'raw_value': event_ties},
        {'points':qual_loss_points, 'raw_value': event_losses},
        {'points':elimination_points, 'raw_value': elimination_progress_name},
        {'points':seed_points, 'raw_value': event_rank},
        {'points':award_points, 'raw_value': event_award_names_colon_points},
        ]

    return breakdown

'''
Returns a list of point values that are orderered as described by the humman_readable_point_categories variable
'''
def get_point_breakdown_for_event(team_number, event_id):
    detailed_breakdown = get_category_and_value_breakdown(team_number, event_id)

    breakdown = []
    for category in detailed_breakdown:
        breakdown.append(category['points'])

    return breakdown

def get_team_points_at_event(team_number, event_id):
    breakdown = get_point_breakdown_for_event(team_number, event_id)
    return sum(breakdown)

def get_points_to_date(team_number):
    schedule = get_team_schedule(team_number)
    points = 0
    for week, event in enumerate(schedule):
        if schedule[week]['competition_name'] != "":
            event_key = schedule[week]['event_key']
            points = points + get_team_points_at_event(team_number, event_key)
    return points

def get_point_breakdown_display(team_number, event_id):
    detailed_breakdown = get_category_and_value_breakdown(team_number, event_id)
    display_output = []
    if len(detailed_breakdown) != 0: #There is data for this event
        for i, category in enumerate(detailed_breakdown):
            if (i < len(detailed_breakdown) - 1): #Don't use this style for awards
                format = point_breakdown_display_style[i] #Get the template from above
                display_output.append({
                                    'display':format % (category['raw_value']), #Use template to create description
                                    'points': category['points'] #Include raw points for the sake of totals
                                    })
            else: #This is the awards category
                award_display = ""
                format = point_breakdown_display_style[i]
                for award in category['raw_value']:
                    award_display = award_display + (format % award)
                if award_display == "":
                    award_display = "No Awards won at this event"
                display_output.append({
                                    'display': category['points'],
                                    'tooltip': award_display,
                                    'points': category['points']})
    else: #There is no data
        for i in humman_readable_point_categories:
            display_output.append({
                                'display': no_data_display,
                                'points': 0
                                })
    return display_output


#Uses ids based off of https://github.com/the-blue-alliance/the-blue-alliance/blob/master/consts/award_type.py
award_points_by_TBA_id = {
    0 : 42,
    1 : 30,
    2 : 20,

    3 : 8,
    4 : 4,
    5 : 2,
    6 : 2,
    7 : 2,
    8 : 2,

    9 : 36,
    10 : 20,
    11 : 2,
    12 : 2,
    13 : 5,
    14 : 5,
    15 : 15,
    16 : 15,
    17 : 15,
    18 : 2,
    19 : 2,
    20 : 15,
    21 : 15,
    22 : 2,
    23 : 15,
    24 : 15,
    25 : 2,
    26 : 2,
    27 : 2,
    28 : 2,
    29 : 15,
    30 : 2,
    31 : 2,
    32 : 2,
    33 : 2,
    34 : 2,
    35 : 2,
    36 : 2,
    37 : 2,
    38 : 15,
    39 : 2,
    40 : 2,
    41 : 2,
    42 : 2,
    43 : 2,
    44 : 2,
    45 : 2,
    46 : 2,
    47 : 2,
    48 : 2,
    49 : 2,
    50 : 2,
    51 : 2,
    52 : 2,
    53 : 2,
    54 : 2,
    55 : 2,
    56 : 2,
    57 : 2,
    58 : 2,
    59 : 5,
    60 : 2,
    61 : 2,
    62 : 2,
    63 : 2,
    64 : 15,
    65 : 2,
    66 : 42, #I consider golden corn dog to be equivalent to chairman's
}