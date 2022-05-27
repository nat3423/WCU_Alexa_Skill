###################################################
# Western Carolina University
# Fall 2021 - CS Capstone
# Alexa WCU Skill
# David Jennings & Nate Welch
##################################################


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
from ask_sdk_model.services.directive import (SendDirectiveRequest, Header, SpeakDirective)



def academic_calendar(handler_input):
    """Generates a calendar in the form of a python list with dict object representing the days in the calendar.

    This method uses selenium to parse the academic calendar found on the WCU website. It first gets the table element
    containing the calendar and then sorts through the elements in said table to create a 2d python list, each inner list
    representing a week in the calendar. Each inner list will have 7 dict object which has 2 keys: Day, Event.
    Day - holds the numerical value of the day of the month.
    Event - holds a string which represents the event on said day, defaults to 'No Events' if no event is detected.

    Example::

        selenium_parsing.academic_calendar() --->

        27 : 8a Fifth Week Grades Due | 28 : No Events | 29 : Very Important Example Entry | 30 : No Events | 1 : No Events
        -----------------------------------------------------------------------------------------------------------------
        2 : No Events | 3 : No Events | 4 : No Events | 5 : No Events | 6 : No Events | 7 : No Events | 8 : 8a Homecoming
        -----------------------------------------------------------------------------------------------------------------
        9 : No Events | 10 : No Events | 11 : No Events | 12 : No Events | 13 : No Events | 14 : 8a First 8Wk Session Ends
        -----------------------------------------------------------------------------------------------------------------
        15 : No Events | 16 : 8a 2nd Session Begins | 17 : No Events | 18 : No Events | 19 : No Events | 20 : No Events
        -----------------------------------------------------------------------------------------------------------------
        21 : No Events | 22 : National Holiday | 23 : No Events | 24 : No Events | 25 : 8a Last Day to Drop with a "W"
        -----------------------------------------------------------------------------------------------------------------
        26 : No Events | 27 : No Events | 28 : Advising Day - No Classes| 29 : No Events | 30 : No Events | 31 : No Events
        -----------------------------------------------------------------------------------------------------------------

        Day - 29
        Event - Very Important Example Entry
        --------->
        {"Day": "29", "Event": "Very Important Example Entry"}

    """

    start_time = time.perf_counter()
    timer_length = 8
    max_to_send = 5
    amount_sent = 0

    # The following 4 lines will get us the source code and needed table for parsing the calendar data

    options = Options()
    options.binary_location = "/opt/headless-chromium"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--single-process")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome("/opt/chromedriver",options=options)

    driver.get("https://www.wcu.edu/learn/academic-calendar.aspx")
    driver.switch_to.frame(2)
    calendar_html = driver.find_element(By.CLASS_NAME, 'twMonthTable')

    week_days = []  # this list will temporarily hold week day (dates) until it merges with events
    events_in_weeks = []  # this list will temporarily event descriptions until it merges with days

    # this loop will add lists to the weeks lists so that they have a length representing the number of weeks in the month
    for week in calendar_html.find_elements(By.TAG_NAME, 'tr'):
        if len(week.find_elements(By.TAG_NAME, 'td')) > 1 and \
                (week.find_elements(By.TAG_NAME, 'td')[0]).get_attribute('class') == 'twMonthForceLabel':
            week_days.append([])

        if len(week.find_elements(By.TAG_NAME, 'td')) > 1 and \
                (week.find_elements(By.TAG_NAME, 'td')[0]).get_attribute('class') == 'twMonthForceCell':
            events_in_weeks.append([])

        if time.perf_counter() - start_time > (timer_length * amount_sent) and amount_sent <= max_to_send:
            get_progressive_response(handler_input, amount_sent + 1)
            amount_sent = amount_sent + 1


    # every 'td' list starts with a 'twMothForce[Cell | Label]' which contains no needed data so to counteract this
    #  non-essential element, the day in week starts at -1 and increments, and only add the day if it is >= 0
    day_in_week = -1

    week_num = 0  # keep track of weeks by indexing at 0
    events_num = 0  # keep track of events by their day in the week by indexing at 0
    events = False  # calendar alternates between dates and events

    # the for loop iterates through the 'tr' list which will contain lists of 'td' elements which hold the calendar data
    for element in calendar_html.find_elements(By.TAG_NAME, 'tr'):

        # The lists containing the data we need always have a first element of class 'twMonthForce[Label | Cell]'
        if len(element.find_elements(By.TAG_NAME, 'td')) > 1 and \
                ((element.find_elements(By.TAG_NAME, 'td')[0]).get_attribute('class') == 'twMonthForceLabel' or
                (element.find_elements(By.TAG_NAME, 'td')[0]).get_attribute('class') == 'twMonthForceCell'):

            if events:
                for day in element.find_elements(By.TAG_NAME, 'td'):

                    if day_in_week >= 0:  # checking that it is not the first element which is empty
                        if len(day.text) <= 1:  # if the text has a length equal or shorter than 1 it has no events
                            events_in_weeks[events_num].append("No Events")

                        else:
                            events_in_weeks[events_num].append(day.text)

                    day_in_week += 1

                events_num += 1
                events = not events  # switches to check dates

            else:
                for day in element.find_elements(By.TAG_NAME, 'td'):

                    if day_in_week >= 0:  # checking that it is not the first element which is empty
                        week_days[week_num].append(day.text)

                    day_in_week += 1

                week_num += 1
                events = not events  # switches to check events

        day_in_week = -1  # reset the day of the week at every iteration of the loop

        if time.perf_counter() - start_time > (timer_length * amount_sent) and amount_sent <= max_to_send:
            get_progressive_response(handler_input, amount_sent + 1)
            amount_sent = amount_sent + 1

    calendar = []

    for week in week_days:
        calendar.append([])

    # this loop parses through the week_days and events_in_weeks to create a dictionary object with the date and event
    for i in range(0, len(week_days)):

        for j in range(0, len(week_days[i])):

            # this checks to ensure the two lists have the same length, if they don't we append elements to make them even
            if len(events_in_weeks[i]) < len(week_days[i]):
                empty = len(week_days[i])-len(events_in_weeks[i])

                for k in range(empty):
                    events_in_weeks[i].append(events_in_weeks[i][0])

            calendar[i].append({"Day": week_days[i][j], "Event": events_in_weeks[i][j]})

        if time.perf_counter() - start_time > (timer_length * amount_sent) and amount_sent <= max_to_send:
            get_progressive_response(handler_input, amount_sent + 1)
            amount_sent = amount_sent + 1

    driver.quit()
    return calendar

def get_progressive_response(handler_input, index):
    request_id = handler_input.request_envelope.request.request_id
    directive_header = Header(request_id=request_id)
    if index == 0:
        speech = SpeakDirective("OK, Fetching academic Calendar.")
    elif index == 1:
        speech = SpeakDirective("Still working on it.")
    elif index == 2:
        speech = SpeakDirective("Almost done!")
    elif index == 3:
        speech = SpeakDirective("Any minute now.")
    elif index == 4:
        speech = SpeakDirective("Stall #5")
    elif index == 5:
        speech = SpeakDirective("Stall #6")
    elif index == 6:
        speech = SpeakDirective("Stall #7")
    else:
        speech = SpeakDirective("Finalizing.")
    directive_request = SendDirectiveRequest(header=directive_header, directive=speech)
    directive_service_client = handler_input.service_client_factory.get_directive_service()
    directive_service_client.enqueue(directive_request)
