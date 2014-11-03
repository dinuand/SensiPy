import flask
from flask import request
from datetime import datetime

app = flask.Flask(__name__)
# app.config['DEBUG'] = True

import os
import struct
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
ACTIVE      = 1
INACTIVE    = 0
B = 3975         # value of the thermistor
notification = ""
notificationIsReceived = 1
sensorValue    = [0, 0, 0, 0, 0, 0]
isActive       = [0, 0, 0, 0, 0, 0]
criticalLevel  = [100, 10, 50, 0, 0, 0]
lowLevel       = [400, 20, 400, 0, 0, 0]
normalLevel    = [600, 25, 750, 0, 0, 0]
clientIsNotifiedOnLowLevel      = [0, 0, 0, 0, 0, 0]
clientIsNotifiedOnCriticalLevel = [0, 0, 0, 0, 0, 0]

lcd = rgb_lcd()
lcd.begin(16, 2)

def colorToRGB (color):
  return struct.unpack ('BBB', color[1:].decode('hex'))

def printOnLcd():
  color = colorToRGB('#ff0000')
  global lcd
  lcd.setRGB(color[0], color[1], color[2] )
  lcd.setCursor(0,0)
  lcd.write(str('Hi! :)'))
  lcd.setCursor(0,1)
  lcd.write(str('I\'m SmartPlant.'))

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
  print "This is Twilio"
  twilio_account = 'ACcddeaecc38d98989c00fd7f86c5c0271'
  twilio_token   = 'e9dbad9c7a9130ddc1e5c0baab3f83d7'
  twilio_client  = TwilioRestClient(twilio_account, twilio_token)
  myMessage = twilio_client.messages.create(to=number, from_='+14063330030', body=message)

#**************************************************************************************************
# Parse string that server receives from client about the active sensorValue
#**************************************************************************************************

def setSensorsState(receivedDataString, state) :
  print "Hello from parser"
  listOfSensors = receivedDataString.split('_')
  global isActive
  for i in xrange(len(listOfSensors) - 1) :
    print listOfSensors[i]
    if listOfSensors[i]   == 'Humidity' :
      isActive[HUMIDITY]    = state
      clientIsNotifiedOnLowLevel[HUMIDITY] = clientIsNotifiedOnCriticalLevel[HUMIDITY] = 0 
    elif listOfSensors[i] == 'Water-Level' :
      isActive[WATER_LEVEL] = state
      clientIsNotifiedOnLowLevel[WATER_LEVEL] = clientIsNotifiedOnCriticalLevel[WATER_LEVEL] = 0
    elif listOfSensors[i] == 'Light' :
      isActive[LIGHT]       = state 
      clientIsNotifiedOnLowLevel[LIGHT] = clientIsNotifiedOnCriticalLevel[LIGHT] = 0
    elif listOfSensors[i] == 'Temperature' :
      isActive[TEMPERATURE] = state
      clientIsNotifiedOnLowLevel[TEMPERATURE] = clientIsNotifiedOnCriticalLevel[TEMPERATURE] = 0
    elif listOfSensors[i] == 'Sound' :
      isActive[SOUND]       = state
      clientIsNotifiedOnLowLevel[SOUND] = clientIsNotifiedOnCriticalLevel[SOUND] = 0
    elif listOfSensors[i] == 'Motion' :
      isActive[MOTION]      = state
      clientIsNotifiedOnLowLevel[MOTION] = clientIsNotifiedOnCriticalLevel[MOTION] = 0

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

