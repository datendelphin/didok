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

import swisstowgs84

#didok column settings
internal_text_columns = ["name", "gonr", "xkoord", "ykoord", "goabk",
                         "gemeinde_nr", "gemeinde", "kanton", "bp",
                         "vp", "vk", "verkehrsmittel"]
internal_int_columns = ["dstnr", "hoehe"]
header_to_internal = {"DSt-Nr":"dstnr",
                      "Dst-Nr":"dstnr",
                      "Name":"name",
                      "GO-Nr":"gonr",
                      "GO-Abk":"goabk",
                      "Gde-Nr":"gemeinde_nr",
                      "Gde":"gemeinde",
                      "Kt.":"kanton",
                      "BP":"bp",
                      "VP":"vp",
                      "Höhe":"hoehe",
                      "X-Koord.":"xkoord",
                      "Y-Koord.":"ykoord",
                      "Verkehrsmittel":"verkehrsmittel",
                      }

def table_exists(db, table_name):
    cur = db.cursor()
    cur.execute("SELECT EXISTS(SELECT * FROM information_schema.tables WHERE table_name='%s')"
            % (table_name))

    return cur.fetchone()[0]

def import_didok(db, options, csv_file):
    cur = db.cursor()
    
    if table_exists(db, options.import_table):
        cur.execute("DELETE FROM %s" % options.import_table)
    else:
        text_fields = " ".join([",\n" + c + " TEXT" for c in internal_text_columns])
        int_fields = " ".join([",\n" + c + " INT" for c in internal_int_columns])
        cur.execute("CREATE TABLE " + options.import_table + """ (
            id SERIAL PRIMARY KEY""" +
            text_fields +
            int_fields + """,
            type character(1),
            version INT
        )""")

        cur.execute("SELECT AddGeometryColumn('%s', 'import_geom', 4326, 'POINT', 2)"
                % (options.import_table))

        cur.execute("CREATE INDEX didok_stops_index ON %s USING gist (import_geom)"
                % (options.import_table))

    #cur.execute("GRANT SELECT ON TABLE %s TO \"www-data\"" % (options.import_table))

    fulltable = options.match_table

    version = 0
    didok = list(csv.reader(open(csv_file), delimiter=';', quotechar='"'))
    headers = didok[0]
    del didok[0]

    # create translation of columns to internal fields
    internal_to_column = {}
    for i,header in enumerate(headers):
        if header in header_to_internal:
            internal_to_column[header_to_internal[header]] = i

    print "detected fields"
    for i in internal_to_column:
        print "    %s: column %d" % (i, internal_to_column[i])

    if "xkoord" in internal_to_column:
        xkoord_col = internal_to_column["xkoord"]
    else:
        print "xkoord column not found"
        return

    if "ykoord" in internal_to_column:
        ykoord_col = internal_to_column["ykoord"]
    else:
        print "ykoord column not found"
        return

    if "dstnr" in internal_to_column:
        dstnr_col = internal_to_column["dstnr"]
    else:
        print "dstnr column not found"
        return
    
    print "Starting import " + csv_file
    skipped_lines = 0
    for row in didok:
        infos = list(row);
        infos = [x.strip() for x in infos]
        # match 
        # only use rows which have a valid uic number and valid coordinates
        try:
            infos[dstnr_col] = int(infos[dstnr_col]) + 8500000
            lat, lon = swisstowgs84.CHtoWGS((float(infos[xkoord_col])*1000,
                                             float(infos[ykoord_col])*1000))
            for i in internal_int_columns:
                if i in internal_to_column:
                    if infos[internal_to_column[i]] != "":
                        infos[internal_to_column[i]] = int(infos[internal_to_column[i]])
        except:
            skipped_lines += 1
            continue

        fields = (internal_to_column.keys())
        values = [infos[internal_to_column[field]] for field in fields]

        query = "INSERT INTO "
        query += options.import_table
        query += " (" + ", ".join(fields) + """, type, version, import_geom)
                       VALUES(""" + ("%s," * len(internal_to_column)
                       ) + "'?',%s,ST_GeomFromText('POINT(%s %s)', 4326));"
        cur.execute(query, values + [version, lon, lat])

    print "skipped %d lines in import of didok data" % (skipped_lines,)
    db.commit()

    # create annotation table if it doesn't exist
    if not table_exists(db, options.annotation_table):
        cur.execute("""CREATE TABLE %s (
            id SERIAL PRIMARY KEY,
            dstnr INT,
            text text
        )""" % (options.annotation_table))
        db.commit()



