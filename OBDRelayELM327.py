# Règle de conception : toujours attendre l'invite avant de redonner la main, sauf en cas d'exception.
# Règle de conception : une erreur de communication (sauf expiration) doit toujours engendrer une exception qui entraînera une nouvelle communication.
# Note: the ELM327 documentation informs that parasitic 0x00 bytes may occasionally be seen on the serial port. They are not ignored as recommended.

# TODO : nouvel objet de requête CAN multiple, utilisation individualisée par configuration => Messages "Capturing CAN identifiers xxx, xxx, xxx together will also capture CAN identifiers xxx, xxx, xxx." avec réglages des trames connues.


import threading
import serial
import sys

from datetime import datetime
from time import sleep
from time import time
from traceback import format_exc
from OBDRelayHTTPServer import WebSocket_vehicle

from utility import execfile
from utility import execfileIfNeeded
from utility import printT
from utility import setConsoleColorWindows
from utility import setConsoleTitle

import inspect
parametersFile = inspect.getfile( inspect.currentframe() )+"/../config/parameters.py"
sequenceFile   = inspect.getfile( inspect.currentframe() )+"/../config/sequenceELM327.py"

outputList = None
outputListLock = None

MAX_OBD_NEGOCIATION_TIME = 30

class OBDRelayELM327Thread( threading.Thread ):
	daemon = True # exit immediatly on program exit
	
	def __init__( self, vehicleData ):
		threading.Thread.__init__( self )
		self.parametersFileInfo = {}
		self.sequenceFileInfo = {}
		self.pidResponseCallbacks = {}
		self.lastResponseDatas = {}
		global outputList
		outputList = vehicleData[0]
		global outputListLock
		outputListLock = vehicleData[1]
		self.ser = None
		self.sequence = []
	
	class CanFrameRequest( tuple ):
		""" Special object to use in place of an OBD PID to request for a specific CAN frame identifier """
		identifier = property( lambda self: self[0] )
		identifierBits = property( lambda self: self[1] )
		minDataBytes = property( lambda self: self[2] )
		expireTime_s = property( lambda self: self[3] )
		def __new__( cls, identifier, identifierBits, minDataBytes, expireTime_s=0.1 ):
			identifier = int( identifier )
			identifierBits = int( identifierBits )
			minDataBytes = int( minDataBytes )
			expireTime_s = float( expireTime_s )
			
			if not( identifierBits==11 or identifierBits==29 ):
				raise ValueError( "identifierBits must be 11 or 29" )
			if identifier<0:
				raise ValueError( "identifier cannot be negative" )
			if   identifierBits==11:
				if identifier>0x7FF:
					raise ValueError( "identifier is too big for an 11-bit CAN identifier" )
			elif identifierBits==29:
				if identifier>0x1FFFFFFF:
					raise ValueError( "identifier is too big for a 29-bit CAN identifier" )
			if   minDataBytes<1:
				raise ValueError( "minDataBytes must be 1 at minimum" )
			elif minDataBytes>8:
				raise ValueError( "minDataBytes must be 8 at maximum" )
			if expireTime_s<=0.:
				raise ValueError( "expireTime_s must be greater than 0" )
			
			obj = super().__new__( cls, (
				identifier,
				identifierBits,
				minDataBytes,
				expireTime_s,
			) )
			return obj
	
	logger = None
	def attachLoggingThread( self, logger ):
		self.logger = logger
	
	def reloadParameters( self ):
		global parametersFile
		parameters = {}
		if execfileIfNeeded( parametersFile, parameters, self.parametersFileInfo ):
			self.serialPort = parameters["serialPort"]
			self.serialBaudRateInitial = parameters["serialBaudRateInitial"]
			self.serialBaudRateDesired = parameters["serialBaudRateDesired"]
			self.serialBaudRateDesiredForce = parameters["serialBaudRateDesiredForce"]
			self.serialTimeoutWhileOBD = parameters["serialTimeoutWhileOBD"]
			self.serialShowSentBytes = parameters["serialShowSentBytes"]
			self.serialShowReceivedBytes = parameters["serialShowReceivedBytes"]
			self.scannerATSP = parameters["ATSP"] # OBD bus selection
			self.obdShowIncorrectResult = parameters["obdShowIncorrectResult"]
			scannerATBRD = round( 4000000/self.serialBaudRateDesired )
			if scannerATBRD>0xFF:
				printT( "The parameter serialBaudRateDesired is set to an insufficient value!" )
			self.scannerATBRD = b"ATBRD"+bytes( "%.2X"%round( 4000000/self.serialBaudRateDesired ), "ascii" )+b"\x0D" # desired baudrate
			
			obdCanFrameReq11 = parameters["obdCanFrameReq11"]
			obdCanFrameReq29 = parameters["obdCanFrameReq29"]
			self.obdCanFramePrep11 = self.obdCanFramePrepLoaded[obdCanFrameReq11]
			self.obdCanFramePrep29 = self.obdCanFramePrepLoaded[obdCanFrameReq29]
			self.obdCanFrameReq11 = self.obdCanFrameReqLoaded[obdCanFrameReq11]
			self.obdCanFrameReq29 = self.obdCanFrameReqLoaded[obdCanFrameReq29]
			self.obdCanFrameCleanup11 = self.obdCanFrameCleanupLoaded[obdCanFrameReq11]
			self.obdCanFrameCleanup29 = self.obdCanFrameCleanupLoaded[obdCanFrameReq29]
			
			if self.logger is not None:
				self.logger.setParameters( parameters )
			printT( "[OBDRelayELM327.py] Parameters have been reloaded." )
	
	def reloadSequence( self ):
		global sequenceFile
		global outputList
		global outputListLock
		if execfileIfNeeded( sequenceFile, {"obd":self}, self.sequenceFileInfo ):
			with outputListLock:
				outputList.clear() # erase any obsolete JSON data
			printT( "The OBD sequence has been reloaded." )
			if self.logger is not None:
				parameters = {}
				execfile( parametersFile, parameters )
				self.logger.setParameters( parameters )
	
	lastShownReceived = False
	def write( self, data ):
		if self.serialShowSentBytes:
			printT( "    PC :", data.decode( "ascii", "replace" ) )
		OBDRelayELM327Thread.lastShownReceived = False
		return self.ser.write( data )
	def read( self, size=1 ):
		result = self.ser.read( size )
		if len( result )!=0:
			if self.serialShowReceivedBytes:
				if not OBDRelayELM327Thread.lastShownReceived:
					printT( "ELM327 :" )
				if result==b"\x0D":
					print( "" ) # new line
				elif result==b"\x0A":
					pass
				else:
					sys.stdout.write( result.decode( "latin_1" ) )
			OBDRelayELM327Thread.lastShownReceived = True
		else:
			if self.serialShowReceivedBytes:
				printT( "ELM327 : <timeout>" )
			OBDRelayELM327Thread.lastShownReceived = False
		return result
	
	# Reading of bytes until getting the prompt '>'; nothing must arrive after it.
	# Returns True if the prompt has been found.
	def waitForPrompt( self, errorMessageOnFailure=None, maxBytesToRead=32, noSilentTest=False ):
		# An exception is thrown only when errorMessageOnFailure is defined (character string).
		failure = False
		for numByte in range( maxBytesToRead ):
			newByte = self.read()
			if len( newByte )==0: # no prompt (timeout)
				failure = True
				break
			elif newByte==b'>':
				break
		self.ser.timeout = 0.5
		if not failure and ( noSilentTest or len( self.read() )==0 ):
			return True
		elif errorMessageOnFailure is None:
			return False
		else:
			raise Exception( errorMessageOnFailure )
	
	# Reading of an answer until getting the prompt '>' (returns immediately after that)
	# Returns the last non-empty line if the prompt is found, or False on timeout or if too many received bytes
	# There is a restart after a given number of failures.
	def readAnwer( self, errorMessageOnFailure=None, maxBytesToRead=64 ):
		lines = []
		# Reading of incoming lines
		currentLine = bytearray()
		for numByte in range( maxBytesToRead ):
			newByte = self.read()
			if len( newByte )==0:
				return False # no prompt (failure)
			newByteInt = newByte[0]
			if newByte==b'\x0D' or newByte==b'>':
				lines.append( currentLine.decode( "ascii", "replace" ) )
				currentLine = bytearray()
				if newByte==b'>':
					break
			elif newByteInt>0x00 and newByteInt<0x80:
				currentLine.extend( newByte )
		else: # exceeded max length
			self.read( 255 ) # flush with delay
			return False
		# Selection of the last non-empty line (considering length > 1)
		for i in range( len( lines )-1, -1, -1 ):
			line = lines[i]
			if len( line )>1:
				return line
		return lines[len( lines )-1]
	
	# Apply the desired baudrate
	def applyDesiredBaudRate( self ):
		if self.ser.baudrate!=self.serialBaudRateDesired:
			printT( "Switching baud rate (",self.scannerATBRD ,")..." )
			self.write( b"ATBRT00\x0D" )
			self.waitForPrompt( "No prompt after ATBRT00!" )
			self.write( self.scannerATBRD )
			self.ser.timeout = 2
			receivedO = False
			receivedOK = False
			unsupported = False
			newByte = None
			# Wait for "OK"
			for numByte in range( 8 ):
				newByte = self.read()
				if len( newByte )==0 or newByte==b'>':
					raise Exception( "No answer or invalid answer while applying the desired baudrate!" )
				elif newByte==b'?': # unsupported
					printT( "This chip version does not support changing the serial link bitrate, or wrong argument in "+self.scannerATBRD.decode( "ascii" )+"." )
					self.ser.timeout = 0.5
					unsupported = True
					self.waitForPrompt( "No prompt after unsupported ATBRD!" )
					break
				elif newByte==b'O':
					receivedO = True
				elif newByte==b'K':
					if receivedO:
						receivedOK = True
						break
				else:
					receivedO = False
			if unsupported:
				return False
			elif not receivedOK:
				raise Exception( "Invalid answer while applying the desired baudrate!" )
			# Switch baudrate
			self.ser.baudrate = self.serialBaudRateDesired
			# Wait for "ELM327" (without order checking)
			unsupported = False
			receivedStepsATI = {
				b'E': False,
				b'L': False,
				b'M': False,
				b'3': False,
				b'2': False,
				b'7': False,
			}
			receivedATI = False
			for numByte in range( 8 ):
				newByte = self.read()
				if len( newByte )==0:
					unsupported = True
					break
				elif newByte==b'7':
					receivedStepsATI[newByte] = True
					for byte in receivedStepsATI.keys():
						if not receivedStepsATI[byte]:
							unsupported = True
					if not unsupported:
						receivedATI = True
					else:
						self.waitForPrompt()
						self.ser.timeout = 0.5
					break
				elif newByte in receivedStepsATI:
					receivedStepsATI[newByte] = True
				else:
					for byte in receivedStepsATI.keys():
						receivedStepsATI[byte] = False
			# Wait for <CR>
			receivedCR = False
			if receivedATI and not unsupported:
				for numByte in range( 8 ):
					newByte = self.read()
					if newByte==b"\x0D":
						receivedCR = True
						break
			if ( not receivedATI ) or ( not receivedCR ) or unsupported:
				printT( "The communication did not work after applying the desired baudrate!" )
				self.ser.baudrate = self.serialBaudRateInitial
				self.waitForPrompt()
				self.ser.timeout = 0.5
				return False
			# Send confirmation
			self.write( b"\x0D" )
			self.ser.timeout = 0.5
			# Wait for prompt and reset waiting delay
			self.waitForPrompt( "No prompt after setting the desired baudrate!" )
			self.write( b"ATBRT0F\x0D" )
			self.waitForPrompt( "No prompt after ATBRT0F!" )
		return True
	
	## Methods for the "update vehicle information" sequence
	pidResponseLengths = {}
	pidResponseReturnByteArrays = {}
	def setPidResponseLength( self, pid, length, returnByteArray=True ):
		self.pidResponseLengths[pid] = length
		self.pidResponseReturnByteArrays[pid] = returnByteArray
	def setPidResponseCallback( self, pid, receivedCallback ):
		self.pidResponseCallbacks[pid] = receivedCallback
	def getLastResponseData( self, pid ):
		return self.lastResponseDatas.get( pid )
	def getCurrentOutputData( self, key ):
		global outputList
		global outputListLock
		with outputListLock:
			value = outputList.get( key )
		return value
	def setCurrentOutputData( self, key, outputData ):
		global outputList
		global outputListLock
		dataDateTime = datetime.now()
		WebSocket_vehicle.broadcastValue( key, outputData )
		with outputListLock:
			outputList[b"relaytime"] = time()
			outputList[key] = outputData
		# Logging:
		if self.logger is not None:
			self.logger.logData( key, outputData, dataDateTime )
	sequence = None
	pidToCommand = {} # formatted PID requests for ELM327
	def resetSequence( self ):
		self.sequence = []
	def addPidToSequence( self, pid ):
		self.sequence.append( pid )
		if isinstance( pid, self.CanFrameRequest ):
			pass
		else:
			self.pidToCommand[pid] = b"01"+bytes( "%.2X"%pid, "ascii" )+b"\x0D"
	## End
	
	def handleOBDResult( self, resultLine ):
		resultLineBytes = None
		try:
			resultLineBytes = bytes.fromhex( resultLine )
		except:
			if resultLine=="STOPPED":
				# The OBD interface was not ready, let it cool down for a while...
				printT( "Received a STOPPED alert" )
				self.write( b"0100\x0D" ) # retry initiating communication to the OBD bus
				self.ser.timeout = max( MAX_OBD_NEGOCIATION_TIME, self.serialTimeoutWhileOBD ) # very conservative
				if not self.waitForPrompt():
					printT( "Prompt not received after STOPPED!" ) # no exception: case handled naturally
				self.ser.timeout = self.serialTimeoutWhileOBD
				return
			else:
				if self.obdShowIncorrectResult:
					printT( "Incorrect OBD result (PID "+( "0x%.2X"%self.lastPid )+"): "+resultLine )
		if resultLineBytes is not None:
			resultType = resultLineBytes[0:1]
			if resultType==b"\x41":
				resultPid = resultLineBytes[1]
				resultData = resultLineBytes[2:( 2+self.pidResponseLengths[resultPid] )]
				if not self.pidResponseReturnByteArrays[resultPid]:
					resultData = int.from_bytes( resultData, 'big' )
				callback = self.pidResponseCallbacks.get( resultPid )
				if callback is not None:
					try:
						callback( resultPid, resultData )
					except:
						printT( format_exc() )
				self.lastResponseDatas[resultPid] = resultData # memorizing to make the value available from other callbacks
			elif resultType==b"\x7F":
				# The vehicle reported something. If unsupported then fix the sequence.
				# Unsupported PIDs may report this or time out.
				printT( "The ECU reported a 7F code for PID "+( "0x%.2X"%self.lastPid )+"): " )
			else:
				printT( "Unexpected OBD result type in: "+resultLine )
	
	def run( self ):
		self.reloadParameters()
		self.reloadSequence()
		self.lastPid = -1
		self.ser = serial.Serial( port=None, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, inter_byte_timeout=None )
		self.ser.exclusive = True # silently fails if "exclusive" does not exist
		isFirstAttempt = True
		while True:
			setConsoleColorWindows( "4F" )
			setConsoleTitle( "ELM327: Disconnected" )
			if self.ser.is_open:
				self.ser.close()
			if not isFirstAttempt:
				sleep( 1 )
			try:
				# Startup
				if not self.ser.is_open:
					# Configure and open the serial port
					self.reloadParameters()
					printT( "New connection to "+self.serialPort+"..." )
					self.ser.port = self.serialPort
					self.ser.open()
					# Communication attempt
					self.ser.baudrate = self.serialBaudRateInitial
					self.ser.timeout = 0.5
					printT( "Contacting the ELM327 chip..." )
					connectionConfirmed = False
					while not connectionConfirmed:
						self.write( b"ATH\x0D" ) # command that does nothing
						connectionConfirmed = self.waitForPrompt()
						# Alternate between initial and desired baudrates
						if not connectionConfirmed:
							self.reloadParameters()
							if self.ser.baudrate==self.serialBaudRateInitial:
								self.ser.baudrate = self.serialBaudRateDesired
							else:
								self.ser.baudrate = self.serialBaudRateInitial
					printT( "Connection works at "+str( self.ser.baudrate )+" b/s" )
					# Reset
					if self.ser.baudrate==self.serialBaudRateDesired:
						# Note: on my Icar01 ELM327 V1.5, ATWS resets the baud rate. This is a workaround.
						self.write( b"ATD\x0D" )
					else:
						self.write( b"ATWS\x0D" )
					self.ser.timeout = 5
					self.waitForPrompt( "No prompt after ATWS or ATD!" ) # resets the timeout to 0.5
					# Apply parameters (except new baudrate)
					self.write( b"ATE0\x0D" ) # no echo
					self.waitForPrompt( "No prompt after ATE0!" )
					self.write( b"ATL0\x0D" ) # no <LF> after <CR>
					self.waitForPrompt( "No prompt after ATL0!" )
					self.write( b"ATS0\x0D" ) # no spaces
					self.waitForPrompt( "No prompt after ATS0!" )
					self.write( b"ATCAF1\x0D" ) # display only the OBD payload
					self.waitForPrompt( "No prompt after ATCAF1!" )
					self.write( b"ATSP"+self.scannerATSP+b"\x0D" ) # selection of the OBD bus
					self.waitForPrompt( "No prompt after ATSP!" )
					self.write( b"0100\x0D" ) # try initiating communication to the OBD bus
					self.ser.timeout = max( MAX_OBD_NEGOCIATION_TIME, self.serialTimeoutWhileOBD ) # very conservative
					self.waitForPrompt( "No prompt after initial 0100! Is the ignition on?" )
					self.ser.timeout = 5
					# Apply the desired baudrate
					if not self.applyDesiredBaudRate():
						if self.serialBaudRateDesiredForce:
							raise Exception( "The desired baud rate could not be selected!" )
					printT( "Connection established at "+str( self.ser.baudrate )+" b/s" )
					setConsoleColorWindows( "2F" )
					setConsoleTitle( "ELM327: "+str( self.ser.baudrate )+" b/s" )
				# Read OBD information until thread exit
				straightErrorCount = 0
				counter = 0 # counts the number of executed sequences
				self.ser.timeout = max( MAX_OBD_NEGOCIATION_TIME, self.serialTimeoutWhileOBD ) # very conservative (1st request)
				isFirstRequest = True
				isReadingCan29 = False
				isReadingCan11 = False
				while True:
					# Send and handle requests from the configured sequence:
					for pid in self.sequence:
						self.ser.reset_input_buffer()
						if isinstance( pid, self.CanFrameRequest ):
							# Reading of a CAN frame identifier:
							req = pid
							if req.identifierBits==29:
								if not isReadingCan29:
									self.obdCanFramePrep29( self )
									isReadingCan29 = True
								resultData = self.obdCanFrameReq29( self, req )
							else:
								if not isReadingCan11:
									self.obdCanFramePrep11( self )
									isReadingCan11 = True
								resultData = self.obdCanFrameReq11( self, req )
							if resultData:
								callback = self.pidResponseCallbacks.get( req )
								if callback is not None:
									try:
										callback( req.identifier, resultData )
									except:
										printT( format_exc() )
									callback = None
							req = None
							resultData = None
						else:
							# Reading of an OBD PID:
							if isReadingCan29 or isReadingCan11:
								if self.obdCanFrameCleanup29==self.obdCanFrameCleanup11:
									self.obdCanFrameCleanup29( self )
								else:
									if isReadingCan29:
										self.obdCanFrameCleanup29( self )
									if isReadingCan11:
										self.obdCanFrameCleanup11( self )
								isReadingCan29 = False
								isReadingCan11 = False
							self.write( self.pidToCommand[pid] )
							self.lastPid = pid
							line = self.readAnwer()
							if line==False:
								straightErrorCount = straightErrorCount+1
							else:
								straightErrorCount = 0
								self.handleOBDResult( line )
						if isFirstRequest:
							isFirstRequest = False
							self.ser.timeout = self.serialTimeoutWhileOBD
					# Live-refresh of configuration:
					if counter%2==0:
						self.reloadSequence()
					else:
						self.reloadParameters()
					# Handle erroring communication:
					if straightErrorCount>=len( self.sequence ):
						raise Exception( "Unable to communicate on the serial port anymore!" )
					# Update the sequence counter:
					counter = counter+1
			except serial.SerialException as e:
				printT( e )
				isFirstAttempt = False
			except:
				printT( format_exc() )
				isFirstAttempt = False

