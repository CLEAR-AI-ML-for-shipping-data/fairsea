leafletPolycolor(L);

var map = L.map('map', {preferCanvas: true}).setView([51.505, -0.09], 13);

const dataInput = document.getElementById("observationsInput");
dataInput.onchange = getFile;

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

const aisInput = document.getElementById("aisInput");
aisInput.onchange = () => {
    console.log("Loading ais file");
    const csv = aisInput.files[0];
    let dataPoints = [];
    let i = 0;

    var heatmap = L.webGLHeatmap({size: 1000, opacity: 0.8});
    map.addLayer(heatmap);
    Papa.parse(csv, {
        header: true,
        step: function(row) {
            if (i % 10 == 0) {
                //console.log(i/30553435);
                console.log(row.meta.cursor / csv.size * 100);
                //dataPoints.push([parseFloat(row.data.Latitude), parseFloat(row.data.Longitude), 0.1]);
                //heatmap.setData(dataPoints);
                heatmap.addPoint([parseFloat(row.data.Latitude), parseFloat(row.data.Longitude)]);
                //heatmap.addDataPoint(parseFloat(row.data.Latitude), parseFloat(row.data.Longitude, 1));
                //heatmap.gl.update();
                //heatmap.gl.display();
            }
            i++;
            //console.log("Row:", row.data);
        },
        complete: function() {
            //var dataPoints = [[44.6674, -63.5703], [44.6826, -63.7552], [44.6325, -63.5852], [44.6467, -63.4696], [44.6804, -63.487], [44.6622, -63.5364], [44.603, - 63.743]];
            console.log("All loaded")
            //custom size for this example

        }
    });
}

function getFile () {
    const file = dataInput.files[0];
    new Response(file).json().then(json => {
      console.log(json);
      drawObservations(json);
    }, err => {
      console.error(`${file.name} is not a valid JSON file!`);
    })
}

function drawObservations(jsonData) {
    const lut = new Lut("cooltowarm");
    lut.setMin(- 60 * 60000); // 1 hour before
    lut.setMax(60 * 60000);   // 1 hour after
    const markerGroup = new L.FeatureGroup();
    for (let observation of jsonData) {
        const marker = L.marker([observation.Latitude, observation.Longitude]);
        marker.on('click', e=>{
            console.log(e.latlng);

            map.eachLayer(layer=>{
                if (layer instanceof L.Polyline){
                    map.removeLayer(layer);
                }
            });

            for (let i in observation.closestShipTrajs) {
                const shipTraj = observation.closestShipTrajs[i];
                const latlngs = shipTraj.map(p=>[p.Latitude, p.Longitude]) ;
                //const trajLine = L.polyline(latlngs, {color: 'red'}).addTo(map);
                /*
                trajLine.on('mouseover', ()=>{
                    trajLine.setText(`IMO: ${observation.closestShips[i]}`, {offset: 18, attributes: {'font-weight': 'bold', 'font-size': '18'}});
                    //trajLine.setText('  ►  ', {repeat: true, fill: 'red'});
                });
                trajLine.on('mouseout', ()=>{
                    trajLine.setText(null);
                });
                */
                const colors = shipTraj.map(p=>"#"+lut.getColor(p.Timestamp_datetime - observation.datetime * 1000).getHexString());
                const trajLine = L.polycolor(latlngs, {colors: colors, weight: 5}).addTo(map);
            }
        })

        markerGroup.addLayer(marker);
    }
    markerGroup.addTo(map);
    map.fitBounds(markerGroup.getBounds());
}