def import_osm(db, snapshot_db, options):
    print "import osm stops into %s" % (options.osm_table)
    cur = db.cursor()
    snapshot_cur = snapshot_db.cursor()
    if table_exists(db, options.osm_table):
        cur.execute("DELETE FROM %s" % options.osm_table)
    else:
        cur.execute("""
            CREATE TABLE %s (
                id        BIGINT,
                osm_name  TEXT,
                osm_type  TEXT,
                uic_ref   INT,
                tags      hstore,
                user_id   INT,
                version   INT
            )""" % (options.osm_table))

        cur.execute("SELECT AddGeometryColumn('%s', 'osm_geom', 4326, 'POINT', 2)"
             % (options.osm_table))

    #nodes
    snapshot_cur.execute("""
        SELECT
            id,
            tags -> 'name' AS name,
            'n' as type,
            (tags -> 'uic_ref')::INT AS uic_ref,
            tags,
            user_id,
            version,
            geom
        FROM nodes
        WHERE tags ? 'uic_ref'
        AND   tags -> 'uic_ref' ~  E'^\\\\d+$'""")

    cur.executemany("""
        INSERT INTO %s (id, osm_name, osm_type, uic_ref, tags, user_id, version, osm_geom)
        VALUES (%%s, %%s, %%s, %%s, %%s, %%s, %%s, %%s)""" % (options.osm_table), snapshot_cur.fetchall())

    #ways
    snapshot_cur.execute("""
        SELECT
            w.id,
            w.tags -> 'name' AS name,
            'w' as type,
            (w.tags -> 'uic_ref')::INT AS uic_ref,
            w.tags,
            w.user_id,
            w.version,
            ST_CENTROID(ST_MAKELINE(n.geom))
        FROM ways w, nodes n
        WHERE w.tags ? 'uic_ref'
        AND   w.tags -> 'uic_ref' ~  E'^\\\\d+$'
        AND n.id = ANY (w.nodes)
        GROUP BY w.id""")

    cur.executemany("""
        INSERT INTO %s (id, osm_name, osm_type, uic_ref, tags, user_id, version, osm_geom)
        VALUES (%%s, %%s, %%s, %%s, %%s, %%s, %%s, %%s)""" % (options.osm_table), snapshot_cur.fetchall())

    #relations
    snapshot_cur.execute("""
        SELECT
            r.id,
            r.tags -> 'name' AS name,
            'r' as type,
            (r.tags -> 'uic_ref')::INT AS uic_ref,
            r.tags,
            r.user_id,
            r.version,
            ST_CENTROID(ST_COLLECT(
                CASE
                    WHEN m.member_type = 'N' THEN
                        (SELECT ST_COLLECT(n.geom) FROM nodes n WHERE m.member_id = n.id)
                    WHEN m.member_type = 'W' THEN
                        (SELECT ST_COLLECT(n.geom) FROM nodes n, ways w WHERE n.id = ANY (w.nodes) AND w.id = m.member_id)
                END))
        FROM relations r JOIN relation_members m ON r.id = m.relation_id
        WHERE r.tags ? 'uic_ref'
          AND r.tags -> 'uic_ref' ~  E'^\\\\d+$'
        GROUP BY r.id""")

    cur.executemany("""
        INSERT INTO %s (id, osm_name, osm_type, uic_ref, tags, user_id, version, osm_geom)
        VALUES (%%s, %%s, %%s, %%s, %%s, %%s, %%s, %%s)""" % (options.osm_table), snapshot_cur.fetchall())

    db.commit()

    if table_exists(db, options.username_table):
        cur.execute("DELETE FROM %s" % options.username_table)
    else:
        cur.execute("""
            CREATE TABLE %s (
                id        INT,
                name      TEXT
            )""" % (options.username_table))

    snapshot_cur.execute("""SELECT * FROM users""")

    cur.executemany("""INSERT INTO %s VALUES (%%s, %%s)""" % (options.username_table),
            snapshot_cur.fetchall())

    db.commit()

def matches(db, options):
    print "calculating matches into %s" % (options.match_table)
    cur = db.cursor()

    if table_exists(db, options.match_table):
        cur.execute("DELETE FROM %s" % options.match_table)
    else:
        cur.execute("""CREATE TABLE %s 
                        ( osm_id bigint,
                          didok_id INT,
                          dist real
                        );""" % (options.match_table))
    

    ### matches

    cur.execute("""INSERT INTO %s
                       SELECT o.id, i.id, NULL
                           FROM %s o, %s i
                           WHERE o.uic_ref = i.dstnr AND i.version = 0
                """ % (options.match_table, options.osm_table, options.import_table))


    # Distances are just for display.
    cur.execute("""UPDATE %s SET dist=ST_distance_spheroid(
                                     ST_transform(o.osm_geom, 4326), 
                                     ST_transform(i.import_geom, 4326),
                                     'SPHEROID["WGS 84",6378137,298.257223563,
                                     AUTHORITY["EPSG","7030"]]')
                  FROM %s o, %s i
                  WHERE o.id = osm_id AND i.id = didok_id
               """ % (options.match_table, options.osm_table, options.import_table))

    # Throw away lines where there was no distance, there is a partner missing
    cur.execute("DELETE FROM %s WHERE dist is NULL;" % options.match_table)

    #cur.execute("GRANT SELECT ON TABLE %s TO \"www-data\"" % (fulltable))

    db.commit()
            
if __name__ == "__main__":
    # fun with command line options
    parser = OptionParser(description=__doc__,
                          usage='%prog [options] didok-csv-file')
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
    parser.add_option('--didok_table', dest='import_table', default='didok_stops',
                       help='table to store match data into')
    parser.add_option('--didok_annotation_table', dest='annotation_table', default='didok_annotation',
                       help='table to store didok annotations')
    parser.add_option('--snapshotdbname', dest='snapshot_db', default='switzerland',
                       help='db with osm snapshot schema')
    parser.add_option('--user_table', dest='username_table', default='osm_usernames',
                       help='table to store osm user names in')
    parser.add_option('--update', action='store_true', dest='update', default=False,
                       help='update osm tables and make matches')

    (options, args) = parser.parse_args()

    if (options.update and len(args) != 0) or (not options.update and len(args) != 1):
        parser.print_help()
    else:
        db = psycopg2.connect('dbname=%s user=%s password=%s' % 
                (options.database, options.username, options.password))
        snapshot_db = psycopg2.connect('dbname=%s user=%s password=%s' % 
                (options.snapshot_db, options.username, options.password))
        if not options.update:
            import_didok(db, options, args[0])
        import_osm(db, snapshot_db, options)
        matches(db, options)


