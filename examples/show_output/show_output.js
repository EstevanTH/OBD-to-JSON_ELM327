function onConnected(){
	document.body.className = "connected";
}
function onDisconnected(){
	document.body.className = "";
}
if( true ){
	let knownCellValues = {};
	let outputTable = document.getElementById( "outputTable" );
	function updateData( obdObject ){
		for( key in obdObject ){
			var cellValue = knownCellValues[key];
			if( !cellValue ){
				var row = document.createElement( "TR" );
					var cellKey = document.createElement( "TH" );
						cellKey.innerText = key;
					row.appendChild( cellKey );
					cellValue = document.createElement( "TD" );
					row.appendChild( cellValue );
				outputTable.appendChild( row );
				knownCellValues[key] = cellValue;
			}
			cellValue.innerText = obdObject[key].toString();
		}
	}
}
