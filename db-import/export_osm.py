#!/usr/bin/python
# -*- coding: UTF8 -*-
"""
Import osm and didok stops and match them
"""

import os
import re
import sys
import csv

import psycopg2
from optparse import OptionParser


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
    return row[0:2] + coords + row[5:] + (link,)

def export_osm(db, options, csv_file):
    print "export osm stops from %s" % (options.osm_table)
    cur = db.cursor()
    columns = ["uic_ref", "osm_name", "osm_type", "o.id", "ST_AsText(osm_geom)", "dist"]
    cur.execute("""SELECT %s FROM %s o LEFT OUTER JOIN %s m ON o.id = m.osm_id JOIN %s u ON o.user_id = u.id""" %
            (", ".join(columns), options.osm_table, options.match_table, options.username_table))

    osm_csv = csv.writer(open(csv_file, "w"))
    osm_csv.writerow(["#uic","OSM Name", "longitude", "latitude", "distance to DIDOK coords [m]", "link to OSM object"])
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


