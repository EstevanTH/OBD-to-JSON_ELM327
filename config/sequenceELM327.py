###
# obd.setCurrentOutputData() resets the log file if the key (= column name) has not been seen yet.
###


""" Declaration of the format of PIDs ###
Currently the length argument is not optional. DEFAULT should match the payload length of the OBD answer.

Synopsis:
	obd.setPidResponseLength( int pid, int length=DEFAULT, bool returnByteArray=true )
"""

obd.setPidResponseLength( 0x33, 1, False ) # BAROMETRIC PRESSURE
obd.setPidResponseLength( 0x05, 1, False ) # ENGINE COOLANT TEMPERATURE
obd.setPidResponseLength( 0x2F, 2, False ) # FUEL LEVEL INPUT
obd.setPidResponseLength( 0x21, 2, False ) # DISTANCE TRAVELED WITH MALFUNCTION INDICATOR LAMP ON
obd.setPidResponseLength( 0x0D, 1, False ) # VEHICLE SPEED
obd.setPidResponseLength( 0x0C, 2, False ) # ENGINE RPM
obd.setPidResponseLength( 0x49, 1, False ) # ACCELERATOR PEDAL POSITION D
obd.setPidResponseLength( 0x0B, 1, False ) # INTAKE MANIFOLD ABSOLUTE PRESSURE
obd.setPidResponseLength( 0x2C, 1, False ) # COMMANDED EGR


""" Declaration of CAN identifier requests ###
CanFrameRequest objects can be used in place of OBD PIDs.

Instanciation synopsis:
	req = obd.CanFrameRequest( int identifier, int identifierBits, int minDataBytes, expireTime_s=0.1 )
		minDataBytes: number of data bytes starting from D0 needed for your process:
			1 for D0 only, 3 for D0 to D2, 8 for D0 to D7, etc.
"""

reqBrake = obd.CanFrameRequest( 0x0810a000, 29, 3, expireTime_s=0.1 ) # BRAKE PEDAL POSITION
reqAcceleratorRpmBoost = obd.CanFrameRequest( 0x0618a001, 29, 8, expireTime_s=0.1 ) # ACCELERATOR PEDAL POSITION (EFFECTIVE) + ENGINE RPM + BOOST
reqSpeedAbs = obd.CanFrameRequest( 0x0210a006, 29, 6, expireTime_s=0.1 ) # VEHICLE SPEED + ABS


""" Setup of functions that handle receiving OBD answers / CAN packets ###

Synopses:
	obd.setPidResponseCallback( int pid, function receivedCallback )
	obd.setPidResponseCallback( CanFrameRequest pid, function receivedCallback )
	receivedCallback( int pid, bytes   data )
	receivedCallback( int pid, int data )
	obd.getLastResponseData( int pid )
	obd.getCurrentOutputData( bytes key )
	obd.setCurrentOutputData( bytes key, mixed outputData )
"""

# BAROMETRIC PRESSURE
def callback( pid, data ):
	obd.setCurrentOutputData( b"barometricPressure", data/100. ) # bars
	# value only used elsewhere (to calculate the boost)
obd.setPidResponseCallback( 0x33, callback )

# ENGINE COOLANT TEMPERATURE
def callback( pid, data ):
	obd.setCurrentOutputData( b"coolantTemperature", data-40 ) # °C
obd.setPidResponseCallback( 0x05, callback )

# FUEL LEVEL INPUT
def callback( pid, data ):
	obd.setCurrentOutputData( b"fuelLevel", data/255. ) # no unit
obd.setPidResponseCallback( 0x2F, callback )

# DISTANCE TRAVELED WITH MIL ON
def callback( pid, data ):
	obd.setCurrentOutputData( b"malfunctionDistance", data ) # km
obd.setPidResponseCallback( 0x21, callback )

# VEHICLE SPEED
def callback( pid, data ):
	obd.setCurrentOutputData( b"vehicleSpeed", data ) # km/h
obd.setPidResponseCallback( 0x0D, callback )

# ENGINE RPM
def callback( pid, data ):
	obd.setCurrentOutputData( b"engineRPM", data/4 ) # RPM
obd.setPidResponseCallback( 0x0C, callback )

# ACCELERATOR PEDAL POSITION D
def _():
	min = 0x2E # vehicle-dependant
	max = 0xD1 # vehicle-dependant
	coef = 1/( max-min )
	def callback( pid, data ):
		obd.setCurrentOutputData( b"throttlePosition", ( data-min )*coef ) # no unit
	obd.setPidResponseCallback( 0x49, callback )
