##########################
# Authors: Nate Welch & David Jennings
# Version: 12/14/2021
# Purpose: Functions for Retrieving the Schedule of Classes for WCU
##########################
import re
from multiprocessing import Pipe, Process

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import Select
from selenium import webdriver

# Elements for First Screen
termSelectorXPath = "//*[@id=\"contentHolder\"]/div[2]/form/table[1]/tbody/tr/td/select"
submitButtonXPath = "//*[@id=\"id____UID0\"]"

# Elements for Second Screen
subjectSelectorXPath = "//*[@id=\"subj_id\"]"
courseNumberXPath = "//*[@id=\"crse_id\"]"
courseTitleXPath = "//*[@id=\"title_id\"]"
classSearchButtonXPath = "//*[@id=\"id____UID0\"]"

# Elements for Third Screen
classesFoundTableXPath = "//*[@id=\"contentHolder\"]/div[2]/table[1]/tbody/tr[]"

# Elements for Fourth Screen
seatCap = "/html/body/div[3]/div[3]/div[2]/div[1]/div[2]/table[1]/tbody/tr[2]/td/table/tbody/tr[2]/td[1]"
currSeats = "/html/body/div[3]/div[3]/div[2]/div[1]/div[2]/table[1]/tbody/tr[2]/td/table/tbody/tr[2]/td[2]"

# Set up our chromedriver with some options needed to run on the backend
options = webdriver.ChromeOptions()
options.binary_location = "/opt/headless-chromium"
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--single-process")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome("/opt/chromedriver", options=options)
#driver = webdriver.Chrome()


def get_classes(term, subject, courseNum, getSeats, send_pipe):
    # type: (string, string, string, bool, list) -> list
    """This method returns two lists. The first is all the classes found, the second are the ones matching the courseNum
       and specifications"""

    # Selects the term
    firstScreen(term)

    # Selects the subject
    secondScreen(subject, courseNum)

    # Scrapes the classes
    thirdScreen(getSeats, send_pipe)

    send_pipe.send(None)


def firstScreen(term):
    # type: (string) -> None
    """This function handles finding the term menu and submitting """

    driver.get("https://ssbprod-wcu.uncecs.edu/pls/WCUPROD/bwckschd.p_disp_dyn_sched")

    # This call here forces any javascript to run
    driver.page_source

    # Select the dropdown menu for selecting the term
    select = Select(driver.find_element_by_xpath(termSelectorXPath))

    # Terms no longer open for registration are appended with (View only)
    altTerm = term + " (View only)"

    try:
        # If the first term throws an exception
        select.select_by_visible_text(term)
    except NoSuchElementException:
        # try the alternate term
        select.select_by_visible_text(altTerm)

    # Click the submit button
    driver.find_element_by_xpath(submitButtonXPath).click()


def secondScreen(subject, course_num):
    # type: (string) -> None
    """This function handles selecting the correct subject and submitting"""
    select = Select(driver.find_element_by_xpath(subjectSelectorXPath))
    select.select_by_visible_text(subject.title())

    subject_textbox = driver.find_element_by_xpath(courseNumberXPath)
    subject_textbox.send_keys(str(course_num))

    driver.find_element_by_xpath(classSearchButtonXPath).click()

def thirdScreen(getSeats, send_pipe):
    # type: (bool) -> None
    """This function scrapes a list of classes and returns a list of Class objects"""

    i = 1
    # We don't have a great way of knowing how many classes there are so I loop until the next element cannot be found
    # by catching the NoSuchElementException then setting the loop variable to outside the bounds
    while i >= 0:
        try:
            # Get the first part of the class
            classXPath = getClassXPath(i)
            classInfo1 = driver.find_element_by_xpath(classXPath).text

            # Go to the next item and this is the second part of the class
            classXPath = getClassXPath(i + 1)
            classInfo2 = driver.find_element_by_xpath(classXPath).text

            # if getSeats is true, go to the fourth screen and get seat info
            if getSeats:
                seats = fourthScreen(i)
                ourClass = Class((classInfo1, classInfo2, seats))
            else:
                ourClass = Class((classInfo1, classInfo2))

            # Append the newly created class to our list
            send_pipe.send(ourClass)

            # Clear ourClass out for next round
            ourClass = None

            # Move two since each class has two parts
            i = i + 2
        except NoSuchElementException:
            # Set the loop variable to outside the bounds because we have run out of classes
            i = -1


