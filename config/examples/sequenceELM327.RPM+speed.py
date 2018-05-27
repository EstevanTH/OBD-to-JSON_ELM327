obd.setPidResponseLength( 0x0D, 1, False ) # VEHICLE SPEED
obd.setPidResponseLength( 0x0C, 2, False ) # ENGINE RPM


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


obd.resetSequence()
obd.addPidToSequence( 0x0D ) # SPEED
obd.addPidToSequence( 0x0C ) # RPM