_()

# INTAKE MANIFOLD ABSOLUTE PRESSURE
def callback( pid, pressionAdmi ):
	# need both atmospheric pressure and intake manifold pressure to calculate boost
	pressionAtmo = obd.getLastResponseData( 0x33 )
	if pressionAtmo is not None:
		obd.setCurrentOutputData( b"boostPressure", ( pressionAdmi-pressionAtmo )/100. ) # bars
obd.setPidResponseCallback( 0x0B, callback )

# COMMANDED EGR
def callback( pid, data ):
	obd.setCurrentOutputData( b"egrCommanded", data/255. ) # no unit
obd.setPidResponseCallback( 0x2C, callback )

# BRAKE PEDAL POSITION
isAbsActive = False
def callback( identifier, data ):
	""" This vehicle returns only 3 values: 0, 1, 3. On brake release, 2 can be seen. """
	brakePosition = data[2]
	brakePosition &= 0b01100000
	brakePosition >>= 5
	if isAbsActive and brakePosition!=0:
		brakePosition = 1. # 100% when ABS active and pedal pressed
	else:
		brakePosition /= 4. # 75% max when ABS inactive
	obd.setCurrentOutputData( b"brakePosition", brakePosition ) # no unit
obd.setPidResponseCallback( reqBrake, callback )

# ACCELERATOR PEDAL POSITION (EFFECTIVE) + ENGINE RPM + BOOST
def callback( identifier, data ):
	"""
	Accelerator: Values are 0 to 255
	Engine RPM: Value is in RPM
	Boost: Values are in bars
	"""
	throttlePosition = data[7] # D7
	throttlePosition /= 255.
	engineRPM = data[2:4] # D2 to D3
	engineRPM = int.from_bytes( engineRPM, "big" )
	boost = data[1] # D1
	boost -= 16
	boost /= 128.
	boostSmooth = data[4] # D4
	boostSmooth -= 16
	boostSmooth /= 128.
	boostTarget = data[6] # D6
	boostTarget -= 16
	boostTarget /= 128.
	obd.setCurrentOutputData( b"throttlePosition", throttlePosition ) # no unit
	obd.setCurrentOutputData( b"engineRPM", engineRPM ) # RPM
	obd.setCurrentOutputData( b"boostPressure", boost ) # boost
	obd.setCurrentOutputData( b"boostSmooth", boostSmooth ) # boost (smoother)
	obd.setCurrentOutputData( b"boostTarget", boostTarget ) # boost target
obd.setPidResponseCallback( reqAcceleratorRpmBoost, callback )

# VEHICLE SPEED + ABS
def callback( identifier, data ):
	vehicleSpeed = data[4:6] # D4 to D5
	vehicleSpeed = int.from_bytes( vehicleSpeed, "big" )
	vehicleSpeed /= 128.
	absFlag = data[3] # D3
	absFlag &= 0b00010000
	absFlag = ( absFlag!=0 )
	obd.setCurrentOutputData( b"vehicleSpeed", vehicleSpeed ) # km/h
	global isAbsActive; isAbsActive = absFlag
obd.setPidResponseCallback( reqSpeedAbs, callback )


""" Setup the sequence of OBD readings ###

You will have better response times if CAN readings are grouped together.
Avoid adding low-frequency periodic CAN frames as they will slow down the sequence.

Synopses:
	obd.resetSequence()
	obd.addPidToSequence( int pid )
	obd.addPidToSequence( CanFrameRequest req )
"""

obd.resetSequence()
def addPidListToSequence( subSequence ):
	for pid in subSequence:
		obd.addPidToSequence( pid )
# subSequence1 = [0x0B, reqBrake, 0x49, 0x0D, 0x0C, 0x2C] # INTAKE PRESSURE / BRAKE / ACCELERATOR / SPEED / RPM / EGR
# subSequence1 = [0x0B, reqBrake, reqAcceleratorRpmBoost, reqSpeedAbs, 0x2C] # INTAKE PRESSURE / BRAKE / ACCELERATOR + RPM / SPEED + ABS / EGR
subSequence1 = [reqBrake, reqAcceleratorRpmBoost, reqSpeedAbs, 0x2C] # BRAKE / ACCELERATOR + RPM + BOOST / SPEED + ABS / EGR
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x33 ) # BAROMETRIC PRESSURE
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x05 ) # ENGINE COOLANT TEMPERATURE
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x2F ) # FUEL LEVEL INPUT
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x21 ) # DISTANCE TRAVELED WITH MIL ON
addPidListToSequence( subSequence1 )
