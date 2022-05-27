##########################
# Authors: Nate Welch & David Jennings
# Version: 05/24/2022
# Purpose: The Backend for our Alexa Skill
##########################

# Whole lotta imports
import pymysql
import datetime
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.api_client import DefaultApiClient
import ask_sdk_core.utils as ask_utils
from ask_sdk_model import Response
import sched_of_classes_scraping
from web_scraper import get_data, get_faculty_info
from schedule_parser import *
import selenium_parsing
from sched_of_classes_scraping import Class
from multiprocessing import Process, Pipe
import time
from ask_sdk_model.services.directive import (SendDirectiveRequest, Header, SpeakDirective)
from ask_sdk_model.ui import SimpleCard
import requests

# This function returns a connection to our database. If we plan to store secure data in the database, it would be
#  best to move the login info to a seperate file for security.
def connect():
    # type: () -> pymysql.Connection
    """This method returns a Connection to the database"""

    # Here we initialize the connection to None so it can be accessed outside the try-catch
    conn = None

    # We need to put it in a try-catch because it can throw a MySQLError
    try:

        # We connect to our database using our specific log in info
        conn = pymysql.connect(host='alexaskilldb.cgjytetmnhis.us-east-2.rds.amazonaws.com',
                               db='AlexaSkillDB',
                               user='admin',
                               passwd='cscapstone',
                               connect_timeout=10,
                               autocommit=True)
    except pymysql.MySQLError as e:
        # Print statements do not go back to the user, they are just logged.
        print("The database is offline.")

    return conn


# Connect to our database immediatly so any handler can access it
database = connect()


# This class was supplied by default
class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """Returns true if this handler can handle the intent"""

        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """"Handles any request that doesn't match up to any intent"""

        speech = "Hmm, I'm not sure. You can say Hello or Help. What would you like to do?"
        reprompt = "I didn't catch that. What can I help you with?"
        return handler_input.response_builder.speak(speech).ask(reprompt).response

# This class is the handler for "Static" questions. These are questions whose answers will note likely change often
# Thus we store the answer in the database, locate it by the type of question the user asked, then return the stored 
# answer.
class StaticIntentHandler(AbstractRequestHandler):
    """Handler for any and all static questions"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """Returns true if this handler can handle the intent"""
        return handler_input.request_envelope.request.intent.name in ["getLocationOfSchool", "howManyGradPrograms",
                                                                      "howManyMajors", "howManyOnlinePrograms",
                                                                      "howManyRemotePrograms",
                                                                      "onCampusHousingAvailability",
                                                                      "onCampusHousingRequirement",
                                                                      "onCampusParkingRequirement", "getLibraryAddress"]

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """"Handles the request by getting the answer related to the intent"""
        speech = self.get_answer(handler_input.request_envelope)

        handler_input.response_builder.speak(speech).set_card(
            SimpleCard(self.get_header_text(handler_input), speech))

        return handler_input.response_builder.response

    def get_header_text(self, handler_input):
        # type: (HandlerInput) -> String
        """Finds the name of the intent from the HandlerInput and returns a nicely formatted version that we can 
        display on their screen if applicable."""

        intentName = self.get_intent(handler_input.request_envelope)
        if intentName == "getLibraryAddress":
            return "Library Location"
        elif intentName == "getLocationOfSchool":
            return "School Location"
        elif intentName == "howManyMajors":
            return "Number of Majors"
        elif intentName == "howManyGradPrograms":
            return "Number of Graduate Programs"
        elif intentName == "howManyOnlinePrograms":
            return "Number of Online Programs"
        elif intentName == "howManyRemotePrograms":
            return "Number of Remote Programs"
        elif intentName == "onCampusHousingAvailability" or intentName == "onCampusHousingRequirement":
            return "On-Campus Housing"
        elif intentName == "onCampusParkingRequirement":
            return "On-Campus Parking"

    # TODO: Remove magic numbers
    def get_answer(self, request):
        # type: (RequestEnvelope) -> String
        """ Takes the JSON request, returns the appropriate answer from the database"""

        cursor = database.cursor()
        intentName = self.get_intent(request)

        # get the entire table
        cursor.execute("SELECT * FROM QuestionTable WHERE intent = " + "'" + intentName + "'")
        data = cursor.fetchall()

        # Take the first, and most likely only, result and get the second entry in the row which is the answer
        return data[0][1]

    def get_intent(self, request):
        # type: (RequestEnvelope) -> str
        """Helper method for get_answer()"""

        # Go into the request envelope and fetch the intent name
        return request.request.intent.name


