### HTTP servers ###
#~ What IP address and TCP port do you need to bind each server to?
#~ For how many seconds should unrefreshed data remain valid? 0.0 means that data never expire. After the delay, the server returns the HTTP status 504 Gateway Time-out.
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
ATSP = b'0'
#~ Show a message when an incorrect result is received?
obdShowIncorrectResult = False
#~ Log to a CSV file every time obd.setCurrentOutputData() is called in the sequence? Enter a filename or None.
obdLogOutputData = None
#from datetime import datetime
#obdLogOutputData = "logs/logObdData "+datetime.now().strftime( "%Y-%m-%d %H-%M-%S" )+".csv"
#~ Compact logging format: CSV logging only fills cells with updated values. The updated column does not have its name displayed in a specific cell.
obdLogOutputDataCompact = False
#~ Which method to read a specific CAN frame identifier? Can be one of:
#-- None (bypass CAN frame readings from the sequence)
#-- "CAF0_CRA_RTR" (for genuine ELM327, not tested: request by ATRTR; interrupt in the event of a looping reading)
#-- "CAF0_CRA_RTR_STOPPED" (for my Icar01 ELM327 V1.5: faster than "CAF0_CRA_RTR" by always interrupting looping reading)
obdCanFrameReq11 = None
obdCanFrameReq29 = None
