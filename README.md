# Alexa Skill for WCU

Authors: Nathaniel Welch and David Jennings

Version: 05/24/22

Description: This project acts as a back-end for an Alexa Device to contact with events. There are
several types of questions that the skill can answer, and for the most part, each type has its own handler.
The handlers employ a variety of tools such as webscraping, a database, and other processing to return an
adequate answer to the user.

Known Bugs: Due to the nature of webscraping from public sites for much of the information, many aspects of the
handlers may have become outdated and no longer work due to updates to the sites.

Usage: This is a diffcult product to test, especially now that we are no longer hosting any of its parts on AWS.
Where applicable, some of the webscraping utilites have their own tester code inside a seperate file's main method.
Again this is not garunteed to still work if the sites have been updates.