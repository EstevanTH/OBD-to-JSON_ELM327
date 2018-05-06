### HTTP servers ###
#- What IP address and TCP port do you need to bind each server to?
#- For how many seconds should unrefreshed data remain valid? 0.0 means that data never expire. After the delay, the server returns the HTTP status 504 Gateway Time-out.
httpBindings = [
	{"address": "127.0.0.1", "port": 8327, "cacheExpire": 2.0},
	{"address": "0.0.0.0", "port": 8327, "cacheExpire": 2.0},
]

### Serial port ###
#~ Which serial port to choose?
serialPort = "COM3"
#~ What is the baud rate used by the ELM327 by default?
serialBaudRateInitial = 38400
#~ What baud rate would you like to use instead? It can be the same as serialBaudRateInitial if you need no change.
serialBaudRateDesired = 115200
#~ Should the initialization restart when the desired baud rate could not be set?
serialBaudRateDesiredForce = True
#~ How many seconds to wait while scanning values from the sequence?
serialTimeoutWhileOBD = 2
#~ For debuggers: show everything that is sent to the ELM327?
serialShowSentBytes = False
#~ For debuggers: show everything that is received from the ELM327?
serialShowReceivedBytes = False
#~ What OBD communication bus should be used? 0 is for auto-detection, others are described in the ELM327 manual.
ATSP = b'A7'
#~ Show a message when an incorrect result is received?
obdShowIncorrectResult = False
