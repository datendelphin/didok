/* The Map */
var map;


var lineStyle = {
        "color": "#000000",
        "weight": 2,
        "opacity": 1
};

/* overlays */
var connected = new L.LayerGroup();
var onlydidok = new L.LayerGroup();
var onlyosm = new L.LayerGroup();
var badname = new L.LayerGroup();
var clusterlayer = new L.LayerGroup();
var worst100 = new L.LayerGroup();
var v1 = new L.LayerGroup();

/* base layers */
var osmch = L.tileLayer('//tile.osm.ch/switzerland/{z}/{x}/{y}.png', {maxZoom: 20,
                attribution: "Tiles <a href=\"http://creativecommons.org/licenses/by-sa/2.0/\">CC-by-SA</a> " +
		             "<a href=\"http://www.osm.ch\">osm.ch</a>"});
var osmorg = L.tileLayer('//tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 18,
		attribution: "Tiles <a href=\"http://creativecommons.org/licenses/by-sa/2.0/\">CC-by-SA</a> " +
		             "<a href=\"http://www.openstreetmap.org\">osm.org</a>"});
var transport = L.tileLayer('//tile.thunderforest.com/transport/{z}/{x}/{y}.png', {maxZoom: 18,
        attribution: "Tiles <a href=\"//creativecommons.org/licenses/by-sa/2.0/\">CC-by-SA</a> " +
                     "Andy Allan (<a href=\"//www.thunderforest.com\">thunderforest</a>)"});

function pointMarker(feature, latlng)
{
    var geojsonMarkerOptions = {
        radius: 3,
        fillColor: "#ff7800",
        fillOpacity: 1,
        color: '#ff0000',
        opacity: 0.5,
        weight: 4,
        stroke: false
    };

    if (feature.properties.state == "ON")
        geojsonMarkerOptions.fillColor = "#00FFFF";
    if (feature.properties.state == "VN")
        geojsonMarkerOptions.fillColor = "#FF0000";
    if (feature.properties.state == "OY")
        geojsonMarkerOptions.fillColor = "#00FF00";
    if (feature.properties.state == "OB")
        geojsonMarkerOptions.fillColor = "#FF30FF";
    if (feature.properties.state == "VY")
        geojsonMarkerOptions.fillColor = "#000000";
    if (feature.properties.state == "VI")
        geojsonMarkerOptions.fillColor = "#FFE000";
    if (feature.properties.state == "O1")
    {
        geojsonMarkerOptions.fillOpacity = 0;
        geojsonMarkerOptions.radius = 5;
        geojsonMarkerOptions.stroke = true;
        geojsonMarkerOptions.color = '#FF0000';
    }
    if (feature.properties.state == "OX")
    {
        geojsonMarkerOptions.fillOpacity = 0;
        geojsonMarkerOptions.radius = 5;
        geojsonMarkerOptions.stroke = true;
        geojsonMarkerOptions.color = '#FF9010';
    }
    if (feature.properties.state == "OC")
    {
        geojsonMarkerOptions.fillOpacity = 0;
        geojsonMarkerOptions.radius = 5;
        geojsonMarkerOptions.stroke = true;
        geojsonMarkerOptions.color = '#00E000';
    }
    return L.circleMarker(latlng, geojsonMarkerOptions).bindLabel(feature.properties.name);
}

function highlightFeature(e) {
    if (e.target.feature.properties.state != "O1" &&
        e.target.feature.properties.state != "OX" &&
        e.target.feature.properties.state != "OC")
    {
        e.target.setRadius(6);

        if (!L.Browser.ie && !L.Browser.opera) {
            e.target.bringToFront();
        }
    }
}

function resetHighlight(e) {
    if (e.target.feature.properties.state != "O1" &&
        e.target.feature.properties.state != "OX" &&
        e.target.feature.properties.state != "OC")
    {
        e.target.setRadius(3);
    }
}

function featurePopup(e) {

    info = $.get("didokstops/info/" + e.target.feature.properties.id,
                    function (data){
                        e.target.bindPopup(data);
                        e.target.openPopup();
                    }
                );

    if (!L.Browser.ie && !L.Browser.opera) {
        e.target.bringToFront();
    }
}

function onEachLine(feature, layer) {
    layer.on({
        click: featurePopup
    });
}

function onEachPoint(feature, layer) {
    layer.on({
        mouseover: highlightFeature,
        mouseout: resetHighlight,
        click: featurePopup
    });
}

