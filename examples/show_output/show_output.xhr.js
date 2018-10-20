if( true ){
	var obdRelayUrl = "http://127.0.0.1:8327/vehicle.json";
	var obdRate = 15; // requests per second
	
	// Mechanism:
	let relaytime = 0;
	let busy = false;
	function updateObd(){
		if( !busy ){
			var xhr = new XMLHttpRequest();
			xhr.open( "GET", obdRelayUrl, true );
			xhr.onreadystatechange = function(){
				if( xhr.readyState==4 ){
					busy = false;
					if( xhr.status==200 ){
						onConnected();
						var obdObject = JSON.parse( xhr.responseText );
						if( obdObject.relaytime!=relaytime ){
							relaytime = obdObject.relaytime;
							updateData( obdObject );
						}
					}
					else{
						onDisconnected();
						throw "Received a "+xhr.status+" HTTP status!";
					}
				}
			};
			busy = true;
			xhr.send( null );
		}
	}
	
	// Start the magic!
	setInterval( updateObd, 1000/obdRate );
	updateObd();
}