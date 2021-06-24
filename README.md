# BuzoBus

A Python Script to get the next bus time and do something about it

# How to

1. Request a key from OpenDataBordeaux using [this link ](https://data.bordeaux-metropole.fr/opendata/key)
2. Go into source folder with `cd src`
3. Install the app requirements with `pip install -r requirements.txt`
4. Use `config.template.json` as a template to create your config and rename it `config.json`
5. Paste your key into `config.json` (`/openData/apiKey`)
6. Clear the value of `/stop/name`, `/stop/id`, `/bus/name` and `/bus/direction`
7. Launch the app with `python buzobus.py`
8. Look for your bus stop name into the newly created `stops_list.json` by using `Super+F`
	- The name to get is `features[]/properties/libelle`
9. Put this name into your config under `/stop/name`
10. Launch again the app
11. Choose the correct stop id into the list displayed by the app
	- This step is kind of tricky when you have multiple choice. 
	- The app will be improved in near future to assist user
12. Put this stopid into your config under `/stop/id`
13. Launch again the app
14. Choose one of the bus line and put its name and direction under `/bus/name` and `/bus/direction`
15. Configure the walk time (`/user/walkTimeMin`) in minutes to get to the bus stop and add an extra 2 min.
16. Launch again to get the next buses
17. Notifications will be sent if its time to go

# Usage

Use `python buzobus.py -h` and read.
