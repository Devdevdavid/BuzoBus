#!/usr/bin/python
# Author  : David DEVANT
# Desc    : See APP_DESC :)
# File    : buzobus.py
# Date    : June 4th, 2021
# Version : 0.1

import time
import argparse
import signal, os
import json
import urllib.request
import logging
from datetime import datetime
from notifypy import Notify

# Constants
APP_NAME = "Buzobus"
APP_DESC = "Periodically fetch bus timming table to alert user with a buzzer or notification when its time to go"

def send_notification(title, message):
    notification = Notify(
      default_notification_title=title,
      default_application_name=APP_NAME,
      default_notification_icon="tbm.png",
    )
    notification.message = message
    notification.send(block=False)


class Buzobus:
    """
    Buzobus is mainly based on the algorithm proposed here:
    https://data.bordeaux-metropole.fr/opendemos/saeiv/passages
    """

    # =============
    # Variables
    # =============

    config = None           # Store the configuration

    # =============
    # Members
    # =============

    def handler_sigint(self, signum, frame):
        self.isAppQuitting = True

    def __init__(self, logger):
        # Init
        self.isAppQuitting = False
        self.logger = logger

        # Check arguments
        parser = argparse.ArgumentParser(description=APP_DESC)
        parser.add_argument('-v', '--verbose', help='enable verbose logs', default=False, action='store_true')
        parser.add_argument('-a', '--always_notif', help='always send notifications', default=False, action='store_true')
        parser.add_argument('-n', '--no_notif', help='prevent notifications', default=False, action='store_true')
        parser.add_argument('-c', '--config', default='config.json', dest="configFile", help='specify json config file', type=str)
        # Use vars() to get python dict from Namespace object
        self.args = vars(parser.parse_args())

        # Handle args
        if self.args["verbose"]:
            self.logger.setLevel(logging.DEBUG)

    def get_json_from_url(self, url):
        openUrl = urllib.request.urlopen(url)

        # Check code
        if (openUrl.getcode() != 200):
            raise RuntimeError('URL not found (Error ' + operUrl.getcode() + ') ' + url)

        # Read file
        data = openUrl.read()

        # Parse as json
        return json.loads(data)

    def save_json_to_file(self, filename, jsonData):
        with open(filename, "w") as outfile:
            json.dump(jsonData, outfile, indent=4)

    def load_config(self, filename):
        with open(filename, "r") as file:
            data = file.read()
            self.config = json.loads(data)

    def bdd_get_stops(self):
        url = self.config["openData"]["geojsonServer"]
        url += '/features/SV_ARRET_P?'
        url += 'key=' + self.config["openData"]["apiKey"]
        url += '&attributes=["IDENT","LIBELLE"]'

        self.logger.info("Getting stops")
        self.logger.debug("Reading {0}".format(url))

        jsonResult = self.get_json_from_url(url)
        self.save_json_to_file("stops_list.json", jsonResult)

        return jsonResult

    def bdd_get_next_bus_times(self, stopId):
        url = self.config["openData"]["geojsonServer"]
        url += '/process/saeiv_arret_passages?'
        url += 'key=' + self.config["openData"]["apiKey"]
        url += '&datainputs={"arret_id":"' + stopId + '"}'
        url += '&attributes=["libelle","hor_estime","terminus"]'

        self.logger.info("Getting bus times")
        self.logger.debug("Reading {0}".format(url))

        jsonResult = self.get_json_from_url(url)
        if self.args["verbose"]:
            self.save_json_to_file("bus_times.json", jsonResult)

        return jsonResult

    def extract_bus_stop_id(self, jsonStops):
        busStopIds = []

        # Check
        if not 'features' in jsonStops:
            raise RuntimeError('Bad JSON Stops : Missing "features"')

        # Print count
        stopCount = len(jsonStops['features'])
        self.logger.info("Found {0} stops".format(stopCount))

        for feature in jsonStops['features']:
            # Ignore features without the expected data
            if not 'properties' in feature:
                continue

            properties = feature['properties']

            # Ignore features without the expected data
            if not 'libelle' in properties:
                continue
            if not 'ident' in properties:
                continue

            if not properties['libelle'] == self.config["stop"]["name"]:
                continue

            busStopIds.append(properties['ident'])

        # Only one found, great !
        if len(busStopIds) == 1:
            self.logger.info("Found busStopId = {0}".format(busStopIds[0]))
            return busStopIds[0]

        # Nothing found
        if len(busStopIds) == 0:
            raise RuntimeError('"' + self.config["stop"]["name"] + '" not found in JSON, check your config /stop/name')

        # More than one found, user need to choose
        self.logger.info("Found {0} bus stops:".format(len(busStopIds)))
        for busStopId in busStopIds:
            self.logger.info("- {0}".format(busStopId))

        raise RuntimeError('Choose one of those StopId and put in into yout config under /stop/id')

    def extract_next_bus_times(self, jsonBusTime):
        timeTable = []

        # Check
        if not 'features' in jsonBusTime:
            raise RuntimeError('Bad JSON BusTime : Missing "features"')

        # Print count
        busTimesCount = len(jsonBusTime['features'])

        # No informations for now
        if (busTimesCount == 0):
            self.logger.info("Found {0} bus times".format(busTimesCount))
            return timeTable

        for feature in jsonBusTime['features']:
            # Ignore features without the expected data
            if not 'properties' in feature:
                continue

            properties = feature['properties']

            # Ignore features without the expected data
            if not 'libelle' in properties:
                continue
            if not 'terminus' in properties:
                continue
            if not 'hor_estime' in properties:
                continue

            if not properties['libelle'] == self.config["bus"]["name"]:
                continue

            if not properties['terminus'] == self.config["bus"]["direction"]:
                continue

            timeTable.append(properties['hor_estime'])

        if len(timeTable) == 0:
            self.logger.info("Here are the possibilities:")
            for feature in jsonBusTime['features']:
                # Ignore features without the expected data
                if not 'properties' in feature:
                    continue

                properties = feature['properties']

                # Ignore features without the expected data
                if not 'libelle' in properties:
                    continue
                if not 'terminus' in properties:
                    continue

                self.logger.info("- Name: {0}, Direction: {1}".format(properties['libelle'], properties['terminus']))

            if (self.config["bus"]["name"] == "") or (self.config["bus"]["direction"] == ""):
                raise RuntimeError('Choose a bus name and direction and put it into your config under /bus/name and /bus/direction')
            else:
                raise RuntimeError('"' + self.config["bus"]["name"] + ' (' + self.config["bus"]["direction"] + ')" not found in JSON, check config /bus/*')

        return timeTable

    def get_datetime_diff_from_now(self, date):
        difference = date - datetime.now()
        return difference.seconds // 60

    def get_remaining_time_table(self, timeTable):
        # Got something like "2021-06-04T22:55:58"
        remTimeTable = []

        for timeStr in timeTable:
            if timeStr != None:
                timeObj = datetime.strptime(timeStr, '%Y-%m-%dT%H:%M:%S')
                diffInMin = self.get_datetime_diff_from_now(timeObj)
            else:
                diffInMin = 0;
            remTimeTable.append(diffInMin)

        return remTimeTable

    def get_text_time_table(self, remTimeTable):
        textTimeTable = []

        for remTimeStr in remTimeTable:
            if (remTimeStr == 0):
                textTimeTable.append("Proche")
            elif (remTimeStr >= 60):
                textTimeTable.append("Plus d'une heure")
            else:
                textTimeTable.append("{0:2} min".format(remTimeStr))

        return textTimeTable

    def display_time_table(self, textTimeTable):
        self.logger.info("Next bus:")

        # Handle case with no info
        if (len(textTimeTable) == 0):
            self.logger.info("- Pas d'information")
            return

        for textTimeStr in textTimeTable:
            self.logger.info("- " + textTimeStr)

    def notify_user(self, textTime):
        title = "{0} ({1}) - Arrêt {2}".format(
            self.config["bus"]["name"],
            self.config["bus"]["direction"],
            self.config["stop"]["name"]
        )
        message = "Prochain bus: {0}".format(textTime)
        send_notification(title, message)

    def run(self):
        # Read configuration
        self.load_config("config.json")

        # init stop id
        if self.config["stop"]["id"] == "":
            jsonStops = self.bdd_get_stops()
            stopId = self.extract_bus_stop_id(jsonStops)
        else:
            stopId = self.config["stop"]["id"]

        # Act
        jsonBusTime = self.bdd_get_next_bus_times(stopId)
        nextTimes = self.extract_next_bus_times(jsonBusTime)
        remTimeTable = self.get_remaining_time_table(nextTimes)
        textTimeTable = self.get_text_time_table(remTimeTable)
        self.display_time_table(textTimeTable)

        # Do nothing if there is no informations
        if (len(remTimeTable) == 0):
            return

        # Check if user wants notification or not
        if self.args["no_notif"]:
            return;

        # Do range check if we don't want to always send notification
        if self.args["always_notif"] == False:
            threshold = self.config["user"]["walkTimeMin"]
            isInsideRange = (remTimeTable[0] >= threshold) and (remTimeTable[0] < threshold + 5)

            # Either too late or too soon, do nothing more
            if not isInsideRange:
                return;

        # Send notification to user with the next incomming bus
        self.notify_user(textTimeTable[0])

if __name__ == '__main__':
    # Logging
    logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)
    logger = logging.getLogger(APP_NAME)

    # Init app
    app = Buzobus(logger)

    # Configure signal handler
    signal.signal(signal.SIGINT, app.handler_sigint);

    # Main loop
    try:
        app.run()
    except Exception as e:
        logger.error("Exit with errors: " + str(e));









