import threading
from datetime import datetime
from utility import printT

class OBDLoggingThread( threading.Thread ):
	daemon = False
	
	def __init__( self ):
		threading.Thread.__init__( self )
		
		self.pendingData = []
		self.pendingDataLock = threading.Lock()
		
		self.continueProcessLock = threading.Lock()
		self.continueProcessLock.acquire()
		self.terminating = False
		self.parametersLock = threading.Lock()
		
		self.logOutputData = None
		self.logOutputDataFile = None
		self.logOutputDataColumns = {}
		self.logOutputDataColumnsOrder = []
	
	def setParameters( self, parameters ):
		self.parametersLock.acquire()
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
		self.logOutputDataCompact = parameters["obdLogOutputDataCompact"]
		self.parametersLock.release()
	
	def logData( self, key, outputData ):
		if self.logOutputDataFile is not None:
			self.pendingDataLock.acquire()
			self.pendingData.append( (key,outputData) )
			self.pendingDataLock.release()
			try:
				self.continueProcessLock.release()
			except RuntimeError:
				pass
	
	def terminate( self ):
		self.terminating = True
		try:
			self.continueProcessLock.release()
		except RuntimeError:
			pass
	
	def run( self ):
		while not self.terminating:
			self.continueProcessLock.acquire()
			presentPendingData = True
			self.parametersLock.acquire()
			while presentPendingData:
				self.pendingDataLock.acquire()
				pendingData = self.pendingData
				self.pendingData = [] # cleanup
				self.pendingDataLock.release()
				presentPendingData = len( pendingData )!=0
				for onePendingData in pendingData:
					key = onePendingData[0]
					outputData = onePendingData[1]
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
							dataValue = outputData
							dataType = type( dataValue )
							CSVDataColumn = b'"#"'
							if self.logOutputDataCompact and key1!=key:
								CSVDataColumn = b''
							else:
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
			self.parametersLock.release()
