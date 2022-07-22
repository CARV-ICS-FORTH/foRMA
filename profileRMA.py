#!/usr/bin/python3

import getopt 
import sys 
import os
import re
import fnmatch
import numpy as np
import collections
import subprocess

import matplotlib.pyplot as plt


def parse_trace(rma_tracked_calls):

	global rma_allranks
	global windows_per_node
	global total_exec_times
	global start_wall_times
	global window_union

	global statistic_labels

	#print('Number of arguments: {}'.format(len(argv)))
	#print('Argument(s) passed: {}'.format(str(argv)))

	#rma_all_calls = ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']


	# rma_tracked_calls =  ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']
	#rma_tracked_calls =  rma_all_calls

	rma_set = frozenset(rma_tracked_calls)

	rma_occurences = { i : 0 for i in rma_tracked_calls }

	statistic_labels = ['Min', 'Max', 'Avg', 'Std Dev', 'Median', '90%ile', '95%ile', '99%ile']

	ordered_files = sorted(os.listdir(format(str(dirname))))
	current_call = ''
	start_wall_time = 0
	end_wall_time = 0
	start_cpu_time = 0
	end_cpu_time = 0
	current_window = 0
	current_bytes = 0
	current_size = 0
	current_type = ''
	current_target = 0
	current_op = ''
	current_duration_wall = 0
	current_duration_cpu = 0

	calls_per_node = []
	wincount_per_node = []
	windows_per_node = []
	rma_allranks = []

	start_times = []
	end_times = []
	total_exec_times = []
	start_wall_times = []

	#for filename in os.listdir(format(str(dirname))):
	for filename in ordered_files:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			#print('Filename is: '+filename)
			filepath = format(str(dirname))+'/'+format(str(filename))
			#print('File path is: '+filepath)
			os.system('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > d2atemp.out')

			call_count = 0
			win_count = 0
			windows = set() 
		
			rma_node_timeseries = []

			monitoring_call = 0

			i = 0 # read second line

			file = open('d2atemp.out', 'r')
			#next(file)
			line = next(file)
			line = line.strip()
			linesplit = re.split(' |, ', line)

			start_time = float(linesplit[6]) * 1000000 # convert to usec right away

			start_times.append(start_time)

			start_wall_times.append(float(linesplit[4])*1000000)

			#print(start_times)
			file.seek(0)

			# from https://www.geeksforgeeks.org/python-how-to-search-for-a-string-in-text-files/
			for line in file:
				line = line.strip()
				linesplit = re.split(' |, ', line)

				if monitoring_call == 0:
					if linesplit[0] in rma_set and linesplit[1] == 'entering':
						monitoring_call = 1
						current_call = linesplit[0]
						rma_occurences[current_call] += 1 
						

				elif monitoring_call == 1:
					if linesplit[1] == 'returning':
						monitoring_call = 0
						

			
			end_time = float(linesplit[6]) * 1000000 # convert to usec right away
			end_times.append(end_time)
			#print(end_times)

			exec_time = end_time - start_time
			total_exec_times.append(exec_time)
			#print(total_exec_times)
			
			#file.seek(0)
			#bdata = file.read()
			#print('Binary sentence', bdata)

			calls_per_node.append(call_count)
			windows_per_node.append(windows)
			#wincount_per_node.append(win_count)
			rma_allranks.append(rma_node_timeseries)
			file.close()
			os.system('rm d2atemp.out')
	#		print(rma_node_timeseries)

	window_union = set().union(*windows_per_node)

	#filter_calls_per_rank(rma_allranks, windows_per_node, total_exec_times)
	#fence_summary(rma_allranks, windows_per_node)

	return rma_occurences


def tracked_calls_get():

	rma_tracked_calls = []

	with open('rmacalls.conf') as callfile:
		for line in callfile:
			if line[0] != '#':
				cleanline = line.strip('\n')
				rma_tracked_calls.append(cleanline)
	return rma_tracked_calls


def read_footers(dirname, timestamp):

	cc = {} # for Call Count

	os.system('rm validate.temp')

	#subprocess.call('./footer_reader.sh rmacalls.conf ' + dirname + ' ' + timestamp + ' validate.temp', shell=True)
	os.system('./footer_reader.sh rmacalls.conf ' + dirname + ' ' + timestamp + ' validate.temp')
	print("Counting calls.")
	with open('validate.temp', 'r') as countfile:
		for line in countfile:
			cleanline = line.strip("\n")
			(k, v) = cleanline.split(":")
			cc[k] = int(v)
	return cc


def validate_count(call_count, rma_occurences):

	if len(call_count) != len(rma_occurences):
		print ('Exception: discrepancy in tracked calls list!')
		sys.exit()
	for (k,v), (kk, vv) in zip(call_count.items(), rma_occurences.items()):
		if k.strip(' ') != kk.strip(' '):
			print(f'Exception: discrepancy of tracked RMA calls! {k} vs {kk}')
			sys.exit()
		if v != vv:
			print(f'Exception: discrepancy of occurence count for RMA call {kk}!')
			sys.exit()
	print('RMA occurrence count validation successful.')
	os.system('rm validate.temp')


def main():

	global dirname, timestamp

	action = 'r'
	cmdlnaction = False


	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]

	# from https://www.datacamp.com/community/tutorials/argument-parsing-in-python

	try: 
		if len(argv) < 4 or len(argv) > 6:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ]')
			sys.exit(2)
		else:
			opts, args = getopt.getopt(argv, 'd:t:a:')
			for o, a in opts:
				if o == "-d": 
					dirname = a
				elif o == "-t":
					timestamp = a
				elif o == "-a":
					action = a
					cmdlnaction = True
				else: 
					assert False, "No such command-line option!"
					sys.exit(2)
			#print('Directory name is : ' + format(str(dirname)))
			#print('Timestamp is : ' + format(str(timestamp)))
			
	except getopt.GetoptError:
		print ('Exception: wrong usage. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ] instead')
		sys.exit()


	rma_tracked_calls = tracked_calls_get()

	rma_occurences = parse_trace(rma_tracked_calls)

	cc = read_footers(dirname, timestamp)
	validate_count(cc, rma_occurences)



"""

	while action != 'q':
		if (not cmdlnaction):
			if action == 'r':
				print('--------------------------------------------\n- Options -\n' + 
				'\te: Statistics per epoch (fence-based synchronization)\n' + 
				'\tf: Fence statistics\n' + 
				'\tc: Time spent in calls (per rank)\n' + 
				'\tr: Reprint options\n' + 
				'\tq: Quit\n')
			action = input('Please select action: ')

		if action == 'q':
			sys.exit()
		elif action == 'e': #
			find_epochs()
		elif action == 'f':
			fence_summary()
		elif action == 'c':
			filter_calls_per_rank()
		elif action == 'r':
			pass
		else:
			print('Invalid action option!')
			action = 'r'

		if cmdlnaction:
			sys.exit()

""" 	


# from https://realpython.com/python-main-function/#a-basic-python-main 
# "What if you want process_data() to execute when you run the script from 
# the command line but not when the Python interpreter imports the file?"
if __name__ == "__main__":
	main()