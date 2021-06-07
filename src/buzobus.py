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

# Constants
APP_NAME = "Buzobus"
APP_DESC = "Periodically fetch bus timming table to alert user with a buzzer when its time to go"

class Buzobus:
    """
    Buzobus is mainly based on the algorithm proposed here:
    https://data.bordeaux-metropole.fr/opendemos/saeiv/passages
    """

    # =============
    # Variables
    # =============

    isAppQuitting = False   # Tell if user want to quit
    config = None           # Store the configuration

    # =============
    # Members
    # =============

    def handler_sigint(self, signum, frame):
        self.isAppQuitting = True

    def __init__(self):
        # Check arguments
        parser = argparse.ArgumentParser(description=APP_DESC)
        args = parser.parse_args()

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

        logging.info("Getting stops")
        logging.debug("Reading {0}".format(url))

        jsonResult = self.get_json_from_url(url)
        self.save_json_to_file("stops.json", jsonResult)

        return jsonResult

    def bdd_get_next_bus_times(self, stopId):
        url = self.config["openData"]["geojsonServer"]
        url += '/process/saeiv_arret_passages?'
        url += 'key=' + self.config["openData"]["apiKey"]
        url += '&datainputs={"arret_id":"' + stopId + '"}'
        url += '&attributes=["libelle","hor_estime","terminus"]'

        logging.info("Getting bus times")
        logging.debug("Reading {0}".format(url))

        jsonResult = self.get_json_from_url(url)
        self.save_json_to_file("busTimes.json", jsonResult)

        return jsonResult

    def extract_bus_stop_id(self, jsonStops):
        busStopIds = []

        # Check
        if not 'features' in jsonStops:
            raise RuntimeError('Bad JSON Stops : Missing "features"')

        # Print count
        stopCount = len(jsonStops['features'])
        logging.info("Found {0} stops".format(stopCount))

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

        if len(busStopIds) == 1:
            logging.info("Found busStopId = {0}".format(busStopIds[0]))
            return busStopIds[0]

        logging.info("Found {0} bus stops:".format(len(busStopIds)))
        for busStopId in busStopIds:
            logging.info("- {0}".format(busStopId))

        raise RuntimeError('"' + self.config["stop"]["name"] + '" not found in JSON, check CONFIG_BUS_STOP')

    def extract_next_bus_times(self, jsonBusTime):
        timeTable = []

        # Check
        if not 'features' in jsonBusTime:
            raise RuntimeError('Bad JSON BusTime : Missing "features"')

        # Print count
        busTimesCount = len(jsonBusTime['features'])
        logging.info("Found {0} bus times".format(busTimesCount))

        # No informations for now
        if (busTimesCount == 0):
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
            logging.info("Here are the possibilities:")
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

                logging.info("- {0} ({1})".format(properties['libelle'], properties['terminus']))

            raise RuntimeError('"' + self.config["bus"]["name"] + ' (' + self.config["bus"]["direction"] + ')" not found in JSON, check CONFIG_BUS_*')

        return timeTable

    def get_datetime_diff_from_now(self, date):
        difference = date - datetime.now()
        return difference.seconds // 60

    def display_time_table(self, timeTable):
        # Got something like "2021-06-04T22:55:58"
        logging.info("Next bus:")

        # Handle case with no info
        if (len(timeTable) == 0):
            logging.info("- Pas d'information")
            return

        for timeStr in timeTable:
            timeObj = datetime.strptime(timeStr, '%Y-%m-%dT%H:%M:%S')
            diffInMin = self.get_datetime_diff_from_now(timeObj)

            if (diffInMin == 0):
                logging.info("- Proche")
            elif (diffInMin >= 60):
                logging.info("- Plus d'une heure")
            else:
                logging.info("- {0:2} min".format(diffInMin))

    def run(self):
        # Read configuration
        self.load_config("config.json")

        # init stop id
        if self.config["stop"]["id"] == "":
            jsonStops = self.bdd_get_stops()
            stopId = self.extract_bus_stop_id(jsonStops)
        else:
            stopId = self.config["stop"]["id"]

        while (not self.isAppQuitting):
            # Sleep
            time.sleep(1)

            # Act
            jsonBusTime = self.bdd_get_next_bus_times(stopId)
            nextTimes = self.extract_next_bus_times(jsonBusTime)
            self.display_time_table(nextTimes)

            # Debug
            self.isAppQuitting = True

        # We are leaving
        logging.warning("Quitting gracefully")


if __name__ == '__main__':
    # Init app
    app = Buzobus()

    # Configure signal handler
    signal.signal(signal.SIGINT, app.handler_sigint);

    # Logging
    logging.basicConfig(format='[%(levelname)s] %(message)s', level=logging.INFO)

    # Main loop
    try:
        app.run()
    except Exception as e:
        logging.error("Exit with errors: " + str(e));









