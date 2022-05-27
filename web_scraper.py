##########################
# Authors: Nate Welch & David Jennings
# Version: 12/14/2021
# Purpose: Uses BS4 to scrape data from the web
##########################
import time
from multiprocessing import Pipe, Process

import selenium.common.exceptions
from bs4 import BeautifulSoup
import urllib.request
import html5lib
import re
import requests
from selenium import webdriver

lib = "html5lib"


def main():
    send_pipe, rcv_pipe = Pipe(duplex=True)
    name = "susan abram"
    id = 2

    # Spawn a process to get a list of classes for that subject, including seats
    process = Process(target=get_faculty_info, args=(name, id, send_pipe))
    process.start()

    loop = True

    while loop:
        # If the process has sent back info
        if rcv_pipe.poll(timeout=0):
            # Get it
            info_bit = rcv_pipe.recv()
            if info_bit is not None:
                # Add it to the list
                print(info_bit)
            else:
                # The process is done sending classes
                loop = False
    """
    driver = webdriver.Chrome()

    faculty_url = "https://www.wcu.edu/faculty/"

    driver.get(faculty_url)

    i = 1
    loop = True

    try:
        while loop:
            xpath = "/html/body/div/div/div[1]/div[3]/div[3]/div[" + str(i) + "]/a/div[2]/p[1]"
            name = driver.find_element_by_xpath(xpath).text.lower()
            print(name + "," + str(i) + "," + name.split(" ")[-1])
            i = i + 1

    except selenium.common.exceptions.NoSuchElementException:
        loop = False
    """


def get_faculty_info(name, id, send_pipe):
    # print("in scraper")
    options = webdriver.ChromeOptions()
    options.binary_location = "/opt/headless-chromium"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--single-process")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome("/opt/chromedriver", options=options)
    # print("driver setup")

    # driver = webdriver.Chrome()

    faculty_url = "https://www.wcu.edu/faculty/"

    # try:
    driver.get(faculty_url)
    # except Exception:
        # print("couldnt load url")

    # print("gotten site")

    correct_faculty_xpath = "/html/body/div/div/div[1]/div[3]/div[3]/div[" + str(id) + "]/a"

    name_xpath = "/html/body/div/div/div[1]/div[3]/div[3]/div[" + str(id) + "]/a/div[2]/p[1]"

    if name not in driver.find_element_by_xpath(name_xpath).text.lower():
        print("id error")
        return "Skill needs updating"


    # print("clicking link")
    driver.find_element_by_xpath(correct_faculty_xpath).click()

    # print("loading page")

    time.sleep(1)

    page_source = driver.page_source

    # print(page_source)

    # print("getting info")
    (email, phone, office) = get_professor_info_from_source(page_source)

    for item in (email, phone, office):
        # print("sending")
        send_pipe.send(item)

    # print("done")
    send_pipe.send(None)


def get_professor_info_from_source(page_source):
    return get_email(page_source), get_phone(page_source), get_office(page_source)


def get_email(page_source):
    regex = "Email: <a .*>(.*)<\/a><"
    regularExpression = re.compile(regex)
    returnString = regularExpression.search(page_source)
    if returnString is not None:
        return returnString.group(1)
    else:
        return "No email provided"


def get_phone(page_source):
    regex = "Phone: (\d+\.\d+\.\d+)<br>"
    regularExpression = re.compile(regex)

    regex2 = "tel:(\d+\.\d+\.\d+)"
    regularExpression2 = re.compile(regex2)

    returnString = regularExpression.search(page_source)
    returnString2 = regularExpression2.search(page_source)

    if returnString is not None:
        return returnString.group(1)
    elif returnString2 is not None:
        return returnString2.group(1)
    else:
        return "No phone number provided"


def get_office(page_source):
    regex = "Office: (.*)\n"
    regularExpression = re.compile(regex)
    returnString = regularExpression.search(page_source)
    if returnString is not None:
        return returnString.group(1).replace("&nbsp;", " ")
    else:
        return "No office provided"

if __name__ == '__main__':
    main()


