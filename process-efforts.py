#!/usr/bin/python3

# Copyright (c) 2024 Contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import glob
import argparse
import geopy.distance
import math
import json
import gpxpy
import os
import statistics

#these values are all exact according to NIST
KM_PER_METER = 1/1000
MILE_PER_METER = 1/1609.344

KPH_PER_MPS = 3600 * KM_PER_METER
MPH_PER_MPS = 3600 * MILE_PER_METER


NUMBER_EFFORTS=8


#it would be better to actually look at acceleration, that would be smarter
UNLIKELY_SPEED = 120/KPH_PER_MPS #120kph in m/s.  you can reach this speed but only in weird situations
UNLIKELY_DISTANCE_GPX_SPEED = UNLIKELY_SPEED * 3
UNLIKELY_DISTANCE_GPS_POINT = UNLIKELY_SPEED * 5

total_points = 0

def get_gpx_files(args):
	gpx_filters = args.gpx_filters if args.gpx_filters else ['*.gpx']
	gpx_files = []

	for filter in gpx_filters:
		gpx_files += glob.glob('{}/{}'.format(args.gpx_dir, filter))

	if not gpx_files:
		exit('error no gpx files found')

	return gpx_files

def convert_point_to_geopy(point):
	#drops the elevation
	return [point.latitude, point.longitude]

def get_gpx_speed(point):
	for extension in point.extensions:
		if extension.tag == '{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}TrackPointExtension':
			for entry in extension:
				if entry.tag == '{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}speed':
					return float(entry.text)
	return None

def calculate_distance(last_point, current_point):
	#greater_circle is much faster, and difference is very small compared to the accuracy of the gps receiver
	#distance here is geodesic, elevation is not included
	gps_distance = geopy.distance.great_circle(convert_point_to_geopy(last_point), convert_point_to_geopy(current_point)).m
	#gps_distance = math.sqrt(gps_distance**2 + (current_point.elevation - last_point.elevation)**2)
	
	time_change = (current_point.time - last_point.time).total_seconds()
	last_speed_from_gpx=get_gpx_speed(last_point)
	current_speed_from_gpx=get_gpx_speed(current_point)
	if last_speed_from_gpx is not None and current_speed_from_gpx is not None:
		speed_from_gpx=statistics.mean([last_speed_from_gpx, current_speed_from_gpx]) ###hmmmm, this is probably not the best way to do this
		if speed_from_gpx * time_change > UNLIKELY_DISTANCE_GPX_SPEED:
			print('warning: big distance between points', round(speed_from_gpx * time_change), 'm', round(time_change), 's (distance using gpx speeds).  skipping point.')
			return None
		return speed_from_gpx * time_change
	if gps_distance > UNLIKELY_DISTANCE_GPS_POINT:
		print('warning: big distance between points', round(gps_distance), 'm', round(time_change), 's (distance using gps points).  skipping point.')
		return None
	gps_speed = gps_distance / time_change if time_change!=0 else math.inf
	if gps_speed>UNLIKELY_SPEED:
		print('warning: unlikely speed found.  skipping point.', round(gps_speed * KPH_PER_MPS) if gps_speed != math.inf else 'infinite', 'kph')
		return None
	return gps_distance

def read_gpx(filename):
	try:
		return gpxpy.parse(open(filename, 'r'))
		#return [[[point for for point in segment.points] for segment in track.segments] for track in gpx.tracks]
	except gpxpy.gpx.GPXXMLSyntaxException:
		print('trouble reading file, skipping:', filename)
		return None

def accept_point(best_track_efforts, current_efforts, last_point, current_point):
	global total_points
	total_points += 1
	
	distance_change = calculate_distance(last_point, current_point)
	if distance_change is None: return
	time_change = (current_point.time - last_point.time).total_seconds()

	for goal_distance, (current_distance, current_time, point_list) in current_efforts['distances'].items():
		#add a point
		current_distance += distance_change
		current_time += time_change
		point_list.append((distance_change, time_change))
		while current_distance >= goal_distance:
			#check bests
			best_current = best_track_efforts['distances'][goal_distance]
			if best_current is None or current_time < best_current:
				best_track_efforts['distances'][goal_distance] = current_time

			#remove a point
			(removed_distance, removed_time) = point_list.pop(0)
			current_distance -= removed_distance
			current_time -= removed_time
			
		current_efforts['distances'][goal_distance] = (current_distance, current_time, point_list)






