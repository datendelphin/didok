#!/usr/bin/python
# -*- coding: UTF8 -*-
"""
Import osm and didok stops and match them
"""

import os
import re
import sys
import csv
import itertools
import httplib
import urllib
import xml.etree.ElementTree as ET

import psycopg2
import psycopg2.extras
from optparse import OptionParser

import swisstowgs84

#tags to import for osm
osm_tags_import = [('railway','station',1),
                   ('railway','halt',1),
                   ('railway','tram_stop',2),
                   ('highway','bus_stop',4),
                   ('amenity','bus_station',4),
                   ('aerialway','station',8),
                   ('amenity','ferry_terminal',16),
                   ('railway','funicular',64)]

osm_transport_keys = [('train',1),
                      ('light_rail',1),
                      ('tram',2),
                      ('bus', 4),
                      ('trolleybus', 4),
                      ('aerialway',8),
                      ('ferry',16),
                      ('subway',32),
                      ('funicular',64)]

#didok column settings
internal_text_columns = ["name", "gonr", "xkoord", "ykoord", "goabk",
                         "gemeinde_nr", "gemeinde", "kanton", "bp",
                         "vp", "vk", "verkehrsmittel"]
internal_int_columns = ["dstnr", "hoehe"]
header_to_internal = {"DSt-Nr":"dstnr",
                      "Dst-Nr":"dstnr",
                      "Dst-Nr.":"dstnr",
                      "\xef\xbb\xbfDst-Nr.":"dstnr",
                      "Name":"name",
                      "Dst-Bezeichnung-offiziell":"name",
                      "GO-Nr":"gonr",
                      "GO-Abk":"goabk",
                      "Gde-Nr":"gemeinde_nr",
                      "Gde":"gemeinde",
                      "Kt.":"kanton",
                      "BP":"bp",
                      "VP":"vp",
                      "VPP":"vp",
                      "Höhe":"hoehe",
                      "X-Koord.":"xkoord",
                      "Y-Koord.":"ykoord",
                      "KOORDZ":"hoehe",
                      "KOORDX":"xkoord",
                      "KOORDN":"xkoord",
                      "KOORDY":"ykoord",
                      "KOORDE":"ykoord",
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

        cur.execute("CREATE INDEX idx_didok_stops_dstnr ON %s (dstnr)"
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
        if header.strip() in header_to_internal:
            internal_to_column[header_to_internal[header.strip()]] = i

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
            lat, lon = swisstowgs84.CHtoWGS((float(infos[ykoord_col]),
                                             float(infos[xkoord_col])))
            for i in internal_int_columns:
                if i in internal_to_column:
                    if infos[internal_to_column[i]] != "":
                        infos[internal_to_column[i]] = int(float(infos[internal_to_column[i]]))
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

    cur.execute("UPDATE %s SET import_geom = NULL WHERE xkoord = '000.000'" % (options.import_table))
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

    cur.execute('ANALYZE')
    db.commit()


def import_osm(db, options):
    print "import osm stops into %s" % (options.osm_table)
    psycopg2.extras.register_hstore(db)
    cur = db.cursor()
    cur.execute("""
        CREATE OR REPLACE FUNCTION convert_to_integer(v_input text)
            RETURNS INTEGER AS $$
            DECLARE v_int_value INTEGER DEFAULT NULL;
            BEGIN
                BEGIN
                    v_int_value := v_input::INTEGER;
                EXCEPTION WHEN OTHERS THEN
                    RETURN NULL;
                END;
                RETURN v_int_value;
            END;
        $$ LANGUAGE plpgsql;
    """)

    if table_exists(db, options.osm_table):
        cur.execute("DELETE FROM %s" % options.osm_table)
    else:
        cur.execute("""
            CREATE TABLE %s (
                id        BIGINT,
                parent    BIGINT,
                osm_name  TEXT,
                osm_type  TEXT,
                uic_ref   INT,
                tags      hstore,
                user_id   INT,
                version   INT,
                modeoftransport INT
            )""" % (options.osm_table))

        cur.execute("SELECT AddGeometryColumn('%s', 'osm_geom', 4326, 'POINT', 2)"
                % (options.osm_table))

        cur.execute("CREATE INDEX idx_osm_stops_uic_ref ON %s (uic_ref)"
                % (options.osm_table))

        cur.execute("CREATE INDEX osm_stops_index ON %s USING gist (osm_geom)"
                % (options.osm_table))

    table_placeholder = 'pointORwayORrelation';
    tags_conditionals = ["%s[%s=%s];" % (table_placeholder,k,v) for k,v,m in osm_tags_import]
    # for debug, only small area
    # tags_conditionals = ["%s[%s=%s](47.0993,8.3423,47.24684,8.5837);" % (table_placeholder,k,v) for k,v,m in osm_tags_import]
    overpass_filter =  '(\n' + table_placeholder + "[\"uic_ref\"~\"[0-9]+\"];\n"
    # for debug, only small area
    # overpass_filter =  '(\n' + table_placeholder + "[\"uic_ref\"~\"[0-9]+\"](47.0993,8.3423,47.24684,8.5837);\n"
    overpass_filter += "\n".join(tags_conditionals)
    overpass_filter += ");\n"
    overpass_query = overpass_filter + "out meta;"
    overpass_query = "/api/interpreter?" + urllib.urlencode({'data' : overpass_query})

    user_names = dict()
    def extract_users(root, user_names):
        for child in root:
            if child.tag in ("node", "way", "relation"):
                user_names[child.attrib["uid"]] = child.attrib["user"]

    #nodes
    #print overpass_query.replace(table_placeholder,'node');

    print "Query nodes from overpass"

    overpass_conn = httplib.HTTPSConnection("overpass.osm.ch")
    overpass_conn.request("GET", overpass_query.replace(table_placeholder,'node'))
    overpass_res = overpass_conn.getresponse()
    print "Query returned", overpass_res.status, overpass_res.reason, ", parsing node xml"

    node_root = ET.fromstring(overpass_res.read())

    def insert_nodes(node_root):
        for child in node_root:
            if child.tag == "node":
                tags = {tag.attrib["k"]: tag.attrib["v"] for tag in child}
                geom = "SRID=4326;POINT(%s %s)" % (child.attrib["lon"], child.attrib["lat"])
                yield [int(child.attrib["id"]), tags, int(child.attrib["uid"]), int(child.attrib["version"]), geom]

    cur.executemany("""
        INSERT INTO %s (id, osm_type, tags, user_id, version, osm_geom)
        VALUES (%%s, 'n', %%s, %%s, %%s, %%s)""" % (options.osm_table), insert_nodes(node_root))

    print "successfully inserted nodes into database"

    extract_users(node_root, user_names)

    db.commit()
    overpass_conn.close()
    
    #ways

    print "Query ways from overpass"

    overpass_query = "(" + overpass_filter + ">;\n);\nout meta;"
    overpass_query = "/api/interpreter?" + urllib.urlencode({'data' : overpass_query})

    #print overpass_query.replace(table_placeholder,'way');

    overpass_conn = httplib.HTTPSConnection("overpass.osm.ch")
    overpass_conn.request("GET", overpass_query.replace(table_placeholder,'way'))
    overpass_res = overpass_conn.getresponse()
    print "Query returned", overpass_res.status, overpass_res.reason, ", parsing way xml"

    way_root = ET.fromstring(overpass_res.read())

    way_nodes = dict()

    for child in way_root:
        if child.tag == "node":
            way_nodes[child.attrib["id"]] = child

    def insert_ways(way_root):
        for child in way_root:
            if child.tag == "way":
                nodes = [tag.attrib["ref"] for tag in child if tag.tag == "nd"]
                tags = {tag.attrib["k"]: tag.attrib["v"] for tag in child if tag.tag == "tag"}
                lat = lon = 0
                for node in nodes:
                    if node in way_nodes:
                        lat += float(way_nodes[node].attrib["lat"])
                        lon += float(way_nodes[node].attrib["lon"])
                lat /= len(nodes)
                lon /= len(nodes)
                geom = "SRID=4326;POINT(%s %s)" % (lon, lat)
                yield [int(child.attrib["id"]), tags, int(child.attrib["uid"]), int(child.attrib["version"]), geom]

    cur.executemany("""
        INSERT INTO %s (id, osm_type, tags, user_id, version, osm_geom)
        VALUES (%%s, 'w', %%s, %%s, %%s, %%s)""" % (options.osm_table), insert_ways(way_root))

    print "successfully inserted ways into database"

    extract_users(way_root, user_names)

    db.commit()
    overpass_conn.close()

    #relations

    print "Query relations from overpass"

    overpass_query = "(" + overpass_filter + ">;\n);\nout meta;"
    overpass_query = "/api/interpreter?" + urllib.urlencode({'data' : overpass_query})

    #print overpass_query.replace(table_placeholder,'relation');

    overpass_conn = httplib.HTTPSConnection("overpass.osm.ch")
    overpass_conn.request("GET", overpass_query.replace(table_placeholder,'relation'))
    overpass_res = overpass_conn.getresponse()
    print "Query returned", overpass_res.status, overpass_res.reason, ", parsing relation xml"

    relation_root = ET.fromstring(overpass_res.read())

    relation_nodes = dict()
    relation_ways = dict()

    for child in relation_root:
        if child.tag == "node":
            relation_nodes[child.attrib["id"]] = child
        if child.tag == "way":
            relation_ways[child.attrib["id"]] = child

    def insert_relations(relation_root):
        for child in relation_root:
            if child.tag == "relation":
                ways = [tag.attrib["ref"] for tag in child if tag.tag == "member" and tag.attrib["type"] == "way"]
                nodes = []
                for way in ways:
                    if way in relation_ways:
                        nodes += [tag.attrib["ref"] for tag in relation_ways[way] if tag.tag == "nd"]
                nodes += [tag.attrib["ref"] for tag in child if tag.tag == "member" and tag.attrib["type"] == "node"]
                tags = {tag.attrib["k"]: tag.attrib["v"] for tag in child if tag.tag == "tag"}
                lat = lon = 0
                for node in nodes:
                    if node in relation_nodes:
                        lat += float(relation_nodes[node].attrib["lat"])
                        lon += float(relation_nodes[node].attrib["lon"])
                lat /= len(nodes)
                lon /= len(nodes)
                geom = "SRID=4326;POINT(%s %s)" % (lon, lat)
                yield [int(child.attrib["id"]), tags, int(child.attrib["uid"]), int(child.attrib["version"]), geom]

    cur.executemany("""
        INSERT INTO %s (id, osm_type, tags, user_id, version, osm_geom)
        VALUES (%%s, 'r', %%s, %%s, %%s, %%s)""" % (options.osm_table), insert_relations(relation_root))


    print "successfully inserted relations into database"

    extract_users(relation_root, user_names)

    db.commit()
    overpass_conn.close()

    # fill uic_ref and name column
    cur.execute("UPDATE osm_stops SET (uic_ref, osm_name) = (convert_to_integer(tags -> 'uic_ref'), tags -> 'name')")


    # apply uic_ref from relations to elements
    # first collect set of all used nodes and ways    
    w_ids = set((way.attrib["id"] for way in way_root if way.tag == "way"))
    n_ids = set((node.attrib["id"] for node in node_root if node.tag == "node"))
    cur.execute("PREPARE insert_uic_n AS UPDATE osm_stops SET (uic_ref, parent) = ($1, $2) WHERE uic_ref IS NULL AND osm_type = 'n' AND id = $3")
    cur.execute("PREPARE insert_uic_w AS UPDATE osm_stops SET (uic_ref, parent) = ($1, $2) WHERE uic_ref IS NULL AND osm_type = 'w' AND id = $3")
    # iterate over all relations
    for relation in relation_root:
        if relation.tag == "relation":
            r_id = relation.attrib["id"]
            uic_ref = None
            for tag in relation:
                if tag.tag == "tag" and tag.attrib["k"] == "uic_ref":
                    uic_ref = tag.attrib["v"]
            if uic_ref:
                # iterate over all relation members
                for item in relation:
                    if item.tag == "member": # item for relation member (there are also tags)
                        if item.attrib["type"] == "way" and item.attrib["ref"] in w_ids:
                            cur.execute("EXECUTE insert_uic_w (%s, %s, %s)", (uic_ref, r_id, item.attrib["ref"]))
                        if item.attrib["type"] == "node" and item.attrib["ref"] in n_ids:
                            cur.execute("EXECUTE insert_uic_n (%s, %s, %s)", (uic_ref, r_id, item.attrib["ref"]))

    # add mode of transportation to OSM
    cur.execute("""UPDATE %s SET modeoftransport = 0""" % (options.osm_table))
    for k,v,m in osm_tags_import:
        cur.execute("""UPDATE %s SET modeoftransport = %%s | modeoftransport
                WHERE tags -> %%s = %%s""" %
                (options.osm_table), (m, k, v))
    for k,m in osm_transport_keys:
        cur.execute("""UPDATE %s SET modeoftransport = %%s | modeoftransport
                WHERE tags -> %%s = 'yes'""" %
                (options.osm_table), (m, k))

    db.commit()

    # copy user table
    if table_exists(db, options.username_table):
        cur.execute("DELETE FROM %s" % options.username_table)
    else:
        cur.execute("""
            CREATE TABLE %s (
                id        INT,
                name      TEXT
            )""" % (options.username_table))

    cur.executemany("""INSERT INTO %s VALUES (%%s, %%s)""" % (options.username_table),
            user_names.items())

    db.commit()
    cur.execute('ANALYZE')

    # update time of last import
    update_time_table = options.osm_table + "_update_time"
    if table_exists(db, update_time_table):
        cur.execute("DELETE FROM %s" % update_time_table)
    else:
        cur.execute("CREATE TABLE %s (time TIMESTAMP)" % (update_time_table))

    lasttime = "0000-00-00T00:00:00Z"
    for item in itertools.chain(node_root, way_root, relation_root):
        timestamp = item.attrib.get("timestamp", None)
        if timestamp:
            if lasttime < timestamp:
                lasttime = timestamp

    cur.execute("INSERT INTO %s VALUES (%%s)" % (update_time_table), (lasttime,)) 


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
    cur.execute('ANALYZE')
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
        if not options.update:
            import_didok(db, options, args[0])
        import_osm(db, options)
        matches(db, options)


