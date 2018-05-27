obd.setPidResponseLength( 0x33, 1, False ) # BAROMETRIC PRESSURE
obd.setPidResponseLength( 0x0C, 2, False ) # ENGINE RPM
obd.setPidResponseLength( 0x0B, 1, False ) # INTAKE MANIFOLD ABSOLUTE PRESSURE


# BAROMETRIC PRESSURE
def callback( pid, data ):
	global obd
	obd.resetSequence()
	obd.addPidToSequence( 0x0C ) # RPM
	obd.addPidToSequence( 0x0B ) # INTAKE PRESSURE
obd.setPidResponseCallback( 0x33, callback )

# ENGINE RPM
def callback( pid, data ):
	global obd
	obd.setCurrentOutputData( b"engineRPM", data/4 ) # RPM
obd.setPidResponseCallback( 0x0C, callback )

# INTAKE MANIFOLD ABSOLUTE PRESSURE
def callback( pid, pressionAdmi ):
	global obd
	# need both atmospheric pressure and intake manifold pressure to calculate boost
	pressionAtmo = obd.getLastResponseData( 0x33 )
	if pressionAtmo is not None:
		obd.setCurrentOutputData( b"boostPressure", ( pressionAdmi-pressionAtmo )/100 ) # bars
obd.setPidResponseCallback( 0x0B, callback )


obd.resetSequence()
obd.addPidToSequence( 0x33 ) # BAROMETRIC PRESSURE
