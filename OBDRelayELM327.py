# Règle de conception : toujours attendre l'invite avant de redonner la main, sauf en cas d'exception.
# Règle de conception : une erreur de communication (sauf expiration) doit toujours engendrer une exception qui entraînera une nouvelle communication.
# Note: the ELM327 documentation informs that parasitic 0x00 bytes may occasionally be seen on the serial port. They are not ignored as recommended.


import threading
import serial

from datetime import datetime
from time import sleep
from time import time
from traceback import format_exc
from os import system

from utility import execfileIfNeeded
from utility import printT
import inspect
parametersFile = inspect.getfile( inspect.currentframe() )+"/../config/parameters.py"
sequenceFile   = inspect.getfile( inspect.currentframe() )+"/../config/sequenceELM327.py"

outputList = None
outputListLock = None

MAX_OBD_NEGOCIATION_TIME = 20

class OBDRelayELM327Thread( threading.Thread ):
	def __init__( self, vehicleData ):
		threading.Thread.__init__( self )
		global outputList
		outputList = vehicleData[0]
		global outputListLock
		outputListLock = vehicleData[1]
		self.ser = None
		self.daemon = True # exit immediatly on program exit
	
	parametersFileInfo = {}
	logOutputData = None
	logOutputDataFile = None
	logOutputDataColumns = {}
	logOutputDataColumnsOrder = []
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
			self.scannerATBRD = b"ATBRD"+( b"%.2X"%round( 4000000/self.serialBaudRateDesired ) )+b"\x0D" # desired baudrate
			obdLogOutputData = parameters["obdLogOutputData"]
			if obdLogOutputData!=self.logOutputData:
				self.logOutputData = obdLogOutputData
				# Close any open file:
				if self.logOutputDataFile is not None:
					try:
						self.logOutputDataFile.close()
					except:
						pass
					self.logOutputDataFile = None
				# Attempt to open file:
				if self.logOutputData is not None:
					try:
						self.logOutputDataFile = open( self.logOutputData, mode="wb" )
					except Exception as e:
						self.logOutputDataFile = None
						printT( "Unable to open the obdLogOutputData file:", e )
				# Cleanup for clean start:
				self.logOutputDataColumns = {}
				self.logOutputDataColumnsOrder = []
			printT( "[OBDRelayELM327.py] Parameters have been reloaded." )
	
	sequenceFileInfo = {}
	def reloadSequence( self ):
		global sequenceFile
		if execfileIfNeeded( sequenceFile, {"obd":self}, self.sequenceFileInfo ):
			printT( "The OBD sequence has been reloaded." )
	
	def write( self, data ):
		if self.serialShowSentBytes:
			printT( "    PC :", data.decode( "ascii", "replace" ) )
		return self.ser.write( data )
	def read( self, size=1 ):
		result = self.ser.read( size )
		if self.serialShowReceivedBytes:
			if len( result )!=0:
				printT( "ELM327 :", result.decode( "ascii", "replace" ) )
			else:
				printT( "ELM327 : <timeout>" )
		return result
	
	# Reading of bytes until getting the prompt '>'; nothing must arrive after it.
	# Returns True if the prompt has been found.
	def waitForPrompt( self, errorMessageOnFailure=None, maxBytesToRead=32 ):
		# An exception is thrown only when exceerrorMessageOnFailure is defined (character string).
		failure = False
		for numByte in range( maxBytesToRead ):
			newByte = self.read()
			if len( newByte )==0: # no prompt (timeout)
				failure = True
				break
			elif newByte==b'>':
				break
		self.ser.timeout = 0.5
		if not failure and len( self.read() )==0:
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
		currentLine = []
		for numByte in range( maxBytesToRead ):
			newByte = self.read()
			newByteInt = None
			try:
				newByteInt = newByte[0]
			except:
				pass
			if len( newByte )==0:
				return False # no prompt (failure)
			elif newByte==b'\x0D' or newByte==b'>':
				lines.append( ( b''.join( currentLine ) ).decode( "ascii", "replace" ) )
				currentLine = []
				if newByte==b'>':
					break
			elif newByteInt>0x00 or newByteInt<0x80:
				currentLine.append( newByte )
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
			# Wait for "ELM327" (witout order checking)
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
	pidResponseCallbacks = {}
	def setPidResponseCallback( self, pid, receivedCallback ):
		self.pidResponseCallbacks[pid] = receivedCallback
	lastResponseDatas = {}
	def getLastResponseData( self, pid ):
		value = None
		try:
			value = self.lastResponseDatas[pid]
		except:
			pass
		return value
	def getCurrentOutputData( self, key ):
		global outputList
		global outputListLock
		value = None
		outputListLock.acquire()
		try:
			value = outputList[key]
		except:
			pass
		outputListLock.release()
		return value
	def setCurrentOutputData( self, key, outputData ):
		global outputList
		global outputListLock
		now = time()
		outputListLock.acquire()
		outputList[b"relaytime"] = now
		outputList[key] = outputData
		outputListLock.release()
		# Logging:
		if self.logOutputDataFile is not None:
			try:
				if key not in self.logOutputDataColumns:
					self.logOutputDataColumns[key] = True
					self.logOutputDataColumnsOrder = list( self.logOutputDataColumns.keys() )
					self.logOutputDataColumnsOrder.sort()
					self.logOutputDataFile.seek( 0 )
					self.logOutputDataFile.truncate()
					self.logOutputDataFile.write( b'"Time","Updated","'+b'","'.join( self.logOutputDataColumnsOrder )+b'"\x0D\x0A' )
				CSVDataColumns = [b'"'+str( datetime.now() ).encode( "ascii", "replace" )+b'"', b'"'+key+b'"']
				for key1 in self.logOutputDataColumnsOrder:
					dataValue = outputList[key1]
					dataType = type( dataValue )
					CSVDataColumn = '"#"'
					try:
						if dataType is float or dataType is int:
							CSVDataColumn = str( dataValue ).encode( "ascii" )
						elif dataType is bool:
							if dataValue:
								CSVDataColumn = b'1'
							else:
								CSVDataColumn = b'0'
						elif dataValue is None:
							CSVDataColumn = b'""'
						else:
							if dataType is bytes or dataType is bytearray:
								pass
							else:
								dataValue = str( dataValue ).encode( "utf_8", "replace" )
							CSVDataColumn = b'"'+dataValue.replace( b'"',  b"'" )+b'"'
					except:
						pass
					CSVDataColumns.append( CSVDataColumn )
				self.logOutputDataFile.write( b','.join( CSVDataColumns )+b'\x0D\x0A' )
			except Exception as e:
				printT( "Logging error, stopping:", e )
				try:
					logOutputDataFile = self.logOutputDataFile
					self.logOutputDataFile = None
					logOutputDataFile.close()
				except:
					pass
	sequence = []
	pidToCommand = {} # formatted PID requests for ELM327
	def resetSequence( self ):
		self.sequence.clear()
	def addPidToSequence( self, pid ):
		self.sequence.append( pid )
		self.pidToCommand[pid] = b"01"+( b"%.2X"%pid )+b"\x0D"
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
					printT( "Prompt not received after STOPPED!" )
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
				callback = self.pidResponseCallbacks[resultPid]
				callback( resultPid, resultData )
				self.lastResponseDatas[resultPid] = resultData # memorizing to make the value available from other callbacks
			elif resultType==b"\x7F":
				# The vehicle reported something, we do not care about that. If unsupported then fix the sequence.
				pass
			else:
				printT( "Unexpected OBD result type in: "+resultLine )
	
	def run( self ):
		self.reloadParameters()
		self.reloadSequence()
		self.lastPid = -1
		self.ser = serial.Serial( port=None, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=True )
		isFirstAttempt = True
		while True:
			system( "COLOR 4F" )
			system( "TITLE ELM327: Disconnected" )
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
						# Note: on my ELM327 V1.5 (counterfeit), ATWS resets the baud rate. This is a workaround.
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
					self.write( b"ATSP"+self.scannerATSP+b"\x0D" ) # selection of the OBD bus
					self.waitForPrompt( "No prompt after ATSP!" )
					# Apply the desired baudrate
					if not self.applyDesiredBaudRate():
						if self.serialBaudRateDesiredForce:
							raise Exception( "The desired baud rate could not be selected!" )
					printT( "Connection established at "+str( self.ser.baudrate )+" b/s" )
					system( "COLOR 2F" )
					system( "TITLE ELM327: "+str( self.ser.baudrate )+" b/s" )
				# Read OBD information until thread exit
				straightErrorCount = 0
				counter = 0 # counts the number of executed sequences
				self.ser.timeout = max( MAX_OBD_NEGOCIATION_TIME, self.serialTimeoutWhileOBD ) # very conservative (1st request)
				isFirstRequest = True
				while True:
					# Send and handle requests from the configured sequence:
					for pid in self.sequence:
						self.ser.reset_input_buffer()
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