def fourthScreen(counter):
    # type: (int) -> list
    """This function clicks on a specific class and returns the seat info for it"""

    # gets the class xpath and click the link
    driver.find_element_by_xpath(getClassXPath(counter) + "/th/a").click()

    # get the seat info
    seat2 = driver.find_element_by_xpath(seatCap).text
    seat1 = driver.find_element_by_xpath(currSeats).text

    # go back to the list of classes
    driver.back()
    return seat1, seat2


def getClassXPath(desiredIndex):
    # type: () -> pymysql.Connection
    """This function returns the XPath of a particular class in the list of classes"""
    tempString = classesFoundTableXPath

    # find the index of the last character
    index = len(tempString) - 1

    # insert the desired class index right before this index
    newString = tempString[0:index] + str(desiredIndex) + tempString[index:len(tempString)]
    return newString


class Class:
    """This class models a Class"""
    name = None
    subject = None
    crn = None
    courseNum = None
    section = None
    term = None
    registrationStart = None
    registrationEnd = None
    level = None
    campus = None
    scheduleType = None
    credits = None
    daysOfWeek = None
    classStart = None
    classEnd = None
    professor = None
    seatsFilled = None
    totalSeats = None

    def make_class_from_dict(self, dict):
        # type: (dict) -> None
        """This method sets a classes fields to the values specified in the dictionary"""
        self.name = dict['name']
        self.subject = dict['subject']
        self.crn = dict['crn']
        self.courseNum = dict['courseNum']
        self.section = dict['section']
        self.term = dict['term']
        self.registrationStart = dict['registrationStart']
        self.registrationEnd = dict['registrationEnd']
        self.level = dict['level']
        self.campus = dict['campus']
        self.scheduleType = dict['scheduleType']
        self.credits = dict['credits']
        self.daysOfWeek = dict['daysOfWeek']
        self.classStart = dict['classStart']
        self.classEnd = dict['classEnd']
        self.professor = dict['professor']
        self.seatsFilled = dict['seatsFilled']
        self.totalSeats = dict['totalSeats']

    def __init__(self, elements):
        # type: (list) -> None
        """This method is a constructor for a new Class. If elements is 'empty' then an empty class is made. Information
           about seats is optional"""
        if elements != "empty":
            self.prepElements1(elements[0])
            self.prepElements2(elements[1])

            # If elements has another item, its the seat info
            if len(elements) == 3:
                self.seatsFilled = elements[2][0]
                self.totalSeats = elements[2][1]

    def prepElements1(self, element):
        # type: (string) -> None
        """This method parses out any information from the first element"""

        # Split the string by dashes with a space on both sides
        items = element.split(" - ")

        # Trim off any extra spaces
        items = self.trimItems(items)

        # The second item should be a CRN of length 5, if it isnt, some classes have extraneous information here
        if len(items[1]) != 5:
            items.remove(items[1])

        self.name = items[0]
        self.crn = items[1]
        self.subject = items[2].split(" ")[0]
        self.courseNum = items[2].split(" ")[1]
        self.section = items[3]

    def prepElements2(self, element):
        # type: (string) -> None
        """This method parses out any information from the second element"""
        items = self.get_items_from_class_description(element)
        self.term = items[0]
        self.registrationStart = items[1][0]
        self.registrationEnd = items[1][1]
        self.level = items[2]
        self.campus = items[3]
        self.scheduleType = items[4]
        self.credits = items[5]
        self.daysOfWeek = items[6]
        self.classStart = items[7]
        self.classEnd = items[8]
        self.professor = items[9]

    def trimItems(self, items):
        # type: (list) -> list
        """This method returns the same list with spaces trimmed off"""
        returnItems = []
        for item in items:
            newItem = item
            if item[0] == ' ':
                newItem = newItem[1:]
            if item[-1] == ' ':
                newItem = newItem[:-1]
            returnItems.append(newItem)
        return returnItems

    def get_items_from_class_description(self, element):
        # type: (string) -> list
        """This method finds a bunch of information about the fields from the element string and returns the values"""
        returnItems = [self.get_term_from_string(element), self.get_registration_dates_from_string(element),
                       self.get_level_from_string(element), self.get_campus_from_string(element),
                       self.get_schedule_type_from_string(element), self.get_credits_from_string(element),
                       self.get_daysofweek_from_string(element), self.get_class_start_from_string(element),
                       self.get_class_end_from_string(element), self.get_professor_from_string(element)]
        return returnItems

    def get_term_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "Associated Term: ([A-Za-z]* [0-9]*)"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)
        if returnString is not None:
            return returnString.group(1)
        else:
            return "TBA"

    def get_registration_dates_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "Registration Dates: ([A-Za-z]* [0-9]*, [0-9]*) to ([A-Za-z]* [0-9]*, [0-9]*)"
        regularExpression = re.compile(regex)
        match = regularExpression.search(element)

        if match is not None:
            return match.group(1), match.group(2)
        else:
            return "No dates available", "No dates available"

    def get_level_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "Levels: ([A-Za-z ]*)"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)
        if returnString is not None:
            return returnString.group(1)
        else:
            return "No level provided."

    def get_campus_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "([A-Za-z]*) Campus"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)
        if returnString is not None:
            return returnString.group(1)
        else:
            return "No campus provided."

    def get_schedule_type_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "([A-Za-z]*) Schedule Type"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)
        if returnString is not None:
            return returnString.group(1)
        else:
            return "No schedule type provided."

    def get_credits_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "([0-9]*.[0-9]*) Credits"
        regularExpression = re.compile(regex)
        return regularExpression.search(element).group(1)

    def get_daysofweek_from_string(self, element):
        # type: (string) -> string
        """This method returns the result of applying a regular expression to the string to find the desired class info
        """
        regex = "Class [0-9]*:[0-9]* .m - [0-9]*:[0-9]* .m ([A-Z]*)"
        regularExpression = re.compile(regex)

        regex2 = "Lab [0-9]*:[0-9]* .m - [0-9]*:[0-9]* .m ([A-Z]*)"
        regularExpression2 = re.compile(regex2)

        returnString = regularExpression.search(element)
        returnString2 = regularExpression2.search(element)

        if returnString is not None:
            return returnString.group(1)
        elif returnString2 is not None:
            return returnString2.group(1)
        else:
            return "TBA"

    def get_class_start_from_string(self, element):
        # type: (string) -> string
        """Applys a regex on class data to get the class start time"""
        regex = "Class ([0-9]*:[0-9]* .m) - [0-9]*:[0-9]* .m [A-Z]*"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)

        regex2 = "Lab ([0-9]*:[0-9]* .m) - [0-9]*:[0-9]* .m [A-Z]*"
        regularExpression2 = re.compile(regex2)
        returnString2 = regularExpression2.search(element)

        if returnString is not None:
            return returnString.group(1)
        elif returnString2 is not None:
            return returnString2.group(1)
        else:
            return "TBA"

    def get_class_end_from_string(self, element):
        # type: (string) -> string
        """Applys a regex on class data to get the class end time"""
        regex = "Class [0-9]*:[0-9]* .m - ([0-9]*:[0-9]* .m) [A-Z]*"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)

        regex2 = "Lab [0-9]*:[0-9]* .m - ([0-9]*:[0-9]* .m) [A-Z]*"
        regularExpression2 = re.compile(regex2)
        returnString2 = regularExpression2.search(element)

        if returnString is not None:
            return returnString.group(1)
        elif returnString2 is not None:
            return returnString2.group(1)
        else:
            return "TBA"

    def get_professor_from_string(self, element):
        # type: (string) -> string
        """Applys a regex on class data to get the professor"""
        regex = "(\\w* \\w*) \\(P\\)"
        regularExpression = re.compile(regex)
        returnString = regularExpression.search(element)

        if returnString is not None:
            return returnString.group(1)
        else:
            return "TBA"

    def toDict(self):
        # type: () -> string
        """Defines the string representation for the class"""
        return str(vars(self))

    def meetsSpecifications(self, specifications):
        # type: (list) -> bool
        """Tests whether this class meets all specifications in the provided list"""
        if specifications is None:
            return True

        for spec in specifications:
            if spec == "300 level or above":
                if int(self.courseNum) < 300:
                    return False
        return True

    def __eq__(self, other):
        # type: (Class) -> bool
        """Returns whether or not two classes are equal by comparing CRNs"""
        if isinstance(other, Class):
            return self.crn == other.crn

    def __str__(self):
        # type: () -> string
        """Returns a string representation for the class"""
        return self.subject + " " + self.courseNum + ". CRN: " + self.crn



def main():
    send_pipe, rcv_pipe = Pipe(duplex=True)

    # Spawn a process to get a list of classes for that subject, including seats
    process = Process(target=get_classes, args=("Spring 2022", "Computer Science", "151", True, send_pipe))
    process.start()

    # Here we set loop to True and initialize an empty list of classes
    loop = True
    classes = []

    while loop:
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

    # Attempt to join the process
    process.join()

    for cls in classes:
        print(cls.__str__())

if __name__ == '__main__':
    main()