class GetRestaurantHoursIntentHandler(AbstractRequestHandler):
    """ Handler for getting restaurant hours """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """ Checks if this handler is suitable for handling this request """
        return ask_utils.is_intent_name("getRestaurantHours")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """ Handles the restaurant hour request """

        # Get the name of the restaurant from the slots
        restaurant = self.get_restaurant_name(handler_input)

        # Get the schedule of this restaurant
        schedule = self.get_schedule(restaurant)

        # Break up this week-long schedule into day schedules
        schedules = break_into_day_schedules(schedule)

        # If there is a day supplied, use it. Otherwise, get today's weekday
        day = self.get_day_name(handler_input)
        if day is None:
            day = self.getWeekday()

        # If the restaurant is courtyard, it has individual meals so it needs special attention
        # Currently, the schedule does not have this for finals so it is commented out.
        """
        if restaurant == "courtyard":
            properSchedule = parse_courtyard_schedules(schedules)
            if self.get_meal_name(handler_input) is not None:
                meal = self.get_meal_name(handler_input)
                specificSched = properSchedule[day][meal]
            else:
                response = "Courtyard is open for "
                for meal in properSchedule[day]:
                    response = response + self.meal_sched_to_string(properSchedule[day][meal], meal) + ", "
                response = response[0:len(response) - 2]
                response = response + " on " + day
                return handler_input.response_builder.speak(response).response
        """

        # Get a nicely formatted schedule out of the original
        properSchedule = parse_schedules(schedules)

        # Get the formatted schedule of the day requested
        specificSched = properSchedule[day]

        # Build a string out of the schedule, restaurant, and day
        response = self.specific_sched_to_string(specificSched, restaurant, day)

        # If the restaurant is courtyard, it needs a little extra on the string
        # Currently, the schedule does not have meals so it is commented out
        """
        if restaurant == "courtyard":
            response = response + " for " + meal
        """

        handler_input.response_builder.speak(response).set_card(
            SimpleCard(restaurant, self.build_display_text(specificSched)))

        return handler_input.response_builder.response

    # TODO: Comment
    def build_display_text(self, specific_schedule):
        openTime = specific_schedule['start']
        closeTime = specific_schedule['stop']

        return "Hours: " + str(self.time_to_string(self.convert_to_est(
            openTime))) + " - " + str(self.time_to_string(self.convert_to_est(
            closeTime)))

    def get_restaurant_name(self, handler_input):
        # type: (HandlerInput) -> str
        """ This function is passed the HandlerInput then goes and retrieves the user supplied restaurant value
            Then the function passes this restaurant to a function that takes all acceptable inputs and makes one
            standard
        """
        return self.standardize_restaurant_name(
            eval(str(handler_input.request_envelope.request.intent.slots))['restaurant']['value'])

    def get_day_name(self, handler_input):
        # type: (HandlerInput) -> str
        """ This function is passed the HandlerInput then goes and retrieves the user supplied day value """
        return eval(str(handler_input.request_envelope.request.intent.slots))['day']['value']

    def get_meal_name(self, handler_input):
        # type: (HandlerInput) -> str
        """ This function is passed the HandlerInput then goes and retrieves the user supplied meal value """
        return eval(str(handler_input.request_envelope.request.intent.slots))['mealtime']['value']

    # TODO: Remove magic numbers
    def get_schedule(self, restaurant):
        # type: (str) -> str
        """ This function searches the database for the matching restaurant, then, if the schedule is in-date,
        returns it. Otherwise the function updates the schedule and returns the updated version """

        cursor = database.cursor()

        cursor.execute("SELECT * FROM RestaurantHours where restaurant = " + "'" + restaurant + "'")
        data = cursor.fetchall()

        if datetime.datetime.now() - datetime.timedelta(hours=data[0][5]) > \
                datetime.datetime.strptime(str(data[0][4]), "%Y-%m-%d %H:%M:%S"):
            # return the updated schedule
            return self.update_schedule(row)
        # and it is not out of date
        else:
            # return the schedule currently in the database
            return row[1]

    # TODO: Remove magic numbers
    def update_schedule(self, row):
        # type: (list) -> str
        """ This function gets the updated schedule using information stored in the database row, then updates the
        database with the new schedule and new lastUpdated time """

        cursor = database.cursor()

        # We call get_data here with the url and "instructions"
        sched = get_data(row[2], eval(row[3]))

        # We build our SQL commands
        sql = "UPDATE RestaurantHours SET schedule = " + sched + " WHERE name = '" + str(row[0]) + "'"
        sql2 = "UPDATE RestaurantHours SET lastUpdated = '" + str(datetime.datetime.now()) + \
               "' WHERE name = '" + str(row[0]) + "'"

        # Execute and commit the SQL statements
        cursor.execute(sql)
        cursor.execute(sql2)
        database.commit()
        return sched

    def standardize_restaurant_name(self, name):
        # type: (str) -> str
        """ Standardizes the possible restaurant names into one form"""

        # takes whatever restaurant name we receive and matches it to one of the options, returning a string with the
        # "standardized" name
        if name.lower() in ["courtyard", "courtyards", "courtyard food court", "courtyard food courts"]:
            return "courtyard"
        if name.lower() in ["freshens", "freshen", "freshens food studio", "freshens food studios"]:
            return "freshens"
        if name.lower() in ["chickfila", "chick fil as", "chickfilas", "chick fil a"]:
            return "chickfila"
        if name.lower() in ["chilis", "chili", "chili's"]:
            return "chilis"
        if name.lower() in ["einstein", "einstein bros", "einsteins bagels", "einsteins", "einstein bros bagels"]:
            return "einsteins"
        if name.lower() in ["moes", "moes southwestern grills", "moes southwestern grill", "moe", "moes grill", "moe's",
                            "moe's southwestern grills", "moe's southwestern grill", "moe's grill"]:
            return "moes"
        if name.lower() in ["panda", "pandas", "panda express", "panda expresses"]:
            return "panda express"
        if name.lower() in ["papas", "papa johns", "papa johns and sushi with gustos",
                            "papa johns and sushi with gusto", "sushi with gusto"]:
            return "papa johns sushi with gusto"
        if name.lower() in ["starbucksbr", "starbucks at brown", "brown starbucks"]:
            return "starbucks at brown"
        if name.lower() in ["starbuckscy", "starbucks", "starbucks at courtyard", "courtyard starbucks"]:
            return "starbucks at courtyard"
        if name.lower() in ["whichwich", "which wich", "which wich sandwiches", "which wichs", "which wich's"]:
            return "which wich"
        return name.lower()

    def specific_sched_to_string(self, specificSched, restaurant, day):
        # type: (dict, str, str) -> str
        """ Given a specific schedule for a restaurant on a day, returns nicely formatted string
            Used right before returning the specific schedule the user wants
        """
        openTime = specificSched['start']
        closeTime = specificSched['stop']

        # If either openTime or closeTime is missing, this could mean that the restaurant is closed
        if openTime is None or closeTime is None:
            return restaurant + " is closed on " + str(day)
        # Otherwise we convert the start/stop times to EST and make the string
        else:
            return restaurant + " is open from " + self.time_to_string(self.convert_to_est(
                openTime)) + " to " + self.time_to_string(self.convert_to_est(closeTime)) + " on " + str(day)

    def meal_sched_to_string(self, specificSched, meal):
        # type: (dict, str) -> str
        """ A specialized version of the above function used when getting several meal schedules and compiling them
        into one output """
        openTime = specificSched['start']
        closeTime = specificSched['stop']

        # this function is used to compile multiple meal schedules into one day schedule so the string is a little diff
        return meal + " from " + self.time_to_string(self.convert_to_est(
            openTime)) + " to " + self.time_to_string(self.convert_to_est(closeTime))

    # TODO: Remove magic numbers
    def convert_to_est(self, Utcdatetime):
        # type: (str) -> datetime
        """ Given a Utcdatetime in string format, converts it to a local datettime"""
        return datetime.datetime.strptime(Utcdatetime, "%Y-%m-%dT%H:%M:%SZ") - datetime.timedelta(hours=4)

    def time_to_string(self, datetime):
        # type: (datetime) -> str
        hour = datetime.hour
        minute = datetime.minute

        # Start the string off with the 12-hour representation of the hours
        returnString = str(hour % 12) + ":"

        # If minute is 1 digit
        if minute < 10:
            # Pad it with a 0
            returnString = returnString + "0" + str(minute)
        else:
            returnString = returnString + str(minute)

        # If we are in the afternoon
        if hour >= 12:
            # append pm
            returnString = returnString + "pm"
        else:
            # otherwise, append am
            returnString = returnString + "am"

        return returnString

    # TODO: Remove magic numbers (try mass assignment?)
    def getWeekday(self):
        # type () -> str
        """ Gets the current day of the week as a string"""
        weekday = datetime.datetime.today().weekday()
        if weekday == 0:
            return "Monday"
        elif weekday == 1:
            return "Tuesday"
        elif weekday == 2:
            return "Wednesday"
        elif weekday == 3:
            return "Thursday"
        elif weekday == 4:
            return "friday"
        elif weekday == 5:
            return "Saturday"
        elif weekday == 6:
            return "Sunday"


