import http.server
import threading

from http import HTTPStatus
from io import BytesIO
from shutil import copyfileobj
from utility import simpleDictionaryToJSON
from utility import printT
from time import time

outputList = None
outputListLock = None

class OBDRelayHTTPServerThread( threading.Thread ):
	daemon = True # exit immediatly on program exit
	
	def __init__( self, vehicleData, ipAddress="127.0.0.1", tcpPort=8327, cacheExpire=0.0 ):
		threading.Thread.__init__( self )
		global outputList
		outputList = vehicleData[0]
		global outputListLock
		outputListLock = vehicleData[1]
		self.ipAddress = ipAddress
		self.tcpPort = tcpPort
		self.cacheExpire = cacheExpire
	
	def setCacheExpire( self, cacheExpire=0.0 ):
		self.cacheExpire = cacheExpire
	
	def getParameters( self ):
		return {
			"ipAddress": self.ipAddress,
			"tcpPort": self.tcpPort,
			"cacheExpire": self.cacheExpire,
		}
	
	def makeRequestHandler( httpServer ):
		class RequestHandler( http.server.BaseHTTPRequestHandler ):
			# Based on http.server.SimpleHTTPRequestHandler
			server_version = "ELM327 OBD-II Relay"
			
			def do_GET( self ):
				f = self.send_head()
				if f:
					try:
						self.copyfile( f, self.wfile )
					except ConnectionAbortedError:
						pass
					f.close()
			
			def do_HEAD( self ):
				f = self.send_head( headersOnly=True )
				if f:
					f.close()
			
			def send_head( self, headersOnly=False ):
				if self.path=="/vehicle.json":
					global outputList
					global outputListLock
					expired = False
					outputListCopy = None
					outputListLock.acquire()
					try:
						outputListCopy = outputList.copy()
					except:
						pass
					outputListLock.release()
					if b"relaytime" not in outputListCopy:
						expired = True # no data yet
					elif self.httpServer.cacheExpire==0.0:
						pass
					elif time()>outputListCopy[b"relaytime"]+self.httpServer.cacheExpire:
						expired = True
					if not expired:
						encoded = simpleDictionaryToJSON( outputListCopy )
					if not expired:
						response = HTTPStatus.OK
						contentType = "application/json"
					else:
						encoded = b"No available up-to-date data"
						response = HTTPStatus.GATEWAY_TIMEOUT
						contentType = "text/plain"
				else:
					encoded = b"Not found"
					response = HTTPStatus.NOT_FOUND
					contentType = "text/plain"
				
				f = BytesIO()
				f.write( encoded )
				f.seek( 0 )
				self.send_response( response )
				self.send_header( "Content-type", contentType )
				if headersOnly:
					self.send_header( "Content-Length", "0" )
				else:
					self.send_header( "Content-Length", str( len( encoded ) ) )
				self.send_header( "Access-Control-Allow-Origin", "*" )
				self.end_headers()
				return f
			
			def copyfile( self, source, outputfile ):
				copyfileobj( source, outputfile )
			
			def log_request( self, code='-', size='-' ):
				pass # no logging for successful requests
		
		RequestHandler.httpServer = httpServer
		
		return RequestHandler
	
	def run( self ):
		httpd = http.server.HTTPServer( (self.ipAddress, self.tcpPort), self.makeRequestHandler() )
		printT( "OBDRelayHTTPServerThread started:", self.ipAddress, self.tcpPort )
		httpd.serve_forever()
