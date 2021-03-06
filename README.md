# OBD to JSON Relay (ELM327)
This program reads OBD-II / EOBD values from an ELM327 chip (widely available) and makes them available through an HTTP server, formatted as a JSON object. It is great for a web overlay on OBS Studio.

News:
* Oct 2018: Added high-performance WebSocket support

## Features
- Designed for high frequency OBD readings
- Customizable sequence of OBD readings
- Automatic recover from most possible communication errors
- Allows any supported serial port baudrate (`AT BRD` command)
- Configuration is live-refreshed (no restart needed)
- Possibility to run multiple HTTP servers for better performance
- Nice console output to easily debug problems
- Optional CSV logging on updated output data

## Requirements
- An OBD scanner featuring an ELM327 / ELM329 chip (preferably connected through bare RS-232 or USB converter)
- [Python 3.6 or greater, extended to Python 3.4.4](https://www.python.org/downloads/)
- [pySerial 3.0.1 or greater](https://github.com/pyserial/pyserial)
- An OS supported by pySerial

## Instructions
1. Install *Python3*.
1. Install *pySerial*.
1. Edit the files `parameters.py` and `sequenceELM327.py` in the sub-directory `config`.
1. When you are ready to start, run `main.py`.

## Support
You can open an issue when you have a question, or you can join my Discord server [Yvon à bord !](https://discord.gg/pDasWGC) where you are very welcome, or see my contact details on my GitHub profile.