# def clientIsNotifiedAtAll():
#   for i in xrange(len(clientIsNotifiedOnLowLevel)):
#     if clientIsNotifiedOnLowLevel[i] == 1 or clientIsNotifiedOnCriticalLevel[i] == 1:
#       return 0
#   return 1

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
  if thereAreActiveSensors == 1 and notificationIsReceived == 1:
    notification = ""
  # check and solve every test-case with low or critically levels
  # check for LIGHT
  if isActive[LIGHT] == 1 :
    if sensorValue[LIGHT] >= criticalLevel[LIGHT] and sensorValue[LIGHT] <= lowLevel[LIGHT] :
      if clientIsNotifiedOnLowLevel[LIGHT] == 0:
        notification += "Light\n"
        clientIsNotifiedOnLowLevel[LIGHT] = 1
        clientIsNotifiedOnCriticalLevel[LIGHT] = 0
    elif sensorValue[LIGHT] < criticalLevel[LIGHT]:
      # notification = ""
      turnOnLight()
      if clientIsNotifiedOnCriticalLevel[LIGHT] == 0:
        notification += "Light-auto adjusted!\n"
        clientIsNotifiedOnCriticalLevel[LIGHT] = 1
        clientIsNotifiedOnLowLevel[LIGHT] = 0
    elif sensorValue[LIGHT] >= normalLevel[LIGHT]:
      turnOffLight()
      clientIsNotifiedOnLowLevel[LIGHT] = 0
      clientIsNotifiedOnCriticalLevel[LIGHT] = 0
  # check for HUMIDITY
  if isActive[HUMIDITY] == 1:
    if sensorValue[HUMIDITY] >= criticalLevel[HUMIDITY] and sensorValue[HUMIDITY] <= lowLevel[HUMIDITY] :
      if clientIsNotifiedOnLowLevel[HUMIDITY] == 0:
        notification += "Humidity\n"
        clientIsNotifiedOnLowLevel[HUMIDITY] = 1
        clientIsNotifiedOnCriticalLevel[HUMIDITY] = 0
    elif sensorValue[HUMIDITY] < criticalLevel[HUMIDITY]:
      turnOnWater()
      if clientIsNotifiedOnCriticalLevel[HUMIDITY] == 0:
        notification += "Humidity-auto adjusted!\n"
        clientIsNotifiedOnCriticalLevel[HUMIDITY] = 1
        clientIsNotifiedOnLowLevel[HUMIDITY] = 0
    elif sensorValue[HUMIDITY] >= normalLevel[HUMIDITY]:
      clientIsNotifiedOnLowLevel[HUMIDITY] = 0
      clientIsNotifiedOnCriticalLevel[HUMIDITY] = 0
  # send the appropriate notification and take care of thread
  if notification == "" and notificationIsReceived == 1:
    notification = "Ignore\n"
  # sendNotification()
  Timer(3, setup).start()

#**************************************************************************************************
# Routes for communicating with the client
#**************************************************************************************************

NOTIFICATION_CENTER = '/sensors/notification/'        # server notificates client 
LIGHT_ACTION = '/sensors/Light/action/'               # route to light sensor [server data]
HUMIDITY_ACTION = '/sensors/Humidity/action/'         # route to hum sensor [server data]
WATER_LEVEL_SPS = '/sensors/flood/'                   #
RESET_SERVER = '/sensors/reset/'                       # reset the server

# SERVER SENDS to the client a list with general available sensorValue on the board
@app.route('/sensors/list')
def sensorsList():
  return "Humidity#Temperature#Light#Sound#Water-Level#Motion#UV#Vibration"

# SERVER RECEIVES the active sensorValue list from client
@app.route('/sensors/activate/<whichSensors>')
def activateSensors(whichSensors):
  setSensorsState(whichSensors, ACTIVE)
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
  dataToBePosted = ""
  numberOfSensors = len(isActive)
  for i in xrange(numberOfSensors - 1) :
    if isActive[i] == 1:
      if i == LIGHT:
        dataToBePosted += '#' + 'Light=' + str(sensorValue[i])
      elif i == HUMIDITY:
        dataToBePosted += '#' + 'Humidity=' + str(sensorValue[i])
      elif i == TEMPERATURE:
        dataToBePosted += '#' + 'Temperature=' + str(sensorValue[i])
      elif i == WATER_LEVEL:
        dataToBePosted += '#' + 'Water-Level=' + str(sensorValue[i])
      elif i == SOUND:
        dataToBePosted += '#' + 'Sound=' + str(sensorValue[i])
      elif i == MOTION:
        dataToBePosted += '#' + 'Motion=' + str(sensorValue[i])
  return dataToBePosted

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
  global notificationIsReceived
  print "The notification: " + notification
  if notification != "Ignore\n":
    notificationIsReceived = 0
  return notification

@app.route(NOTIFICATION_CENTER + '<action>')
def receiveStateAboutNotification(action):
  global notificationIsReceived
  if action == 'received' :
    notificationIsReceived = 1
  return "Thanks for the information about the notification!"

@app.route(RESET_SERVER + '<whichSensors>')
def resetServer(whichSensors):
  global isActive
  global sensorValue
  setSensorsState(whichSensors, INACTIVE)
  return "Server has reset the values from some sensors!"

@app.route('/user/' + '<action>')
def sayHelloToUser(action) :
  userString = ""
  userString = action.split('_')
  print userString[0]
  message = ""
  message = 'Welcome to Smart Plant project, %s! Have a good night' %userString[0]
  # print userString[0]
  print message
  aux = ""
  aux += '+4'
  aux += userString[1]
  print aux
  # userString[1] = aux
  sendMessage(message, aux)
  return "Data reached server. Thanks!"

#**************************************************************************************************
# Run Flask application
#**************************************************************************************************

printOnLcd()
setup()

if __name__ == '__main__':
  app.run(host='0.0.0.0')