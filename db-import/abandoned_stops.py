#!/usr/bin/python
# -*- coding: UTF8 -*-
"""
create a list of osm stops which are no longer available according to DIDOK
"""

import os
import re
import sys
import csv

import psycopg2
from optparse import OptionParser

number_to_transport={1 :'Zug',
                     2 :'Tram',
                     4 :'Bus',
                     8 :'Luftseilbahn',
                     16:'Schiff',
                     32:'Metro',
                     64:'Funicular'}

def mode_of_transport(number):
    return ' '.join([number_to_transport[bit] for bit in number_to_transport if bit & number])


def column_transform(row):
    coords = tuple(row[4].strip("POINT(").strip(")").split())
    link = "https://www.openstreetmap.org/"
    if row[2] == "n":
        link += "node/"
    if row[2] == "w":
        link += "way/"
    if row[2] == "r":
        link += "relation/"
    link += str(row[3])
    name = row[1] + "(" + row[2] + str(row[3]) + ")"
    return row[1:2] + coords + row[0:1] + (mode_of_transport(row[5]), link)

def export_osm(db, options, csv_file):
    print "export abandoned stops from %s" % (options.osm_table)
    cur = db.cursor()
    columns = ["uic_ref", "osm_name", "osm_type", "o.id", "ST_AsText(osm_geom)", "modeoftransport"]
    cur.execute("""SELECT %s FROM %s o LEFT OUTER JOIN %s m ON o.id = m.osm_id JOIN %s u ON o.user_id = u.id WHERE m.didok_id IS NULL AND o.uic_ref IS NOT NULL AND u.name = 'DidokImportCH'""" %
            (", ".join(columns), options.osm_table, options.match_table, options.username_table))

    osm_csv = csv.writer(open(csv_file, "w"))
    osm_csv.writerow(["#Name", "longitude", "latitude", "uic", "mode of transport", "link to OSM object"])
    output = map(column_transform, cur.fetchall())
    osm_csv.writerows(output)

            
if __name__ == "__main__":
    # fun with command line options
    parser = OptionParser(description=__doc__,
                          usage='%prog [options] osm-csv-file')
    parser.add_option('--dbname', dest='database', default='didok',
                       help='name of database')
    parser.add_option('--dbuser', dest='username', default='osm',
                       help='database user')
    parser.add_option('--dbpassword', dest='password', default='',
                       help='password for database')
    parser.add_option('--match_table', dest='match_table', default='match',
                       help='table to store match data into')
    parser.add_option('--osm_table', dest='osm_table', default='osm_stops',
                       help='table to store match data into')
    parser.add_option('--user_table', dest='username_table', default='osm_usernames',
                       help='table to store osm user names in')

    (options, args) = parser.parse_args()

    if (len(args) != 1):
        parser.print_help()
    else:
        db = psycopg2.connect('dbname=%s user=%s password=%s' % 
                (options.database, options.username, options.password))
        export_osm(db, options, args[0])


