##########################
# Authors: Nate Welch
# Version: 10/11/2021
# Purpose: Parse Schedules Taken from CampusDish
##########################

import re
import json


def break_into_day_schedules(schedule):
    # type: (dict) -> str
    """ This function takes the awful, scary JSON schedule and breaks it down into individual days/meals"""
    return re.findall("\{.*?\}", str(schedule))


def parse_courtyard_schedules(schedules):
    # type: (list) -> dict
    """ This function takes the list of individual day schedules, and makes them a little more user friendly"""
    week = {'Monday': {}, 'Tuesday': {}, 'Wednesday': {}, 'Thursday': {}, 'friday': {}, 'Saturday': {}, 'Sunday': {}}
    i = 0
    for day in week:
        week[day]['breakfast'] = {'start': json.loads(schedules[i])['UtcStartTime'],
                                  'stop': json.loads(schedules[i])['UtcEndTime']}
        i = i + 1
    for day in week:
        week[day]['lunch'] = {'start': json.loads(schedules[i])['UtcStartTime'],
                              'stop': json.loads(schedules[i])['UtcEndTime']}
        i = i + 1
    for day in week:
        week[day]['dinner'] = {'start': json.loads(schedules[i])['UtcStartTime'],
                               'stop': json.loads(schedules[i])['UtcEndTime']}
        i = i + 1

    return week


def parse_schedules(schedules):
    # type: (list) -> dict
    """ Takes day schedules without meals and makes them more user friendly in an order-independent way"""
    week = {'Monday': {}, 'Tuesday': {}, 'Wednesday': {}, 'Thursday': {}, 'friday': {}, 'Saturday': {}, 'Sunday': {}}
    i = 0
    while i < len(schedules):
        currSched = json.loads(schedules[i])
        if currSched["WeekDay"] == 1:
            week['Monday'] = {'start': currSched['UtcStartTime'],
                              'stop': currSched['UtcEndTime']}
        elif currSched["WeekDay"] == 2:
            week['Tuesday'] = {'start': currSched['UtcStartTime'],
                               'stop': currSched['UtcEndTime']}
        elif currSched["WeekDay"] == 3:
            week['Wednesday'] = {'start': currSched['UtcStartTime'],
                                 'stop': currSched['UtcEndTime']}
        elif currSched["WeekDay"] == 4:
            week['Thursday'] = {'start': currSched['UtcStartTime'],
                                'stop': currSched['UtcEndTime']}
        elif currSched["WeekDay"] == 5:
            week['friday'] = {'start': currSched['UtcStartTime'],
                              'stop': currSched['UtcEndTime']}
        elif currSched["WeekDay"] == 6:
            week['Saturday'] = {'start': currSched['UtcStartTime'],
                                'stop': currSched['UtcEndTime']}
        elif currSched["WeekDay"] == 0:
            week['Sunday'] = {'start': currSched['UtcStartTime'],
                              'stop': currSched['UtcEndTime']}
        i = i + 1
    for day in week:
        if not bool(week[day]):
            week[day] = {'start': None, 'stop': None}
    return week