class GetEventsIntentHandler(AbstractRequestHandler):
    """
    Handles the getEvents intent by checking all possible question types and returning valid responses
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """
            checks to see if the user is trying to get an event
        Args:
            handler_input: input from user

        Returns:
            true if the request can be handled, false if not
        """
        return ask_utils.is_intent_name("getEvents")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """
            Handles the request from the user
        Args:
            handler_input: input from user

        Returns:
            response with requested events
        """

        try:

            # Begin progressive response with index at 0
            self.get_progressive_response(handler_input, 0)

            # Get the academic calendar and send the handler input to continue progressive response
            calendar = selenium_parsing.academic_calendar(handler_input)

            day = self.get_week_day(handler_input)

            week = None  # self.get_month_week(handler_input)

            # Get the day passed by the user
            specific_day = self.get_ordinal_day(handler_input, calendar)

            response = "Error Finding Events, please try again."

            # If the day is not null then this type of request has been sent
            if day is not None:
                day_index = self.change_day(day)
                week_index = self.get_this_week(calendar)
                response = "Events for " + day + " are: " + calendar[week_index][day_index].get("Event")

            # If the week is not null then this type of request has been sent
            if week is not None:
                response = self.get_requested_week(week, calendar)

            # If the specific day is not null then this type of request has been sent
            if specific_day is not None:
                response = "Events on " + self.get_month() + " " + specific_day.get(
                    "Day") + " are: " + specific_day.get(
                    "Event")

            # Send the response back to the user
            handler_input.response_builder.speak(response).set_card(SimpleCard(self.get_month() + " " +
                                                                               specific_day.get("Day"),
                                                                               specific_day.get("Event")))


        except Exception as problem:
            response = 'An error has occured when trying to get academic calendar data: ' + str(problem)

        # use the output speech to build a response object and return
        return handler_input.response_builder.response

    def get_progressive_response(self, handler_input, index):
        # type: (HandlerInput, int) -> None
        """
            checks the index passed by the user and builds progressive response based on current position
        Args:
            handler_input: input from user
            index: current position in progressive response
        Returns:
            None
        """
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

    def get_ordinal_day(self, handler_input, calendar_to_search):
        # type: (HandlerInput, list) -> dict | None
        """
            gets the day provided by the user given that they have specified an ordinal day to search
        Args:
            handler_input: input from user
            calendar_to_search: calendar generated in the handler

        Returns:
            dict object with the day requested and event of that day otherwise None
        """
        ordinal_day = eval(str(handler_input.request_envelope.request.intent.slots))['ordinalDay']['value']
        for weeks in calendar_to_search:
            for days in weeks:
                if days.get("Day") == str(ordinal_day):
                    return days
        return None

    def get_week_day(self, handler_input):
        # type: (HandlerInput) -> str
        """
            Returns a day of the week provided by the user.
        Args:
            handler_input: input from the user

        Returns:
            string with the day of the week the user is requesting
        """
        return eval(str(handler_input.request_envelope.request.intent.slots))['day']['value']

    def get_month_week(self, handler_input):
        # type: (HandlerInput) -> int
        """
            Get the week requested and convert the string to an integer.
        Args:
            handler_input: input from the user

        Returns:
            integer of the value given by user
        """
        week_value = eval(str(handler_input.request_envelope.request.intent.slots))['weekIdentifier']['value']
        if week_value == "0":
            return 0
        if week_value == "-1":
            return -1
        if week_value == "1":
            return 1
        else:
            return 0

    def get_this_week(self, calendar_to_search):
        # type: (list) -> int
        """
            Uses the provided calendar to generate an integer representing the index of the current week in the calendar
        Args:
            calendar_to_search: generated calendar which will be used to find the week index

        Returns:
            integer of the index of this week relative to the calendar list
        """
        today = datetime.datetime.today().day
        count = 0
        found_day = False
        for weeks in calendar_to_search:
            for days in weeks:
                if days.get("Day") == str(today):
                    found_day = True
                    break
            if found_day:
                break
            count += 1

        return count

    def get_requested_week(self, week_to_find, calendar_to_search):
        # type: (int, list) -> str
        """
            Uses the calendar and provided week to generate a string response for user input
        Args:
            week_to_find: week to search events from
            calendar_to_search: calendar to look through

        Returns:
            response string to be sent back to the user
        """
        count = self.get_this_week(calendar_to_search)

        return_string = 'Events for this week are: '
        got_events = False
        for week_days in calendar_to_search[count + week_to_find]:
            if week_days.get("Event") != 'No Events':
                got_events = True
                return_string += week_days.get("Event") + " on " + self.get_month() + " " + week_days.get("Day")

        if not got_events:
            return_string += "No Events"

        return return_string

    def change_day(self, day_to_change):
        # type: (str) -> int
        """
            Changes day from string value passed by user to an integer representation.
        Args:
            day_to_change: The day to be changed to an integer

        Returns:
            Integer from 0-7 representing a day of the week
        """
        if day_to_change == "sunday":
            return 0
        elif day_to_change == "monday":
            return 1
        elif day_to_change == "tuesday":
            return 2
        elif day_to_change == "wednesday":
            return 3
        elif day_to_change == "thursday":
            return 4
        elif day_to_change == "friday":
            return 5
        elif day_to_change == "saturday":
            return 6

    def get_month(self) -> str:
        """
            Gets a string value of the current month of the year.
        Returns:
            String with the name of the current month
        """
        month_num = datetime.datetime.today().month
        if month_num == 1:
            return "January"
        elif month_num == 2:
            return "February"
        if month_num == 3:
            return "March"
        if month_num == 4:
            return "April"
        if month_num == 5:
            return "May"
        if month_num == 6:
            return "June"
        if month_num == 7:
            return "July"
        if month_num == 8:
            return "August"
        if month_num == 9:
            return "September"
        if month_num == 10:
            return "October"
        if month_num == 11:
            return "November"
        if month_num == 12:
            return "December"


class ScheduleOfClassesIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """Returns true if this handler can handle the intent"""

        return ask_utils.is_intent_name("scheduleOfClasses")(handler_input)

    def handle(self, handler_input):
        # Gets slot values
        term = self.get_term(handler_input)
        subject = self.get_subject(handler_input)
        courseNum = self.get_course_num(handler_input)
        getSeats = self.get_get_seats(handler_input)

        # Set-up for progressive response. This is just how I implemented it.
        start_time = time.perf_counter()
        timer_length = 8
        max_to_send = 5
        amount_sent = 0

        # Gets both ends of a pipe for inter-process communication
        send_pipe, rcv_pipe = Pipe(duplex=True)

        # Spawn a process to get a list of classes for that subject, including seats
        process = Process(target=sched_of_classes_scraping.get_classes, args=(term, subject, courseNum, getSeats,
                                                                              send_pipe))
        process.start()

        # Here we set loop to True and initialize an empty list of classes
        loop = True
        classes = []

        while loop:
            if time.perf_counter() - start_time > (timer_length * amount_sent) and amount_sent < max_to_send:
                self.get_progressive_response(handler_input, amount_sent)
                amount_sent = amount_sent + 1
            # If a class is ready to be received
            if rcv_pipe.poll(timeout=0):
                # Get it
                cls = rcv_pipe.recv()
                if cls is not None:
                    # Add it to the list
                    classes.append(cls)
                else:
                    # The process is done sending classes
                    loop = False

        process.join()
        # Get the classes out that the user will want to hear and build the speech
        return_classes = self.trim_classes(classes, getSeats)
        outputSpeech = self.build_output_speech(return_classes)

        # Builds the text to display in the Card from the list of returned classes
        output_display_text = self.build_display_text(return_classes)

        # Sets the speech and card for the response
        handler_input.response_builder.speak(outputSpeech).set_card(
            SimpleCard(return_classes[0].subject + " " + str(return_classes[0].courseNum) + " (CRN - Days - Start)",
                       output_display_text))

        # use the output speech to build a response object and return
        return handler_input.response_builder.response

    def build_display_text(self, return_classes):
        return_string = ""
        for cls in return_classes:
            return_string = return_string + cls.crn + " - " + cls.daysOfWeek + " - " + cls.classStart + "\n"
        return return_string

    def trim_classes(self, classes, getSeats):
        newClasses = []
        for cls in classes:
            if getSeats:
                if int(cls.seatsFilled) < int(cls.totalSeats):
                    newClasses.append(cls)
            else:
                newClasses.append(cls)

        return newClasses

    def get_progressive_response(self, handler_input, index):
        request_id = handler_input.request_envelope.request.request_id
        directive_header = Header(request_id=request_id)
        if index == 0:
            speech = SpeakDirective("OK, give me a minute.")
        elif index == 1:
            speech = SpeakDirective("Still working on it.")
        elif index == 2:
            speech = SpeakDirective("Any minute now.")
        elif index == 3:
            speech = SpeakDirective("Almost done!")
        elif index == 4:
            speech = SpeakDirective("Thank you for your patience.")
        else:
            speech = SpeakDirective("Finalizing.")
        directive_request = SendDirectiveRequest(header=directive_header, directive=speech)
        directive_service_client = handler_input.service_client_factory.get_directive_service()
        directive_service_client.enqueue(directive_request)

    def get_requestid(self, handler_input):
        return handler_input.request_envelope.request.request_id

    def get_api_access_token(self, handler_input):
        return handler_input.request_envelope.context.system.api_access_token

    def get_endpoint(self, handler_input):
        return handler_input.request_envelope.context.system.api_endpoint

    def get_specifications(self, handler_input):
        # type: (HandlerInput) -> string
        """"Returns the contents of the Specifications slot"""
        return eval(str(handler_input.request_envelope.request.intent.slots))['Specifications']['values']

    def get_get_seats(self, handler_input):
        # type: (HandlerInput) -> bool
        """"Returns a boolean for get_seats"""
        # here we go ahead and test whether the answer is yes, making the return value a boolean
        return eval(str(handler_input.request_envelope.request.intent.slots))['OpenSeats']['value'] == "yes"

    def get_course_num(self, handler_input):
        # type: (HandlerInput) -> string
        """"Returns the contents of the CourseNumber slot"""
        return eval(str(handler_input.request_envelope.request.intent.slots))['CourseNumber']['value']

    def get_subject(self, handler_input):
        # type: (HandlerInput) -> string
        """"Returns the contents of the Subject slot"""
        return eval(str(handler_input.request_envelope.request.intent.slots))['Subject']['value']

    def get_term(self, handler_input):
        # type: (HandlerInput) -> string
        """"Returns the contents of the Semester slot"""
        return eval(str(handler_input.request_envelope.request.intent.slots))['Semester']['resolutions'] \
            ['resolutions_per_authority'][0]['values'][0]['value']['name']

    def build_output_speech(self, classes):
        # type: (list) -> string
        """"Builds an output speech string for a list of classes"""
        if len(classes) == 0:
            return "No matching classes were found."

        returnString = "The classes I found matching your search are "

        for cls in classes:
            returnString = returnString + str(cls) + ", "

        # chop off the extra comma and space then return
        return returnString[:-2]


class GetDegreeOptionsIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """
            checks to see if the user is trying to get degree options
        Args:
            handler_input: input from user

        Returns:
            true if the request can be handled, false if not
        """
        return ask_utils.is_intent_name("getDegreeOptions")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """
            Handles the request from the user
        Args:
            handler_input: input from user

        Returns:
            response with requested events
        """

        # Gets the connection to the database
        cursor = database.cursor()

        response = ""

        # Getting degree passed from the user
        degree = self.get_degree(handler_input)

        # Getting option passed from the user
        option = self.get_option(handler_input)

        # Determine the type of request given by the user
        if self.check_degree(degree) and self.check_option(option):
            response = self.both_response(degree, option, cursor)
        elif self.check_degree(degree):
            response = self.degree_response(degree, cursor)
        elif self.check_option(option):
            response = self.option_response(option, cursor)
        else:
            response = "No degree or option found for given request"

        handler_input.response_builder.speak(response).set_card(
            SimpleCard(degree + " with " + option, response))

        # use the output speech to build a response object and return
        return handler_input.response_builder.response

    def get_degree(self, handler_input):
        # type: (HandlerInput) -> str
        """
            Gets the string value of the degree the user is requesting
        Args:
            handler_input: input from user
        Returns:
            string of the degree that the user would like to know about
        """
        return eval(str(handler_input.request_envelope.request.intent.slots))['degree']['value']

    def get_option(self, handler_input):
        # type: (HandlerInput) -> str
        """
            Gets the string value of the option the user is requesting and parses to database atribute
        Args:
            handler_input: input from user
        Returns:
            string of the option that the user would like to know about in database atribute form
        """
        string_input = eval(str(handler_input.request_envelope.request.intent.slots))['option']['value']
        response = ""

        if string_input == 'none' or string_input == 'None' or string_input == 'NONE':
            response = 'none'
        if string_input == 'Major' or string_input == 'major':
            response = 'major'
        if string_input == 'Minor' or string_input == 'minor':
            response = 'minor'
        if string_input == 'BS' or string_input == 'bachelor of science':
            response = 'b_s'
        if string_input == 'BA' or string_input == 'bachelor of arts':
            response = 'b_a'
        if string_input == 'BFA' or string_input == 'bachelor of fine arts':
            response = 'b_f_a'
        if string_input == 'BSBA' or string_input == 'bachelor of science in business administration':
            response = 'b_s_b_a'
        if string_input == 'BSED' or string_input == 'bachelor of science in education':
            response = 'b_s_ed'
        if string_input == 'MS' or string_input == 'master of science':
            response = 'm_s'
        if string_input == 'BSEE' or string_input == 'bachelor of science in electrical engineering':
            response = 'b_s_e_e'
        if string_input == 'BSE' or string_input == 'bachelor of science in engineering':
            response = 'b_s_e'
        if string_input == 'BM' or string_input == 'bachelor of music':
            response = 'b_m'
        if string_input == 'Concentration' or string_input == 'concentration':
            response = 'concentration'
        if string_input == 'rn' or string_input == 'registered nurse':
            response = 'r_n_to_b_s_n'
        if string_input == 'BSN' or string_input == 'bachelor of science in nursing':
            response = 'b_s_n'
        if string_input == 'BSW' or string_input == 'bachelor of science in social work':
            response = 'b_s_w'

        return response

    def check_degree(self, degree):
        # type: (str) -> bool
        """
            Determines if a degree is being requested by the user
        Args:
            degree: string that has been obtained from handler_input
        Returns:
            True if a degree is present, False otherwise
        """
        result = True
        if degree == 'none' or degree == 'NONE' or degree == "None":
            result = False

        return result

    def check_option(self, option):
        # type: (str) -> bool
        """
            Determines if an option is being requested by the user
        Args:
            option: string that has been obtained from handler_input
        Returns:
            True if an option is present, False otherwise
        """
        result = True
        if option == 'none' or option == 'NONE' or option == "None":
            result = False

        return result

    def degree_response(self, degree, cursor):
        # type: (str, cursor) -> str
        """
            Builds the response given that the user has passed only a degree
        Args:
            degree: string that has been obtained from handler_input to represent the degree
            cursor: a cursor for accessing the database
        Returns:
            Response to be given to the user based on this request
        """
        full_response = "The options for " + degree + " are"
        sql_query = "SELECT * FROM degree_options WHERE degree = '" + degree + "'"
        cursor.execute(sql_query)
        data = cursor.fetchall()

        options_list = self.make_options(data)

        for degree_option in options_list:
            full_response += ", " + degree_option

        return full_response

    def option_response(self, option, cursor):
        # type: (str, cursor) -> str
        """
            Builds the response given that the user has passed only an option
        Args:
            option: string that has been obtained from handler_input to represent the option
            cursor: a cursor for accessing the database
        Returns:
            Response to be given to the user based on this request
        """
        full_response = "The degrees with " + self.standardize_option(option) + " are "

        sql_query = "SELECT degree FROM degree_options WHERE " + option + " = TRUE"

        cursor.execute(sql_query)

        data = cursor.fetchall()

        for table in data:
            for row in table:
                full_response += ", " + row

        return full_response

    def both_response(self, degree, option, cursor):
        # type: (str, str, cursor) -> str
        """
            Builds the response given that the user has passed both a degree and an option
        Args:
            degree: string that has been obtained from handler_input to represent the degree
            option: string that has been obtained from handler_input to represent the option
            cursor: a cursor for accessing the database
        Returns:
            Response to be given to the user based on this request
        """
        sql_query = "SELECT " + option + " FROM degree_options WHERE degree = '" + degree + "'"

        cursor.execute(sql_query)

        data = cursor.fetchall()

        if data[0][0] == 1:
            response = "A " + self.standardize_option(option) + " is offered for " + degree
        else:
            response = "A " + self.standardize_option(option) + " is not offered for " + degree
        return response

    def make_options(self, data):
        # type: (str) -> list
        """
            Builds the list of available options based on a given resposne from the database
        Args:
            data: a query response provided by the database
        Returns:
            A list of all the options present in the query response
        """
        all_options = []
        if data[0][1] == 1:
            all_options.append("Major")
        if data[0][2] == 1:
            all_options.append("Minor")
        if data[0][3] == 1:
            all_options.append("Bachelor of Science")
        if data[0][4] == 1:
            all_options.append("Bachelor of Art")
        if data[0][5] == 1:
            all_options.append("Bachelor of Fine Art")
        if data[0][6] == 1:
            all_options.append("Bachelor of Science in Business Administration")
        if data[0][7] == 1:
            all_options.append("Bachelor of Science in Education")
        if data[0][8] == 1:
            all_options.append("Master of Science")
        if data[0][9] == 1:
            all_options.append("Bachelor of Science in Ellectrical Engineering")
        if data[0][10] == 1:
            all_options.append("Bachelor of Science in Engineering")
        if data[0][11] == 1:
            all_options.append("Bachelor of Music")
        if data[0][12] == 1:
            all_options.append("Concentration")
        if data[0][13] == 1:
            all_options.append("Registered Nurse to Bachechelor of Science in Nursing")
        if data[0][14] == 1:
            all_options.append("Bachelor of Science in Nursing")
        if data[0][15] == 1:
            all_options.append("Bachelor of Social Work")

        return all_options

    def standardize_option(self, tag):
        # type: (str) -> str
        """
            Converts the provided database atribute version of an option back into the readable version for the user
        Args:
            tag: the given database atribute representing a degree option
        Returns:
            A string version of the degree option that can be added to the response
        """
        if tag == "major":
            standard_option = "Major"
        elif tag == "minor":
            standard_option = "Minor"
        elif tag == "b_s":
            standard_option = "Bachelor of Science"
        elif tag == "b_a":
            standard_option = "Bachelor of Art"
        elif tag == "b_f_a":
            standard_option = "Bachelor of Fine Art"
        elif tag == "b_s_b_a":
            standard_option = "Bachelor of Science in Business Administration"
        elif tag == "b_s_Ed":
            standard_option = "Bachelor of Science in Education"
        elif tag == "m_s":
            standard_option = "Master of Science"
        elif tag == "b_s_e_e":
            standard_option = "Bachelor of Science in Ellectrical Engineering"
        elif tag == "b_s_e":
            standard_option = "Bachelor of Science in Engineering"
        elif tag == "b_m":
            standard_option = "Bachelor of Music"
        elif tag == "concentration":
            standard_option = "Concentration"
        elif tag == "r_n_to_b_s_n":
            standard_option = "Registered Nurse to Bachechelor of Science in Nursing"
        elif tag == "b_s_n":
            standard_option = "Bachelor of Science in Nursing"
        elif tag == "b_s_w":
            standard_option = "Bachelor of Social Work"
        else:
            standard_option = "none"

        return standard_option


class GetFacultyContactInfoIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):  # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("getFacultyContactInfo")(handler_input)

    # TODO: Remove magic numbers
    def handle(self, handler_input):
        # print("in handler")
        start_time = time.perf_counter()
        name = self.get_name(handler_input)
        method = self.get_method(handler_input)
        id = self.get_id(handler_input)

        # print(name)
        # print(method)
        # print(id)

        # Set-up for progressive response. This is just how I implemented it.
        max_to_send = 5
        timer_length = 10
        amount_sent = 0

        # Gets both ends of a pipe for inter-process communication
        send_pipe, rcv_pipe = Pipe(duplex=True)

        # Spawn a process to get a list of classes for that subject, including seats
        process = Process(target=get_faculty_info, args=(name, id, send_pipe))
        process.start()

        loop = True
        info = []

        # print("entering loop")
        while loop:
            if time.perf_counter() - start_time > (timer_length * amount_sent) and amount_sent < max_to_send:
                self.get_progressive_response(handler_input, amount_sent)
                amount_sent = amount_sent + 1
            # If the process has sent back info
            if rcv_pipe.poll(timeout=0):
                # Get it
                # print("Getting info")
                info_bit = rcv_pipe.recv()
                if info_bit is not None:
                    # Add it to the list
                    info.append(info_bit)
                else:
                    # The process is done sending classes
                    loop = False

        # print("out of loop")

        response = ""
        email, phone, office = (info[0], info[1], info[2])

        if method is None:
            response = self.build_response(email, phone, office)
        elif method == "email":
            response = "Their email is: " + email
        elif method == "phone":
            response = "Their phone number is: " + phone
        elif method == "office":
            response = "Their office is: " + office

        # print("Sending response")
        handler_input.response_builder.speak(response).set_card(
            SimpleCard(name, self.build_card_body(email, phone, office)))

        return handler_input.response_builder.response

    # TODO: doc
    def build_card_body(self, email, phone, office):
        return "Email: " + email + "\nPhone: " + phone + "\nOffice: " + office

    # TODO: doc
    def build_response(self, email, phone, office):
        return "Their email is: " + email + ". Their phone number is: " + phone + ". Their office is: " + office

    # TODO: doc
    def get_name(self, handler_input):
        return eval(str(handler_input.request_envelope.request.intent.slots))['name']['resolutions'][
            'resolutions_per_authority'][0]['values'][0]['value']['name']

    # TODO: doc
    def get_id(self, handler_input):
        return eval(str(handler_input.request_envelope.request.intent.slots))['name']['resolutions'][
            'resolutions_per_authority'][0]['values'][0]['value']['id']

    # TODO: doc
    def get_method(self, handler_input):
        return eval(str(handler_input.request_envelope.request.intent.slots))['method']['value']

    # TODO: doc
    # TODO: remove magic numbers, or at least define them somewhere in doc
    def get_progressive_response(self, handler_input, index):
        request_id = handler_input.request_envelope.request.request_id
        directive_header = Header(request_id=request_id)
        if index == 0:
            speech = SpeakDirective("OK, give me a minute.")
        elif index == 1:
            speech = SpeakDirective("Still working on it.")
        elif index == 2:
            speech = SpeakDirective("Any minute now.")
        elif index == 3:
            speech = SpeakDirective("Almost done!")
        elif index == 4:
            speech = SpeakDirective("Thank you for your patience.")
        else:
            speech = SpeakDirective("Finalizing.")
        directive_request = SendDirectiveRequest(header=directive_header, directive=speech)
        directive_service_client = handler_input.service_client_factory.get_directive_service()
        directive_service_client.enqueue(directive_request)


class GetRouteScheduleIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """
            checks to see if the user is trying to get cat-tran schedules
        Args:
            handler_input: input from user

        Returns:
            true if the request can be handled, false if not
        """
        return ask_utils.is_intent_name("getRouteSchedule")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """
            Handles the request from the user
        Args:
            handler_input: input from user

        Returns:
            response with requested events
        """

        # Build proper route name
        route = self.standardize_routes(self.get_route(handler_input))

        # Gets the connection to the database
        cursor = database.cursor()

        # Build response for sending
        response = self.build_response(route, cursor)

        # Create the speak response and Alexa show card
        handler_input.response_builder.speak(response).set_card(
            SimpleCard(route, response))

        # use the output speech to build a response object and return
        return handler_input.response_builder.response

    def get_route(self, handler_input):
        # type: (HandlerInput) -> str
        """
            Gets the route value from the handler input and returns it as a string
        Args:
            handler_input: input from the user
        Returns:
            string representing the route the user wants to know about
        """
        return eval(str(handler_input.request_envelope.request.intent.slots))['route']['value']

    def standardize_routes(self, route):
        # type: (str) -> str
        """
            Converts handler input value of route string into standardized name recognizeable by the database
        Args:
            route: string representing the route as provided by the handler input
        Returns:
            A string representation of the route that can be used to query the database
        """
        route_standard = ""
        if route == "all campus":
            route_standard = "ALL CAMPUS"
        elif route == "all campus express":
            route_standard = "ALL CAMPUS EXPRESS"
        elif route == "commuter express":
            route_standard = "COMMUTER EXPRESS"
        elif route == "HHS commuter express":
            route_standard = "H.H.S. COMMUTER EXPRESS"
        elif route == "HHS express":
            route_standard = "H.H.S. EXPRESS"
        elif route == "late night shuttle":
            route_standard = "LATE NIGHT SHUTTLE"
        elif route == "village express":
            route_standard = "VILLAGE EXPRESS"
        elif route == "weekend shuttle":
            route_standard = "WEEKEND SHUTTLE"
        else:
            route_standard = "No Route Found."
        return route_standard

    def build_response(self, route, cursor):
        # type: (str, cursor) -> str
        """
            Builds the response string that will be returned to the user by searching the database and creating a string
        Args:
            route: the route to be queried
            cursor: a connection to the database that will allow us to query the database
        Returns:
            A string of the requested information in a user friendly format
        """
        formatted_response = "The hours are "

        sql_query = "SELECT start_time, end_time, days FROM cat_tran_schedule WHERE route_name = '" + route + "'"
        cursor.execute(sql_query)
        data = cursor.fetchall()

        # we know from the query that the first value will be start time, second will be end time and third will be days
        formatted_response += str(data[0][0]) + " till " + str(data[0][1]) + " on " + str(data[0][2])

        return formatted_response


class GetRouteInfoIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        """
            checks to see if the user is trying to get cat-tran schedules
        Args:
            handler_input: input from user

        Returns:
            true if the request can be handled, false if not
        """
        return ask_utils.is_intent_name("getRouteInfo")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        """
            Handles the request from the user
        Args:
            handler_input: input from user

        Returns:
            response with requested events
        """

        # Build proper route name
        route = self.standardize_routes(self.get_route(handler_input))

        # Gets the connection to the database
        cursor = database.cursor()

        # Build response for sending
        response = self.build_response(route, cursor)

        # Create the speak response and Alexa show card
        handler_input.response_builder.speak(response).set_card(
            SimpleCard(route, response))

        # use the output speech to build a response object and return
        return handler_input.response_builder.response

    def get_route(self, handler_input):
        # type: (HandlerInput) -> str
        """
            Gets the route value from the handler input and returns it as a string
        Args:
            handler_input: input from the user
        Returns:
            string representing the route the user wants to know about
        """
        return eval(str(handler_input.request_envelope.request.intent.slots))['route']['value']

    def standardize_routes(self, route):
        # type: (str) -> str
        """
            Converts handler input value of route string into standardized name recognizeable by the database
        Args:
            route: string representing the route as provided by the handler input
        Returns:
            A string representation of the route that can be used to query the database
        """
        route_name = ""
        if route == "all campus" or route == "red":
            route_name = "ALL CAMPUS"
        elif route == "all campus express" or route == "purple":
            route_name = "ALL CAMPUS EXPRESS"
        elif route == "commuter express" or route == "blue":
            route_name = "COMMUTER EXPRESS"
        elif route == "HHS commuter express" or route == "orange":
            route_name = "H.H.S. COMMUTER EXPRESS"
        elif route == "HHS express" or route == "yellow":
            route_name = "H.H.S. EXPRESS"
        elif route == "late night shuttle":
            route_name = "LATE NIGHT SHUTTLE"
        elif route == "village express" or route == "green":
            route_name = "VILLAGE EXPRESS"
        elif route == "weekend shuttle":
            route_name = "WEEKEND SHUTTLE"
        else:
            route_name = "No Route Found."
        return route_name

    def build_response(self, route, cursor):
        # type: (str, cursor) -> str
        """
            Builds the response string that will be returned to the user by searching the database and creating a string
        Args:
            route: the route to be queried
            cursor: a connection to the database that will allow us to query the database
        Returns:
            A string of the requested information in a user friendly format
        """
        sql_query = "SELECT route_details from cat_tran_schedule where route_name = '" + route + "'"
        cursor.execute(sql_query)
        data = cursor.fetchall()

        return data[0][0]


"""
class SessionEndedRequestHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.speak("Session Ended").response
"""

# This object will compile all our handlers into one entrypoint
sb = CustomSkillBuilder(api_client=DefaultApiClient())

# Adding our Handlers
sb.add_request_handler(StaticIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(GetRestaurantHoursIntentHandler())
sb.add_request_handler(GetEventsIntentHandler())
sb.add_request_handler(ScheduleOfClassesIntentHandler())
sb.add_request_handler(GetDegreeOptionsIntentHandler())
sb.add_request_handler(GetRouteScheduleIntentHandler())
sb.add_request_handler(GetRouteInfoIntentHandler())
sb.add_request_handler(GetFacultyContactInfoIntentHandler())
# sb.add_request_handler(SessionEndedRequestHandler())

# This handler routes the request to the right handler. Also the entry point of the program
lambda_handler = sb.lambda_handler()
