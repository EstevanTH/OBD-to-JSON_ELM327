import http.server
import threading

from io import BytesIO
from utility import simpleDictionaryToJSON
from utility import printT
from time import time
from socketserver import ThreadingMixIn
from websocket import WebSocketBadRequest, WebSocket

try:
	from http import HTTPStatus
except ImportError:
	import http.client as HTTPStatus # Python36 -> Python34


outputList = None
outputListLock = None


class WebSocket_vehicle(WebSocket):
	maxReceivedLen = 125 # only short frames
	allowFramesBinary = False
	allowFramesText = False
	
	def handleMessage( self, data ):
		""" Incoming message handler: nothing allowed """
		pass
	
	@classmethod
	def broadcastValue( self, key, outputData ):
		""" Broadcast a new value (as JSON) - possible bottleneck """
		self.broadcastMessageText( simpleDictionaryToJSON( {
			b"relaytime": time(),
			key: outputData,
		} ) )


class OBDRelayHTTPRequestHandler( http.server.BaseHTTPRequestHandler ):
	# Based on http.server.SimpleHTTPRequestHandler
	server_version = "ELM327 OBD-II Relay"
	protocol_version = "HTTP/1.1" # mandatory for WebSocket
	runWebSocket = False
	webSocketClass = None
	
	def do_GET( self ):
		try:
			f = self.send_head()
			self.copyfile( f, self.wfile )
		except ConnectionError:
			return
		finally:
			if f is not None:
				f.close()
			del f
		
		if self.runWebSocket:
			try:
				ws = self.webSocketClass( self )
				ws.run()
			except ConnectionError:
				pass
			except StopIteration:
				pass
			except WebSocketBadRequest as e:
				printT( repr( e ) )
				return
	
	def do_HEAD( self ):
		try:
			f = self.send_head( headersOnly=True )
		except ConnectionError:
			return
		finally:
			if f is not None:
				f.close()
			del f
	
	def send_head( self, headersOnly=False ):
		headers = {}
		
		if self.path=="/vehicle.json":
			global outputList
			global outputListLock
			expired = False
			outputListCopy = None
			with outputListLock:
				outputListCopy = outputList.copy()
			if b"relaytime" not in outputListCopy:
				expired = True # no data yet
			elif self.server.thread.cacheExpire==0.0:
				pass
			elif time()>outputListCopy[b"relaytime"]+self.server.thread.cacheExpire:
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
		elif self.path=="/vehicle.ws":
			self.webSocketClass = WebSocket_vehicle
			info = WebSocket.prepareHeaders( self )
			encoded = info["encoded"]
			response = info["response"]
			contentType = info["contentType"]
			headers = info["headers"]
		else:
			encoded = b"Not found"
			response = HTTPStatus.NOT_FOUND
			contentType = "text/plain"
		
		f = BytesIO()
		f.write( encoded )
		f.seek( 0 )
		self.send_response( response )
		if contentType is not None:
			self.send_header( "Content-type", contentType )
		if headersOnly:
			self.send_header( "Content-Length", "0" )
		else:
			self.send_header( "Content-Length", str( len( encoded ) ) )
		for header in headers.items():
			self.send_header( header[0], header[1] )
		self.send_header( "Access-Control-Allow-Origin", "*" )
		self.end_headers()
		return f
	
	copyfile = http.server.SimpleHTTPRequestHandler.copyfile
	
	def log_request( self, code='-', size='-' ):
		pass # no logging for successful requests


class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
	daemon_threads = True


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
	
	def run( self ):
		httpd = ThreadedHTTPServer( (self.ipAddress, self.tcpPort), OBDRelayHTTPRequestHandler )
		httpd.thread = self
		printT( "OBDRelayHTTPServerThread started:", self.ipAddress, self.tcpPort )
		httpd.serve_forever()
