###
# obd.setCurrentOutputData() resets the log file if the key (= column name) has not been seen yet.
###


""" Declaration of the format of PIDs ###
Currently the length argument is not optional. DEFAULT should match the payload length of the OBD answer.

Synopsis:
	obd.setPidResponseLength( int pid, int length=DEFAULT, bool returnByteArray=true )
"""

obd.setPidResponseLength( 0x49, 1, False ) # ACCELERATOR PEDAL POSITION D


""" Setup of functions that handle receiving OBD answers ###

Synopses:
	obd.setPidResponseCallback( int pid, function receivedCallback )
	receivedCallback( int pid, bytes   data )
	receivedCallback( int pid, int data )
	obd.getLastResponseData( int pid )
	obd.getCurrentOutputData( bytes key )
	obd.setCurrentOutputData( bytes key, mixed outputData )
"""

# ACCELERATOR PEDAL POSITION D
def _():
	min = 0x00 # vehicle-dependant
	max = 0xFF # vehicle-dependant
	coef = 1/( max-min )
	from utility import printT
	def callback( pid, data ):
		global obd
		obd.setCurrentOutputData( b"throttlePosition", ( data-min )*coef ) # no unit
		printT( "ACCELERATOR =", data )
	obd.setPidResponseCallback( 0x49, callback )
_()


""" Setup the sequence of OBD readings ###

Synopses:
	obd.resetSequence()
	obd.addPidToSequence( int pid )
"""

obd.resetSequence()
obd.addPidToSequence( 0x49 ) # ACCELERATOR PEDAL POSITION D