distance_list = [int(goal_distance) for goal_distance in [1e3, 2e3, 5e3, 10e3, 20e3, 50e3, 100e3, 160934, 200e3, 500e3]]

def setup_efforts():
	return {'distances': dict((goal_distance, (0, 0, [])) for goal_distance in distance_list)}

def setup_best_track_efforts():
	return {'distances': dict((goal_distance, None) for goal_distance in distance_list)}


best_efforts_file='best-efforts.json'

def parse_best_effort_current(best_effort_current):
	return [tuple(best_effort) for best_effort in best_effort_current]

def setup_best_efforts():
	if os.path.isfile(best_efforts_file):
		best_efforts = json.load(open(best_efforts_file, 'r'))
		best_efforts['distances'] = dict(
			(int(goal_distance), parse_best_effort_current(best_effort_current)) for (goal_distance, best_effort_current) in best_efforts['distances'].items()
		)
		return best_efforts
	else:
		return {'distances': dict((goal_distance, []) for goal_distance in distance_list)}

def save_best_efforts(best_efforts):
	with open(best_efforts_file, 'w') as file:
		json.dump(best_efforts, file, indent='\t')







#@profile
def accept_points(segments):
	current_efforts = setup_efforts()
	best_track_efforts = setup_best_track_efforts()
	#tracks are treated as separate files
	#revisit this:  we ignore the time/distance between segments, but keep the current_efforts open.  this may not be very fair
	for segment in segments:
		last_point = None
		for current_point in segment.points:
			if last_point is not None:
				accept_point(best_track_efforts, current_efforts, last_point, current_point)
			last_point = current_point
	return best_track_efforts


def read_gpx_files(args, best_efforts):
	for filename in get_gpx_files(args):
		if not args.quiet:
			print('reading {}'.format(filename))

		gpx = read_gpx(filename)
		if gpx is None: continue
		for track in gpx.tracks:
			key='{name} ({filename})'.format(name=track.name, filename=filename)
			best_track_efforts = accept_points(track.segments)
			for (goal_distance, best_track_effort) in best_track_efforts['distances'].items():
				if best_track_effort is None: continue
				best_current = [effort for effort in best_efforts['distances'][goal_distance] if effort[1] != key]
				best_current.append((best_track_effort, key))
				best_efforts['distances'][goal_distance] = sorted(best_current)[:NUMBER_EFFORTS]


def format_display(value, unit, digits):
	return '{value:.{digits}f} {unit}'.format(value=value, digits=digits, unit=unit)
	
def display_speed(value, imperial, digits):
	value *= MPH_PER_MPS if imperial else KPH_PER_MPS
	return format_display(value, 'mph' if imperial else 'kph', digits)

def display_distance(value, imperial, digits):
	value *= MILE_PER_METER if imperial else KM_PER_METER
	return format_display(value, 'miles' if imperial else 'km', digits)

def display(best_efforts, imperial):
	for (distance, best_current) in best_efforts['distances'].items():
		ratio = MILE_PER_METER if imperial else KM_PER_METER
		print(display_distance(distance, imperial, 1 if imperial else 0))
		for (best_time, key) in best_current:
			print('    ', display_speed(distance / best_time, imperial, 1), key)
		print()


#@profile
def main(args):
	best_efforts = setup_best_efforts()

	if not args.display_only:
		read_gpx_files(args, best_efforts)
		save_best_efforts(best_efforts)
		print('loaded {} trackpoints'.format(total_points))

	display(best_efforts, args.imperial)
	

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description = 'generate an effort json from gpx files', epilog = 'report issues to github.com/arichnad/process-efforts')

	parser.add_argument('--gpx-dir', metavar = 'DIR', default = 'gpx', help = 'directory containing the gpx files (default: gpx)')
	parser.add_argument('--gpx-filters', metavar = 'FILTERS', action = 'append', help = 'glob filter(s) for the gpx files (default: *.gpx)')
	parser.add_argument('--display-only', default = False, action = 'store_true', help = 'only display the json database: do not add files')
	parser.add_argument('--imperial', default = False, action = 'store_true', help = 'display imperial distances')
	parser.add_argument('--quiet', default = False, action = 'store_true', help = 'quiet output, still displays warnings')

	args = parser.parse_args()

	main(args)

