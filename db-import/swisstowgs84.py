# -*- coding: utf-8 -*-

def CHtoWGS(CH):
	""" Converts a tupel (CHy, CHx) of swiss coordinates
	to a tupel (lat, lon) of WGS84 coordinates
	
	Accuracy about 1 meter according to Swisstopo. This should
	be sufficient for OSM purposes"""
	
	# substract the coordinates of Bern
	CHy, CHx = CH
	CHy = (float(CHy)-600000.)/1000000.
	CHx = (float(CHx)-200000.)/1000000.
	
	# latitude in units of 10000 seconds
	lat = 16.9023892 + 3.238272 * CHx
	lat -= 0.270978 * CHy**2
	lat -= 0.002528 * CHx**2
	lat -= 0.0447 * CHy**2*CHx
	lat -= 0.0140 * CHx**3
	# convert to degrees
	lat *= 100./36.
	
	# longitude in units of 10000 seconds
	lon = 2.6779094 + 4.728982 * CHy
	lon += 0.791484 * CHy * CHx
	lon += 0.1306   * CHy * CHx**2
	lon -= 0.0436   * CHy**3
	# convert to degrees
	lon *= 100./36.
	
	return (lat,lon)