def _():
	# These dicts are filled with methods that are picked when loading the configuration.
	obdCanFramePrepLoaded = {} # prepare for CAN readings
	OBDRelayELM327Thread.obdCanFramePrepLoaded = obdCanFramePrepLoaded
	obdCanFrameReqLoaded = {} # read a selected frame
	OBDRelayELM327Thread.obdCanFrameReqLoaded = obdCanFrameReqLoaded
	obdCanFrameCleanupLoaded = {} # restore for OBD readings
	OBDRelayELM327Thread.obdCanFrameCleanupLoaded = obdCanFrameCleanupLoaded
	
	def obdCanFrameReqBypass( self, req=None ):
		""" Dummy CAN frame read operation """
		pass
	obdCanFramePrepBypass = obdCanFrameReqBypass
	obdCanFrameCleanupBypass = obdCanFrameReqBypass
	obdCanFramePrepLoaded[None] = obdCanFramePrepBypass
	obdCanFrameReqLoaded[None] = obdCanFrameReqBypass
	obdCanFrameCleanupLoaded[None] = obdCanFrameCleanupBypass
	
	def obdCanFramePrepCaf0CraRtr( self ):
		""" Run ATCAF0 """
		self.write( b"ATCAF0\x0D" ) # display the whole CAN payload
		self.waitForPrompt( noSilentTest=True )
	
	def obdCanFrameCleanupCaf0CraRtr( self ):
		""" Run ATCRA + ATCAF1 """
		self.write( b"ATCRA\x0D" ) # reset the CAN identifier = back to OBD
		self.waitForPrompt( noSilentTest=True )
		self.write( b"ATCAF1\x0D" ) # display only the OBD payload
		self.waitForPrompt( noSilentTest=True )
	
	for method in {"CAF0_CRA_RTR_STOPPED", "CAF0_CRA_RTR"}:
		def _():
			alwaysForcedStopped = ( method=="CAF0_CRA_RTR_STOPPED" )
			
			def obdCanFrameReqCaf0CraRtr( self, req ):
				""" CAN frame read operation using ATCAF0, ATCRAxxxxxxxx, ATRTR + stopping the loop
				This is by design less reliable than OBD readings (difficulty to detect errors).
				"""
				# TODO - use a timewatch and log + compare with OBD requests
				
				# Preparation
				data = None
				if req.identifierBits==29:
					self.write( b"ATCRA"+bytes( "%.8X"%req.identifier, "ascii" )+b"\x0D" ) # select the CAN identifier
				else:
					self.write( b"ATCRA"+bytes( "%.3X"%req.identifier, "ascii" )+b"\x0D" ) # select the CAN identifier
				self.waitForPrompt( noSilentTest=True )
				self.ser.timeout = req.expireTime_s
				self.write( b"ATRTR\x0D" ) # read CAN frames (just one, or maybe in a loop)
				
				# Try to receive a CAN frame's payload:
				maxBytesToRead = 64
				currentLine = bytearray()
				nothingReceived = False
				receivedPrompt = False
				for numByte in range( maxBytesToRead ):
					newByte = self.read()
					if len( newByte )==0:
						nothingReceived = True
						break # nothing received
					newByteInt = newByte[0]
					if newByte==b'\x0D' or newByte==b'>':
						# Received a complete line:
						if len( currentLine )*2>=req.minDataBytes:
							try:
								data = bytearray.fromhex( currentLine.decode( "ascii" ) )
								break
							except ValueError:
								pass
						currentLine = bytearray()
						if newByte==b'>':
							receivedPrompt = True
							break
					elif newByteInt>0x00 and newByteInt<0x80:
						currentLine.extend( newByte )
				self.ser.timeout = self.serialTimeoutWhileOBD
				
				# Wait for a prompt (graceful end), it may come or not:
				if not alwaysForcedStopped:
					if not receivedPrompt and not nothingReceived:
						maxBytesToRead = 3 # imagined max byte margin until receiving a planned prompt
						for numByte in range( maxBytesToRead ):
							newByte = self.read()
							if len( newByte )==0:
								break # nothing received
							if newByte==b'>':
								receivedPrompt = True
								break
				
				# Stop scanning and evacuate until prompt received:
				if not receivedPrompt:
					maxBytesToRead = 64 # retry exit for every 64 received bytes
					currentLine = bytearray()
					while not receivedPrompt:
						self.write( b"\x0D" ) # (Icar01 ELM327 V1.5 only accepts <CR> ALONE)
						# Warning: if no exit works, the program will remain stuck!
						for numByte in range( maxBytesToRead ):
							newByte = self.read()
							if len( newByte )==0:
								raise Exception( "ATRTR timed out during an exit attempt!" ) # nothing received
							newByteInt = newByte[0]
							if newByte==b'>':
								receivedPrompt = True
								break
				
				# Return
				return data
			
			obdCanFramePrepLoaded[method] = obdCanFramePrepCaf0CraRtr
			obdCanFrameReqLoaded[method] = obdCanFrameReqCaf0CraRtr
			obdCanFrameCleanupLoaded[method] = obdCanFrameCleanupCaf0CraRtr
		_();del _
_();del _
