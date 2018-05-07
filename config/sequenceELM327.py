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


""" Setup of functions that handle receiving OBD answers ###

Synopses:
	obd.setPidResponseCallback( int pid, function receivedCallback )
	receivedCallback( int pid, bytes   data )
	receivedCallback( int pid, int data )
	obd.getLastResponseData( int pid )
	obd.getCurrentOutputData( bytes key )
	obd.setCurrentOutputData( bytes key, mixed outputData )
"""

# BAROMETRIC PRESSURE
def callback( pid, data ):
	global obd
	# value only used elsewhere (to calculate the boost)
obd.setPidResponseCallback( 0x33, callback )

# ENGINE COOLANT TEMPERATURE
def callback( pid, data ):
	global obd
	obd.setCurrentOutputData( b"coolantTemperature", data-40 ) # °C
obd.setPidResponseCallback( 0x05, callback )

# FUEL LEVEL INPUT
def callback( pid, data ):
	global obd
	obd.setCurrentOutputData( b"fuelLevel", data/255 ) # no unit
obd.setPidResponseCallback( 0x2F, callback )

# DISTANCE TRAVELED WITH MIL ON
def callback( pid, data ):
	global obd
	obd.setCurrentOutputData( b"malfunctionDistance", data ) # km
obd.setPidResponseCallback( 0x21, callback )

# VEHICLE SPEED
def callback( pid, data ):
	global obd
	obd.setCurrentOutputData( b"vehicleSpeed", data ) # km/h
obd.setPidResponseCallback( 0x0D, callback )

# ENGINE RPM
def callback( pid, data ):
	global obd
	obd.setCurrentOutputData( b"engineRPM", data/4 ) # RPM
obd.setPidResponseCallback( 0x0C, callback )

# ACCELERATOR PEDAL POSITION D
def _():
	min = 0x2E # vehicle-dependant
	max = 0xD1 # vehicle-dependant
	coef = 1/( max-min )
	def callback( pid, data ):
		global obd
		obd.setCurrentOutputData( b"throttlePosition", ( data-min )*coef ) # no unit
	obd.setPidResponseCallback( 0x49, callback )
_()

# INTAKE MANIFOLD ABSOLUTE PRESSURE
def callback( pid, pressionAdmi ):
	global obd
	# need both atmospheric pressure and intake manifold pressure to calculate boost
	pressionAtmo = obd.getLastResponseData( 0x33 )
	if pressionAtmo is not None:
		obd.setCurrentOutputData( b"boostPressure", ( pressionAdmi-pressionAtmo )/100 ) # bars
obd.setPidResponseCallback( 0x0B, callback )


""" Setup the sequence of OBD readings ###

Synopses:
	obd.resetSequence()
	obd.addPidToSequence( int pid )
"""

obd.resetSequence()
def addPidListToSequence( subSequence ):
	for pid in subSequence:
		obd.addPidToSequence( pid )
subSequence1 = [0x0D, 0x0C, 0x49, 0x0B] # SPEED / RPM / ACCELERATOR / INTAKE PRESSURE
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x33 ) # BAROMETRIC PRESSURE
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x05 ) # ENGINE COOLANT TEMPERATURE
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x2F ) # FUEL LEVEL INPUT
addPidListToSequence( subSequence1 )
obd.addPidToSequence( 0x21 ) # DISTANCE TRAVELED WITH MIL ON
addPidListToSequence( subSequence1 )
