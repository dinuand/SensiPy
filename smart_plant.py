import flask
from flask import request
from datetime import datetime

app = flask.Flask(__name__)
# app.config['DEBUG'] = True

import os

import sys
try:
  from twilio.rest import TwilioRestClient
except:
  print("Please open the Shell and run 'social_install' script")
  sys.exit(1)

from math import *
from threading import Timer

try:
  from wyliodrin import *
except:
  from wiringpi2 import *
  wiringPiSetup()


#**************************************************************************************************
# Initialize some parameters
#**************************************************************************************************

if os.getenv ("wyliodrin_board") == "raspberrypi":
  grove = 300
  adcMaxValue = 1023
  grovepiSetup (grove, 4)
else:
  grove = 0
  adcMaxValue = 4095

CURRENT_TIME = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # get the current time
HUMIDITY    = 0  # connect humidity sensor on A0
TEMPERATURE = 1  # connect temperature sensor on A1
LIGHT       = 2  # connect light sensor on A2
SOUND       = 3  # connect sound sensor on A3
WATER_LEVEL = 4  # connect sound sensor on A4
MOTION      = 5  # connect motion sensor on A5
sensorValue = [0, 0, 0, 0, 0, 0]
isActive = [0, 0, 0, 0, 0, 0]
criticalLevel = [100, 10, 50, 0, 0, 0]
lowLevel      = [400, 20, 400, 0, 0, 0]
normalLevel   = [500, 25, 750, 0, 0, 0]
B = 3975   # value of the thermistor
notification = ""

#**************************************************************************************************
# Get data from sensors and check it
#**************************************************************************************************

def getTemperatureInFahrenheit (pin):
  value = analogRead(grove + pin)
  value = (1023 - value) * 10000 / value
  celsius = round(1 / (log(value / 10000.0) / B + 1 / 298.15) - 273.15, 2)
  fahrenheit = celsius * 1.8 + 32
  return fahrenheit
  
def getRemainingTimeToWaterFlood():
  temp_ref          = 25.7   # our temperature reference
  average_ref       = 2      # our estimation for humidity units depreciation per 1 minute
  time_left = (sensorValue[HUMIDITY] - 400) / ((average_ref * sensorValue[TEMPERATURE]) / temp_ref)
  if time_left // 1 <= 0:
    return -1
  time_left = '%.0f' % time_left
  return time_left

def getDataFromSensors() :
  thereAreActiveSensors = 0
  global sensorValue
  if isActive[LIGHT] == 1 :
    sensorValue[LIGHT] = analogRead(grove + LIGHT);
    thereAreActiveSensors = 1
  if isActive[TEMPERATURE] == 1 :
    sensorValue[TEMPERATURE] = (getTemperatureInFahrenheit(TEMPERATURE) - 32) / 1.8 
    thereAreActiveSensors = 1
  if isActive[HUMIDITY] == 1 :
    sensorValue[HUMIDITY] = analogRead(grove + HUMIDITY)
    thereAreActiveSensors = 1
  if isActive[TEMPERATURE] == 1 and isActive[HUMIDITY] == 1:
    sensorValue[WATER_LEVEL] = getRemainingTimeToWaterFlood()
  return thereAreActiveSensors

#**************************************************************************************************
# Send message to phone with what's happenning 
#**************************************************************************************************

def sendMessage(message, number):
  twilioAccount = 'AC5dfbe9ffc9bdeb8233a915b9aca401af'
  twilioToken   = 'e2eda003091975e928854e4417ca9612'
  twilioClient  = TwilioRestClient(twilioAccount, twilioToken)
  message = twilio_client.messages.create(to=number, from_='+19065239921', body=message)

#**************************************************************************************************
# Parse string that server receives from client about the active sensorValue
#**************************************************************************************************

def parseString(receivedDataString) :
  print "Hello from parser"
  listOfSensors = receivedDataString.split('_')
  global isActive
  for i in xrange(len(listOfSensors) - 1) :
    print listOfSensors[i]
    if listOfSensors[i]   == 'Humidity' :
      isActive[HUMIDITY]    = 1 
    elif listOfSensors[i] == 'Water-Level' :
      isActive[WATER_LEVEL] = 1
    elif listOfSensors[i] == 'Light' :
      isActive[LIGHT]       = 1 
    elif listOfSensors[i] == 'Temperature' :
      isActive[TEMPERATURE] = 1
    elif listOfSensors[i] == 'Sound' :
      isActive[SOUND]       = 1
    elif listOfSensors[i] == 'Motion' :
      isActive[MOTION]      = 1

#**************************************************************************************************
# Calculations & actions
#**************************************************************************************************