function onMouseMove(e) {
    document.getElementById('map_footer_wgs84').innerHTML = e.latlng.lat.toFixed(6) + ", " + e.latlng.lng.toFixed(6);
    document.getElementById('map_footer_21781').innerHTML = WGStoCHx(e.latlng.lat, e.latlng.lng).toFixed(0) + ", " +
                                                            WGStoCHy(e.latlng.lng, e.latlng.lng).toFixed(0);
}

function permaLink() {
    var ll = map.getCenter();
    var layers = "";
    if (map.hasLayer(connected)) {layers += 'c';}
    if (map.hasLayer(onlydidok)) {layers += 'd';}
    if (map.hasLayer(onlyosm))  {layers += 'o';}
    if (map.hasLayer(badname)) {layers += 'b';}
    if (map.hasLayer(worst100)) {layers += 'w';}
    if (map.hasLayer(v1)) {layers += 's';}
    if (layers == "cdo") {layers = "";}
    else {layers = 's' + layers;}
    if (map.hasLayer(osmorg)) {
        layers = 'o' + layers.slice(1);}
    if (map.hasLayer(transport)) {
        layers = 't' + layers.slice(1);
    }
    if (layers.length > 0) {layers += ':';}
    return "<a href=\"/#" + layers + map.getZoom() + ":" + ll.lat.toFixed(6) + ":" + ll.lng.toFixed(6) + "\">permalink</a>";
}

function initMap() {

    $('#map').text('');

    var init_ll = false;
    var init_zoom = false;

    var overlays = {
        "connected stops" : connected,
        "stops only in didok" : onlydidok,
        "stops only in osm" : onlyosm,
        "wrong uic_name for didok id" : badname,
        "worst 100 matched stops" : worst100,
	"survey state of nodes" : v1
    };

    var basemaps = {
        "osm.ch" : osmch,
        "openstreetmap.org" : osmorg,
        "Transport by Andy Allan" : transport
    };

    var permaLinkBase = {
        'c': osmch,
        'o': osmorg,
        't': transport
    };

    var permaLinkOverlays = {
        "c" : connected,
        "d" : onlydidok,
        "o" : onlyosm,
        "b" : badname,
        "w" : worst100,
	"s" : v1
    };

    var baseLayer = osmch;
    var vectorLayers = [connected, onlydidok, onlyosm];

    if (window.location.hash) {
        var init_loc = window.location.hash.slice(1).split(':');
        if (isNaN(init_loc[0])) {
            if (init_loc[0][0] in permaLinkBase){
                baseLayer = permaLinkBase[init_loc[0][0]];
            }
            init_loc[0] = init_loc[0].slice(1);
            if (init_loc[0].length > 0){
                vectorLayers = [];
                for (var i = 0; i < init_loc[0].length; ++i){
                    if (init_loc[0][i] in permaLinkOverlays){
                        vectorLayers.push(permaLinkOverlays[init_loc[0][i]]);
                    }
                }
            }
            init_loc.splice(0,1);
        }
        if (!isNaN(init_loc[0]))
            init_zoom = init_loc[0];
        if (init_loc[1] && init_loc[2] ) {
        init_ll = new L.LatLng( init_loc[1], init_loc[2] );
        }
    }
    if (!init_ll)   { init_ll  = new L.LatLng( 47, 8 ); }
    if (!init_zoom) { init_zoom = 8; }
    map = L.map('map', {layers: vectorLayers, editInOSMControlOptions: {}});
    L.control.layers(basemaps, overlays).addTo(map);
    baseLayer.addTo(map);
    map.setView(init_ll, init_zoom);
    map.attributionControl.setPrefix("");
    
    document.getElementById('map_footer_permalink').innerHTML = permaLink();

    map.on('moveend', onMapMove);
    map.on('layeradd', onLayerAdd);
    map.on('mousemove', onMouseMove);

    getData();

    clusterlayer.addTo(map);

    /* Code und images borrowed from http://www.sutter.com/map */
    var slider = YAHOO.widget.Slider.getHorizSlider("sliderbg", "sliderthumb", -16, 220+16-4-1);
    slider.getRealValue = function() {return Math.round((this.getValue()-16)*100/(220-4-1))/100;};
    slider.setValue(220+16-2);
    slider.subscribe("change", function(offsetFromStart) {
        osmorg.setOpacity(slider.getRealValue());
        osmch.setOpacity(slider.getRealValue());
        transport.setOpacity(slider.getRealValue());
    });

}

function toggleLegendeView() {
    $("#routeview").toggleClass('opensidebar closedsidebar');
}

