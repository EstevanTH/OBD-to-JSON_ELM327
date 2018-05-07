# Prints a message, prefixed with the current time
from datetime import datetime
def printT( *arguments ):
	print( datetime.now().strftime( "%H:%M:%S" ), *arguments )

# Include a Python script in Python 3
def execfile( filename, globalEnv ):
	f = open( filename )
	source = f.read()
	f.close()
	# Note: replacements of global variables in the included script are not passed to the parent script.
	return exec( compile( source, filename, 'exec' ), globalEnv )

# Include a Python script if it has been modified
from os import stat
def execfileIfNeeded( filename, globalEnv, fileInfo ):
	if "date" not in fileInfo:
		fileInfo["date"] = None
	if "size" not in fileInfo:
		fileInfo["size"] = None
	fileInfoCurrent = stat( filename )
	if fileInfoCurrent.st_size!=fileInfo["size"] or fileInfoCurrent.st_mtime!=fileInfo["date"]:
		if ( fileInfo["date"] is None ) or ( fileInfo["size"] is None ):
			printT( "Loading "+filename )
		else:
			printT( "Reloading "+filename )
		fileInfo["size"] = fileInfoCurrent.st_size
		fileInfo["date"] = fileInfoCurrent.st_mtime
		execfile( filename, globalEnv )
		return True
	else:
		return False

# Convert a dict object (bytes keys and numeric values) into a JSON object as bytes, with JSONP support
def simpleDictionaryToJSON( source, callbackJSONP=None ):
	r = []
	for key in source.keys():
		r.append( b'"'+key+b'":'+str( source[key] ).encode( "ascii" ) )
	if callbackJSONP is None:
		return b'{\n'+b',\n'.join( r )+b'\n}'
	else:
		return callbackJSONP+b'({\n'+b',\n'.join( r )+b'\n});'