def turnOnLight():
  pinMode(4, 1)
  digitalWrite(grove + 4, 1)

def turnOffLight():
  pinMode(4, 1)
  digitalWrite(grove + 4, 0)

def turnOnWater():
  pinMode(5, 1);
  digitalWrite(grove + 8, 1);
  delay(4 * 1000);
  digitalWrite(grove + 8, 0);

def setup() :
  print "Hello from setup"
  # calculate each sensor's value
  thereAreActiveSensors = getDataFromSensors()
  # print some stuff for debugging
  if isActive[LIGHT] == 1:
    print "Light: " + str(sensorValue[LIGHT])
  if isActive[HUMIDITY] == 1:
    print "Humidity: " + str(sensorValue[HUMIDITY])
  if isActive[TEMPERATURE] == 1:
    print "Temperature: " + str(sensorValue[TEMPERATURE])

  global notification
  if thereAreActiveSensors == 1:
    notification = ""
  else: 
    notification = "Ignore\n"
  # check and solve every test-case with low or critically levels
  # check for LIGHT
  if isActive[LIGHT] == 1 :
    if sensorValue[LIGHT] >= criticalLevel[LIGHT] and sensorValue[LIGHT] <= lowLevel[LIGHT] :
      notification += "Light\n"
    elif sensorValue[LIGHT] < criticalLevel[LIGHT]:
      notification = ""
      turnOnLight()
      notification += "Light-auto adjusted!\n"
    elif sensorValue[LIGHT] > normalLevel[LIGHT]:
      turnOffLight()
  # check for HUMIDITY
  if isActive[HUMIDITY] == 1:
    if sensorValue[HUMIDITY] >= criticalLevel[HUMIDITY] and sensorValue[HUMIDITY] <= lowLevel[HUMIDITY] :
      notification += "Humidity\n"
    elif sensorValue[HUMIDITY] < criticalLevel[HUMIDITY]:
      turnOnWater()
      notification += "Humidity-auto adjusted!\n"
  # send the appropriate notification and take care of thread
  sendNotification()
  Timer(5, setup).start()

#**************************************************************************************************
# Routes for communicating with the client
#**************************************************************************************************

NOTIFICATION_CENTER = '/sensors/notification/'              # server notificates client 
LIGHT_ACTION = '/sensors/Light/action/'                     # route to light sensor [server data]
HUMIDITY_ACTION = '/sensors/Humidity/action/'               # route to hum sensor [server data]
WATER_LEVEL_SPS = '/sensors/flood/'

# SERVER SENDS to the client a list with general available sensorValue on the board
@app.route('/sensors/list')
def sensorsList():
  return "Humidity#Temperature#Light#Sound#Water-Level#Motion#UV#Vibration"

# SERVER RECEIVES the active sensorValue list from client
@app.route('/sensors/activate/<data_from_client>')
def activateSensors(data_from_client):
  parseString(data_from_client)
  return "Data reached server. Thanks"

# SERVER SENDS some data to the client about the time before water flood
@app.route(WATER_LEVEL_SPS)
def send_response_for_flood_time():
  time_left = getRemainingTimeToWaterFlood()
  if time_left < 0 :
    return 0
  return time_left

# SERVER SENDS data to client about all active sensorValue
@app.route('/sensors/update/')
def sendUpdatesAboutSensors() :
  data_out = ""
  numberOfSensors = len(isActive)
  for i in xrange(numberOfSensors - 1) :
    if isActive[i] == 1 :
      data_out += '#' + str(sensorValue[i])
  return data_out

# SERVER RECEIVES some info from client about the humidity sensor
@app.route(HUMIDITY_ACTION + '<action>')
def getResponseForHumiditySensor(action):
  if action == 'yes' :
    turnOnWater()
  return "Data reached server. Thanks!"

# SERVER RECEIVES some info from client about the light sensor
@app.route(LIGHT_ACTION + '<action>')
def getResponseForLightSensor(action):
  if action == 'yes' :
    turnOnLight()
  return "Data reached server. Thanks!"

# SERVER SENDS notifications to the client
@app.route(NOTIFICATION_CENTER)
def sendNotification():
  print "The notification: " + notification
  return notification

@app.route('/user/<data_from_client>')
def user_credentials(data_from_client) :
  userString = data_from_client.split('#')
  message = 'Welcome to our service, %s! Senso Check team wish you a happy holiday!' %userString[0]
  aux = ""
  aux += '+4'
  aux += userString[1]
  userString[1] = aux
  sendMessage(message, userString[1])
  return "Data reached server. Thanks!"

#**************************************************************************************************
# Run Flask application
#**************************************************************************************************

setup()

if __name__ == '__main__':
  app.run(host='0.0.0.0')