def get_data(url, instructions):
    # type: (string, tuple) -> string
    """Goes to the url and tries to find the schedule information using the instructions"""
    response = urllib.request.urlopen(url)
    soup = BeautifulSoup(response.read(), lib)

    i = 0
    # for each element matching the element in the instructions (scripts in our case)
    for script in soup.findAll(instructions["element"]):
        # if the length of the list of matches of our regex from the instructions is greater than 0, we want to save
        # the current index
        if len(re.findall(instructions["regex"], str(script))) > 0:
            index = i
        i = i + 1

    i = 0
    # going through these scripts again
    for script in soup.findAll(instructions["element"]):
        # when we find the one we saved
        if i == index:
            # this is the sone we want, save the first match from the regular expression
            schedule = re.findall(instructions["regex"], str(script))[0]
            # cut off the ends because they have extra symbols
            schedule = schedule[2:len(schedule) - 2]
            # return the schedule in single quotes
            return str("'" + schedule + "'")
        i = i + 1


def get_undergrad_programs():
    """
    A method to get all of the majors in the WCU undergrad program in a nicely formatted 2d list.
    Each element in the list represents a program along with degree options, i.e. Major, Minor, B.S., B.A.
    :return: list of programs provided by WCU
    """
    url = 'https://www.wcu.edu/learn/programs/index.aspx'
    website = requests.get(url)
    soup = BeautifulSoup(website.text, 'lxml')
    majors = soup.find('div', class_='promo p-list programs')  # this div class contains a list of all offered majors
    majors_list = majors.find_all('a')  # this will create a python list from the text we got above

    formatted_majors = []
    # this loop is how we get the text from the website which is not formatted "AccountingMajorMinorB.S.B.A."
    # and separates all the keywords so that it can be split into an array containing each piece of data
    for major in majors_list:
        formatted_majors.append(major.text.replace('Major', ' Major')
                                .replace('Minor', ' Minor')
                                .replace('B.S.', ' B.S.')
                                .replace('B.A.', ' B.A.')
                                .replace('B.F.A.', ' B.F.A.')
                                .replace('B.S.Ed.', ' B.S.Ed.')
                                .replace('M.S.', ' M.S.')
                                .replace('B.S.E.E.', ' B.S.E.E.')
                                .replace('B.S.E.', ' B.S.E.')
                                .replace('B.M.', ' B.M.')
                                .replace('B.S.N.', ' B.S.N.')
                                .replace('Concentration', ' Concentration')
                                .replace('Post-Baccalaureate Certificate', ' Post-Baccalaureate Certificate').split()
                                )

    majors_with_options = []  # this will be the final list, it is important to  create a new variable for re-formatting
    count = 0  # counter lets us keep track of where in the list we are

    # This loop will take all of the words which have been split into different strings in a list and merge the titles
    #   of departments and keep the options for degrees separate
    for degree in formatted_majors:
        degree_string = ''
        options = []
        for word in degree:
            if word == 'Major':
                options.append(word)
            elif word == 'Minor':
                options.append(word)
            elif word == 'B.S.':
                options.append(word)
            elif word == 'B.A.':
                options.append(word)
            elif word == 'B.F.A.':
                options.append(word)
            elif word == 'B.S.Ed.':
                options.append(word)
            elif word == 'B.S.E.E.':
                options.append(word)
            elif word == 'B.S.E.':
                options.append(word)
            elif word == 'B.M.':
                options.append(word)
            elif word == 'B.S.N.':
                options.append(word)
            elif word == 'Post-Baccalaureate':
                options.append(word)
            elif word == 'Certificate':
                options.append(word)
            elif word == 'M.S.':
                options.append(word)
            elif word == 'B.S.W.':
                options.append(word)
            elif word == 'Concentration':
                options.append(word)
            elif word == 'B.S.N.R.N.':
                options.append(word)
            elif word == 'to':
                options.append("R.N.")
            elif word == 'B.S.B.A':
                options.append(word)
            else:
                degree_string += word + ' '

        degree_string_list = list(degree_string)
        degree_string_list.pop()
        degree_string = "".join(degree_string_list)

        majors_with_options.append(options)
        majors_with_options[count].insert(0, degree_string)
        count += 1

    return majors_with_options
