if( true ){
	var obdRelayUrl = "ws://127.0.0.1:8327/vehicle.ws";
	
	// Get a suitable WebSocket constructor:
	let _WebSocket;
	try{
		_WebSocket = WebSocket;
	}catch( e ){}
	if( _WebSocket==undefined ){
		_WebSocket = MozWebSocket;
	}
	
	// Mechanism:
	let obdConnection = undefined;
	function connect(){
		obdConnection = new _WebSocket( obdRelayUrl );
		obdConnection.onopen = function( evt ){
			onConnected();
		};
		obdConnection.onclose = function( evt ){
			onDisconnected();
			connect();
		};
		obdConnection.onmessage = function( evt ){
			var obdObject = JSON.parse( evt.data );
			updateData( obdObject );
		};
	}
	
	// Start the magic!
	setTimeout( connect, 1 );
}