function getClusters() {
    clusterlayer.clearLayers();
    
    url="didokstops/clustering?";
    
    if (map.hasLayer(connected) || map.hasLayer(onlydidok))
        url += "didok=true&";
    
    if (map.hasLayer(connected) || map.hasLayer(onlyosm))
        url += "osm=true&";
    
    if (map.hasLayer(badname))
        url += "badname=true&";
    
    var bounds = map.getBounds();
    var minll=bounds.getSouthWest();
    var maxll=bounds.getNorthEast();
    url += 'bbox='+minll.lng+','+minll.lat+','+maxll.lng+','+maxll.lat;
    
    function clusterMarker(feature, latlng)
    {
        var geojsonMarkerOptions = {
            radius: 30,
            fillColor: "#ff7800",
            fillOpacity: 0.5,
            color: "#000000",
            stroke: true
        };

        name = "Zoom in to see more:<br>";
        if (feature.properties.nr_osm)
            name += "osm stops: " + feature.properties.nr_osm;

        if (feature.properties.nr_didok){
            if (name != "Zoom in to see more:<br>")
                name += ", ";
            name += "didok stops: " + feature.properties.nr_didok;
        }
        
        if (feature.properties.nr_badname){
            if (name != "Zoom in to see more:<br>")
                name += ", ";
            name += "badname stops: " + feature.properties.nr_badname;
        }
        
        return L.circleMarker(latlng, geojsonMarkerOptions).bindLabel(name);
    }
    $.get(url, function load(data) {
            eval(data);
            
            L.geoJson(points, {
                pointToLayer: clusterMarker
                }).addTo(clusterlayer);
        }
    );
}

function loadStops(data, layer){
    eval(data);
    
    layer.clearLayers();
    
    if ((layer == connected ||
        (layer == onlydidok && !map.hasLayer(connected)) ||
        (layer == onlyosm && !map.hasLayer(connected) && !map.hasLayer(onlydidok)) ||
        (layer == badname && !map.hasLayer(onlyosm) && !map.hasLayer(connected) && !map.hasLayer(onlydidok)))) {
        if (clustering)
            getClusters();
        else
            clusterlayer.clearLayers();
    }

    if (!clustering || layer == worst100)
    {
        L.geoJson(lines, {
            style: lineStyle,
            onEachFeature: onEachLine
        }).addTo(layer);
 
        L.geoJson(points, {
            pointToLayer: pointMarker,
            onEachFeature: onEachPoint
        }).addTo(layer);
    }

    if (map.hasLayer(badname)) {
        badname.eachLayer(function f(c){c.bringToFront();});
    }
}

function getStops(baseURL, layer){
    var bounds = map.getBounds();
    var minll=bounds.getSouthWest();
    var maxll=bounds.getNorthEast();
    var url=baseURL + 'bbox='+minll.lng+','+minll.lat+','+maxll.lng+','+maxll.lat;
    $.get(url, function load(data) { loadStops(data, layer);});
}

function getData(){
    if (map.hasLayer(connected)) {
        getStops("didokstops/list?", connected);
    }
    if (map.hasLayer(onlydidok)) {
        getStops("didokstops/onlydidok?", onlydidok);
    }
    if (map.hasLayer(onlyosm)) {
        getStops("didokstops/onlyosm?", onlyosm);
    }
    if (map.hasLayer(badname)) {
        getStops("didokstops/badname?", badname);
    }
    if (map.hasLayer(worst100)) {
        getStops("didokstops/list?", worst100);
    }
    if (map.hasLayer(v1)) {
        getStops("didokstops/v1?", v1);
    }
}

function getBadName(){
    getStops("http://didok.osmd.ch/media/static/badname");
}

function onMapMove(e) {
    getData();

    document.getElementById('map_footer_permalink').innerHTML = permaLink();
}

function onLayerAdd(e) {
    if (e.layer == connected) {getData();}
    if (e.layer == onlydidok) {getData();}
    if (e.layer == onlyosm) {getData();}
    if (e.layer == badname) {getData();}
    if (e.layer == worst100) {getData();}
    if (e.layer == v1) {getData();}
    document.getElementById('map_footer_permalink').innerHTML = permaLink();
}

function didok_invalidate(id) {
    div_class = "mark_"+id;
    x = document.getElementById(div_class);
    x.innerHTML = "<button type=\"button\" disabled=\"disabled\">Mark Stop as invalid</button>";
    url="didokstops/edit/inexistentStop/" + id;
    $.get(url, function f(data) { x.innerHTML=data;});
    getData();
}

function didok_revalidate(id) {
    div_class = "mark_"+id;
    x = document.getElementById(div_class);
    x.innerHTML = "<button type=\"button\" disabled=\"disabled\">Mark Stop as valid</button>";
    url="didokstops/edit/existentStop/" + id;
    $.get(url, function f(data) { x.innerHTML=data;});
    getData();
}
