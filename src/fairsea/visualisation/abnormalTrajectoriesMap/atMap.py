
import folium
import branca
import matplotlib
import folium.plugins

import numpy as np
import pandas as pd
import geopandas as gpd

from jinja2 import Template
from pathlib import Path
from shapely.geometry import box
from branca.colormap import LinearColormap
from branca.element import Element, Template, MacroElement, CssLink

DATA_PATH = Path('../../data/')

# Sea zone data.
# https://www.marineregions.org/eezsearch.php
# https://en.wikipedia.org/wiki/Exclusive_economic_zone
EEZ_IW_PATH = DATA_PATH / 'eco_zones' / 'eez_internal_waters_v3.gpkg'
EEZ_12NM_PATH = DATA_PATH / 'eco_zones' / 'eez_12nm_v3.gpkg'
EEZ_24NM_PATH = DATA_PATH / 'eco_zones' / 'eez_24nm_v3.gpkg'
EEZ_200NM_PATH = DATA_PATH / 'eco_zones' / 'eez_v11.gpkg'


# Swedish West Coast (lon_min, lat_min, lon_max, lat_max)
BOUNDING_BOX = (9.0, 56.0, 13.5, 60.0)

class ATMap:

	"""

		Class for creating a web map with subsets of trajectories.
		See classmethod init_map for how to initialize.

	"""

	def __init__(self, _map, df_territory, df_zone, territories, zones):

		self._map = _map
		self.init_layer_control = False

		self.territories = territories
		self.zones = zones
		self.df_zone = df_zone
		self.df_territory = df_territory

		self.territory_cmap = {
			'Sweden': '#ffffb2',
			'Norway': '#2171b5',
			'Denmark': '#e31a1c',
            "Finland": "#813f05",
            "Estonia": "#800012",
            "Latvia": "#800012",
            "Lithuania": "#800012",
            "Russia": "#800012",
            "Alaska": "#800012",
		}

		self.zone_cmap = {
			'Internal Waters': '#fff7f3',
			'Territorial Sea (12NM)': '#fcc5c0',
			'Contiguous Sea (24NM)': '#f768a1',
			'EEZ (200NM)': '#ae017e',
		}

		dummy_layer = folium.FeatureGroup(name='None', overlay=False, control=True, show=True)
		dummy_layer.add_to(self._map)
		self.base_layers = [dummy_layer]

		dummy_layer = folium.FeatureGroup(name='None', overlay=False, control=True, show=True)
		dummy_layer.add_to(self._map)
		self.trajectoy_layers = [dummy_layer]

		# Global JS variables and methods.
		js_code = """

			var global_info_cleared = true;
			var global_info = {};

			var highlight_voy_style = {
				opacity: 1.0,
				fillOpacity: 0.5,
			};

			var hide_voy_style = {
				opacity: 0.2,
				fillOpacity: 0.1,
			};

			var update_info_legend = function (voyid, imo, voystarttime, voyendtime, voytime) {
			
				var elem = document.getElementById('voyid');
				elem.innerHTML  = voyid;

				var elem = document.getElementById('imolink');
				//elem.href = 'https://www.vesselfinder.com/vessels/details/' + imo;
				elem.href = 'https://maritime.ihs.com/Ships/Details/Index/' + imo;
				elem.innerHTML  = imo;

				var elem = document.getElementById('voystarttime');
				elem.innerHTML  = voystarttime;

				var elem = document.getElementById('voyendtime');
				elem.innerHTML  = voyendtime;

				var elem = document.getElementById('voytime');
				elem.innerHTML  = voytime;
			};

		"""

		global_js = Element(template=js_code)
		self._map.get_root().script.add_child(global_js)


	def add_legend_events(self, feature_group, legend_elem):

		"""

			Adding legend handling through JS.
		
		"""

		js_code = """
			$(document).ready(function() {

				{legend_elem}.style.display = 'none';

				{map}.on('overlayadd', function(e) {
					if (e.layer == {feature_group}) {
						{legend_elem}.style.display = 'block';
					}
				});

				{map}.on('overlayremove', function(e) {
					if (e.layer == {feature_group}) {
						{legend_elem}.style.display = 'none';
					}
				});

			});
		"""

		js_code = js_code.replace('{map}', self._map.get_name())
		js_code = js_code.replace('{legend_elem}', legend_elem.get_name())
		js_code = js_code.replace('{feature_group}', feature_group.get_name())
		legend_js = Element(template=js_code)

		self._map.get_root().script.add_child(legend_js)

	def add_extra_js(self, feature_group):

		"""

			Adding extra JS for map interactivity.
		
		"""
		
		js_code = """

			$(document).ready(function() {

				function mapClick(e) {

					// Empty info legend.
					if ({fg}['selected'] == true) {

						global_info[{fg}._leaflet_id.toString()] = {
							'voyid': '',
							'imo': '',
							'voystarttime': '',
							'voyendtime': '',
							'voytime': ''
						};
						
						update_info_legend(
							'',
							'',
							'',
							'',
							''
						);

						for (var layer_id in {fg}._layers) {
					
							{fg}._layers[layer_id].setStyle(highlight_voy_style);

							if ({fg}._layers[layer_id].options.color) {
								if ('metadata' in {fg}._layers[layer_id]) {
									{fg}._layers[layer_id].setStyle({
										color: {fg}._layers[layer_id].metadata.color,
										fillColor: {fg}._layers[layer_id].metadata.fillColor
									});
								}
							} else {
								for (var sub_layer_id in {fg}._layers[layer_id]._layers) {
									if ('metadata' in {fg}._layers[layer_id]._layers[sub_layer_id]) {
										{fg}._layers[layer_id]._layers[sub_layer_id].setStyle({
											color: {fg}._layers[layer_id]._layers[sub_layer_id].metadata.color,
											fillColor: {fg}._layers[layer_id]._layers[sub_layer_id].metadata.fillColor
										});
									}
								}
							}
						}

					}

					
				}

				{map}.on('click', mapClick);

			});
		"""

		js_code = js_code.replace('{map}', self._map.get_name())
		js_code = js_code.replace('{fg}', feature_group.get_name())

		extra_js = Element(template=js_code)
		self._map.get_root().script.add_child(extra_js)

	def add_layer_events(self, feature_group, colorbar_elem):

		"""

			Adding JS for layer interactivity.
		
		"""

		js_code = """

			$(document).ready(function() {

				{colorbar_elem}.svg[0][0].style.display = 'none';

				{map}.on('overlayadd', function(e) {
					
					if (e.layer == {feature_group}) {

						{feature_group}['selected'] = true;

						if ({feature_group}._leaflet_id.toString() in global_info) {
							update_info_legend(
								global_info[{feature_group}._leaflet_id.toString()]['voyid'],
								global_info[{feature_group}._leaflet_id.toString()]['imo'],
								global_info[{feature_group}._leaflet_id.toString()]['voystarttime'],
								global_info[{feature_group}._leaflet_id.toString()]['voyendtime'],
								global_info[{feature_group}._leaflet_id.toString()]['voytime']
							);
						}
						else {
							update_info_legend(
								'',
								'',
								'',
								'',
								''
							);
						}

						{colorbar_elem}.svg[0][0].style.display = 'block';
						
					}

				});

				{map}.on('overlayremove', function(e) {
					if (e.layer == {feature_group}) {

						{feature_group}['selected'] = false;
						{colorbar_elem}.svg[0][0].style.display = 'none';	

					}
				});

			});
		"""

		js_code = js_code.replace('{map}', self._map.get_name())
		js_code = js_code.replace('{colorbar_elem}', colorbar_elem.get_name())
		js_code = js_code.replace('{feature_group}', feature_group.get_name())
		colorbar_js = Element(template=js_code)

		self._map.get_root().script.add_child(colorbar_js)

	def add_info_legend(self):

		"""

			Adding info legend elements to map.
		
		"""

		html_code = '<div id="infolegend" class="maplegend">'
		html_code += '<div class="legend-title">' + 'INFO' + '</div>'
		html_code += '<div class="legend-scale">'
		html_code += '<div>' + 'Voyage ID: ' + '<div id="voyid"></div>' + '</div>'
		html_code += '<div>' + 'IMO: ' + '<a id="imolink" target="_blank"></a>' + '</div>'
		html_code += '<div>' + 'Start Time: ' + '<div id="voystarttime"></div>' + '</div>'
		html_code += '<div>' + 'End Time: ' + '<div id="voyendtime"></div>' + '</div>'
		html_code += '<div>' + 'Voyage Time: ' + '<div id="voytime"></div>' + '</div>'
		html_code += '</div>'
		html_code += '</div>'

		legend_elem = Element(html_code)

		self._map.get_root().html.add_child(legend_elem)

	def init_territories(self):

		"""
	
			Initializing territories on the map.

		"""

		def style_func(x):

			return {
				'stroke': False,
				'fillColor': self.territory_cmap[x['properties']['TERRITORY1']],
				'fillOpacity': 0.3
			}

		feature_group = folium.FeatureGroup(name='Territory', overlay=False, control=True, show=False)
		feature_group.add_to(self._map)
		feature_group.add_child(folium.GeoJson(
			self.df_territory.to_json(),
			style_function=style_func
		))

		# Add Legend
		html_code = '<div id="{{this.get_name()}}" class="maplegend">'
		html_code += '<div class="legend-title">' + 'Territory' + '</div>'
		html_code += '<div class="legend-scale">'
		html_code += '<ul class="legend-labels">'

		for key in self.territory_cmap:
			html_code += '<li><span style="background:' + self.territory_cmap[key] + '; opacity:0.3;"></span>' + key + '</li>'

		html_code += '</ul>'
		html_code += '</div>'
		html_code += '</div>'

		legend_elem = Element(html_code)

		self._map.get_root().html.add_child(legend_elem)
		self.add_legend_events(feature_group, legend_elem)

		return feature_group


	def init_zones(self, layer_name='Zone'):

		"""
	
			Initializing zones on the map.

		"""

		def style_func(x):
				
			return {
				'stroke': False,
				'fillColor': self.zone_cmap[x['properties']['EEZ_Type']],
				'fillOpacity': 0.3,
			}

		feature_group = folium.FeatureGroup(name=layer_name, overlay=False, control=True, show=False)
		feature_group.add_to(self._map)
		feature_group.add_child(folium.GeoJson(
			self.df_zone.to_json(),
			style_function=style_func
		))

		# Add Legend
		html_code = '<div id="{{this.get_name()}}" class="maplegend">'
		html_code += '<div class="legend-title">' + layer_name + '</div>'
		html_code += '<div class="legend-scale">'
		html_code += '<ul class="legend-labels">'

		for key in self.zone_cmap:
			html_code += '<li><span style="background:' + self.zone_cmap[key] + '; opacity: 0.3;"></span>' + key + '</li>'

		html_code += '</ul>'
		html_code += '</div>'
		html_code += '</div>'

		legend_elem = Element(html_code)

		self._map.get_root().html.add_child(legend_elem)
		self.add_legend_events(feature_group, legend_elem)

		return feature_group

	def add_voyages(self, name, df, color_col, cmap_name='Spectral_r', c_min='min', c_max='max', render_with_gaps=True):

		"""

			Adding voyages to the map.

		"""

		feature_group = folium.FeatureGroup(name=name, overlay=False, control=True, show=False)
		feature_group.add_to(self._map)
		self._map.keep_in_front(feature_group)
		self.trajectoy_layers.append(feature_group)

		if c_min == 'min':
			min_val = df[color_col].min()
		else:
			min_val = c_min

		if c_max == 'max':
			max_val = df[color_col].max()
		else:
			max_val = c_max

		# Define cmap.
		n_colors = 30
		step_size = 1.0/(n_colors - 1)
		cmap = matplotlib.colormaps[cmap_name]
		colors = [cmap(i) for i in np.arange(0.0, 1.0 + (step_size - np.finfo(float).eps), step_size)]
		colorbar = branca.colormap.LinearColormap(
			colors,
			vmin=min_val,
			vmax=max_val,
			caption=color_col
		)
		colorbar = colorbar.to_step(20) # Modify to stepped colormap to generate less segments.
		colorbar.add_to(self._map)

		self.add_layer_events(feature_group, colorbar)
		self.add_extra_js(feature_group)
		
		def voyage_style_func(feature):

			return {
				'color': feature['properties']['color'],
				'opacity': 1.0,
				'weight': 3.0,
				'dashArray': '2 8' if feature['properties']['time_gap'] == 1.0 else None,
			}

		for voyage_id in df.groupby('voyage_id').size().sort_values(ascending=False).index:

			df_voy = df[df['voyage_id'] == voyage_id].reset_index(drop=True)

			ship_imo = df_voy['IMO'].values[0]
			voy_start_time = df_voy['Timestamp_datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').values[0]
			voy_end_time = df_voy['Timestamp_datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').values[-1]
			voy_time = (df_voy['Timestamp_datetime'].iloc[-1] - df_voy['Timestamp_datetime'].iloc[0])
			voy_time = str(voy_time).split('.')[0]

			if render_with_gaps:

				# Group voyages into different segments that can be rendered at same time.
				df_voy['color'] = df_voy.apply(lambda x: colorbar(x[color_col]), axis=1)
				voy_groups = df_voy.groupby(['timegap', 'color']).apply(lambda x: {
					'sort_val': x[color_col].min(),
					'indices': x.index.tolist(),
				}).to_dict()

				# Sort dictionary to put highest values on top.
				voy_groups = dict(sorted(voy_groups.items(), key=lambda x: x[1]['sort_val']))

				# Create Feature Collection.
				voy_geojson = {
					'type': 'FeatureCollection',
					'features': []
				}

				# For each voyage group, create a MultiLineString for all segments.
				for key in voy_groups:

					multi_line_string = []
					line_string = []
					prev_idx = 0
					for idx in voy_groups[key]['indices']:

						if idx - prev_idx > 1:
							multi_line_string.append(line_string)
							line_string = [[df_voy['Longitude'].iloc[idx-1], df_voy['Latitude'].iloc[idx-1]]]

						line_string.append([df_voy['Longitude'].iloc[idx], df_voy['Latitude'].iloc[idx]])
						prev_idx = idx

					multi_line_string.append(line_string)

					voy_geojson['features'].append({
						'type': 'Feature',
						'properties': {
							'color': key[1],
							'time_gap': key[0],
						},
						'geometry': {
							'type': 'MultiLineString',
							'coordinates': multi_line_string
						},									
					})

				elem_line = folium.GeoJson(
					data=voy_geojson,
					style_function=voyage_style_func
				)
				feature_group.add_child(elem_line)
				
			else:
				elem_line = folium.ColorLine(
					positions=df_voy[['Latitude', 'Longitude']].values,
					colors=df_voy[color_col].values[1:],
					colormap=colorbar,
					weight=3.0,
					name=voyage_id
				)
				feature_group.add_child(elem_line)
			
			# Start
			elem_start = folium.RegularPolygonMarker(
				location=df_voy[['Latitude', 'Longitude']].values[0],
				fill=True,
				gradient=False,
				fill_color='#%02X%02X%02X%02X' % cmap((df_voy[color_col].values[0] - min_val) / (max_val - min_val), bytes=True),
				color='#%02X%02X%02X%02X' % cmap((df_voy[color_col].values[0] - min_val) / (max_val - min_val), bytes=True),
				fill_opacity=0.5,
				number_of_sides=3,
				radius=10,
				weight=3
			)
			feature_group.add_child(elem_start)
			
			# Stop
			elem_stop_1 = folium.RegularPolygonMarker(
            # folium.CircleMarker(
				location=df_voy[['Latitude', 'Longitude']].values[-1],
				fill=True,
				fill_color='#%02X%02X%02X%02X' % cmap((df_voy[color_col].values[-1] - min_val) / (max_val - min_val), bytes=True),
				color='#%02X%02X%02X%02X' % cmap((df_voy[color_col].values[-1] - min_val) / (max_val - min_val), bytes=True),
				fill_opacity=0.5,
				number_of_sides=4,
				radius=10,
				weight=3.,
                rotation=45,
			)
			feature_group.add_child(elem_stop_1)

			# elem_stop_2 = folium.CircleMarker(
			# 	location=df_voy[['Latitude', 'Longitude']].values[-1],
			# 	fill=False,
			# 	fill_color='#%02X%02X%02X%02X' % cmap((df_voy[color_col].values[-1] - min_val) / (max_val - min_val), bytes=True),
			# 	color='#%02X%02X%02X%02X' % cmap((df_voy[color_col].values[-1] - min_val) / (max_val - min_val), bytes=True),
			# 	radius=4,
			# 	weight=2,
			# )
			# feature_group.add_child(elem_stop_2)

			# JS code for voyage interactivity.
			js_code = """

				$(document).ready(function() {
					
					function trajectoryClick(e) {
						
						//console.log('TRAJECTORY');
						//console.log(e);

						L.DomEvent.stopPropagation(e);

						var fg_ids = [
							{line}._leaflet_id.toString(),
							{start}._leaflet_id.toString(),
							{stop_1}._leaflet_id.toString()//,
						//	{stop_2}._leaflet_id.toString()
						];

						//console.log(fg_ids);

						// Update selected voyage info.
						var promise = new Promise((resolve, reject) => {
							global_info[{fg}._leaflet_id.toString()] = {
								'voyid': '{voy_id}',
								'imo': '{imo}',
								'voystarttime': '{voy_start_time}',
								'voyendtime': '{voy_end_time}',
								'voytime': '{voy_time}'
							};
							resolve();
						});
						
						promise.then(() => {
							update_info_legend(
								'{voy_id}',
								'{imo}',
								'{voy_start_time}',
								'{voy_end_time}',
								'{voy_time}'
							);
						});
						

						for (var layer_id in {fg}._layers) {
							if (!fg_ids.includes(layer_id)) {
							
								{fg}._layers[layer_id].setStyle(hide_voy_style);
								//console.log({fg}._layers[layer_id]);

								if ({fg}._layers[layer_id].options.color) {
									if (!('metadata' in {fg}._layers[layer_id])) {
										{fg}._layers[layer_id]['metadata'] = {
											'color': {fg}._layers[layer_id].options.color,
											'fillColor': {fg}._layers[layer_id].options.fillColor,
										}
									}
									{fg}._layers[layer_id].setStyle({color: '#666666', fillColor: '#666666'});
								} else {
									for (var sub_layer_id in {fg}._layers[layer_id]._layers) {
										if (!('metadata' in {fg}._layers[layer_id]._layers[sub_layer_id])) {
											{fg}._layers[layer_id]._layers[sub_layer_id]['metadata'] = {
												'color': {fg}._layers[layer_id]._layers[sub_layer_id].options.color,
												'fillColor': {fg}._layers[layer_id]._layers[sub_layer_id].options.fillColor,
											}
										}
										{fg}._layers[layer_id]._layers[sub_layer_id].setStyle({color: '#666666'});
									}
								}
						

							} else {
							
								{fg}._layers[layer_id].setStyle(highlight_voy_style);

								if ({fg}._layers[layer_id].options.color) {
									if ('metadata' in {fg}._layers[layer_id]) {
										{fg}._layers[layer_id].setStyle({
											color: {fg}._layers[layer_id].metadata.color,
											fillColor: {fg}._layers[layer_id].metadata.fillColor
										});
									}
								} else {
									for (var sub_layer_id in {fg}._layers[layer_id]._layers) {
										if ('metadata' in {fg}._layers[layer_id]._layers[sub_layer_id]) {
											{fg}._layers[layer_id]._layers[sub_layer_id].setStyle({
												color: {fg}._layers[layer_id]._layers[sub_layer_id].metadata.color,
												fillColor: {fg}._layers[layer_id]._layers[sub_layer_id].metadata.fillColor
											});
										}
									}
								}

								{fg}._layers[layer_id].bringToFront();
							}
						}
					}

					{line}.on('click', trajectoryClick);
					{start}.on('click', trajectoryClick);
					{stop_1}.on('click', trajectoryClick);
					//{stop_2}.on('click', trajectoryClick);

				});
			
			"""

			js_code = js_code.replace('{map}', self._map.get_name())
			js_code = js_code.replace('{fg}', feature_group.get_name())
			js_code = js_code.replace('{voy_id}', voyage_id)
			js_code = js_code.replace('{imo}', ship_imo)
			js_code = js_code.replace('{voy_start_time}', voy_start_time)
			js_code = js_code.replace('{voy_end_time}', voy_end_time)
			js_code = js_code.replace('{voy_time}', voy_time)
			js_code = js_code.replace('{line}', elem_line.get_name())
			js_code = js_code.replace('{start}', elem_start.get_name())
			js_code = js_code.replace('{stop_1}', elem_stop_1.get_name())
			# js_code = js_code.replace('{stop_2}', elem_stop_2.get_name())
			elem_js = Element(template=js_code)
			self._map.get_root().script.add_child(elem_js)

	def init_utils(self):

		"""

			Additional.
		
		"""

		self.add_info_legend()

		# Initialize territories.
		if self.territories:
			self.base_layers.append(self.init_territories())
			self.territories = False

		# Initialize zones.
		if self.zones:
			self.base_layers.append(self.init_zones())
			self.zones = False

		# Group layers and add control to map.
		if not self.init_layer_control:

			folium.plugins.GroupedLayerControl(
				groups={
					'Base Layers': self.base_layers,
					'Trajectories': self.trajectoy_layers
				},
				position='topleft'
			).add_to(self._map)

			# Inject CSS
			with open(Path(__file__).parent.resolve() / 'style.css', 'r') as f:
				self._map.get_root().header.add_child(Element('<style type="text/css">' + f.read() + '</style>'))

			self.init_layer_control = True
			

	def render(self):

		"""
		
			Returns map for rendering in e.g. a notebook.

		"""

		self.init_utils()

		return self._map

	def save(self, output_path=None):

		"""
		
			Saves map as a HTML file.

		"""

		if output_path == None:
			output_path = Path(__file__).parent.resolve() / 'main.html'

		self.render().save(output_path)


	@classmethod
	def init_map(cls, territories=True, zones=True):

		"""
		
			This is a class method that initializes a map object using the Folium library.
			It adds a base map, a bounding box showing a selected sea area, and processes zone data.
			It then clips the zone data to the bounding box, removes parts of the EEZ 200 NM that includes other zones,
			and creates a GeoDataFrame for the zones and territories. Finally, it returns an instance of the class with the map,
			territories, and zones.

		"""

		# Create map object.
		_map = folium.Map(
			location=[
				BOUNDING_BOX[1] + ((BOUNDING_BOX[3] - BOUNDING_BOX[1]) / 2.0),
				BOUNDING_BOX[0] + ((BOUNDING_BOX[2] - BOUNDING_BOX[0]) / 2.0),
			],
			zoom_start=8,
			tiles=None
		)

		# Add base map.
		base_map = folium.FeatureGroup(name='Basemap', overlay=True, control=False, show=True)
		folium.TileLayer(tiles='CartoDB dark_matter').add_to(base_map)
		#folium.TileLayer(tiles='CartoDB').add_to(base_map)
		base_map.add_to(_map)

		# Add bounding box showing selected sea area.
		folium.Rectangle(
			[[BOUNDING_BOX[1], BOUNDING_BOX[0]], [BOUNDING_BOX[3], BOUNDING_BOX[2]]],
			color='#FFFFFF',
			dashArray='20 10',
			opacity=0.2
		).add_to(_map)

		# Read and process zone data.
		df_zone_internal = gpd.read_file(EEZ_IW_PATH, bbox=BOUNDING_BOX)
		df_zone_12nm = gpd.read_file(EEZ_12NM_PATH, bbox=BOUNDING_BOX)
		df_zone_24nm = gpd.read_file(EEZ_24NM_PATH, bbox=BOUNDING_BOX)
		df_zone_200nm = gpd.read_file(EEZ_200NM_PATH, bbox=BOUNDING_BOX)

		# Clip to bounding box.
		bbox = box(*BOUNDING_BOX)
		df_zone_internal = gpd.clip(df_zone_internal, mask=bbox)
		df_zone_12nm = gpd.clip(df_zone_12nm, mask=bbox)
		df_zone_24nm = gpd.clip(df_zone_24nm, mask=bbox)
		df_zone_200nm = gpd.clip(df_zone_200nm, mask=bbox)

		# Remove parts of EEZ 200 NM that includes other zones.
		df_zone_200nm = gpd.overlay(df_zone_200nm, df_zone_internal, how='difference', keep_geom_type=False)
		df_zone_200nm = gpd.overlay(df_zone_200nm, df_zone_12nm, how='difference', keep_geom_type=False)
		df_zone_200nm = gpd.overlay(df_zone_200nm, df_zone_24nm, how='difference', keep_geom_type=False)
		df_zone_200nm = df_zone_200nm.explode(ignore_index=True)
		df_zone_200nm = df_zone_200nm[df_zone_200nm.to_crs('3857').area > 1.0]

		df_zone = gpd.GeoDataFrame(
			data={
				'EEZ_Type': [
					'EEZ (200NM)',
					'Contiguous Sea (24NM)',
					'Territorial Sea (12NM)',
					'Internal Waters',  
				],
				'geometry': [
					df_zone_200nm['geometry'].unary_union,
					df_zone_24nm['geometry'].unary_union,
					df_zone_12nm['geometry'].unary_union,
					df_zone_internal['geometry'].unary_union
				]
			},
			crs='EPSG:4326'
		)

		df_territory = pd.concat((df_zone_internal, df_zone_12nm))[['TERRITORY1', 'geometry']]

		return cls(
			_map,
			df_territory,
			df_zone,
			territories=territories,
			zones=zones
		)
