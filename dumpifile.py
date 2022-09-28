#!/usr/bin/python3


###################################################################################
# RMA timing profiling using data from SST-Dumpi traces
# 
# In order to extract timing information from the traces, the following are assumed 
# about the corresponding executions:
#
# - Synchronization is based on MPI_Win_fence. PSCW and locks are not supported. 
# - Windows created by ranks belong to the same communicator. 
# - RMA epochs on different windows may overlap.
#
###################################################################################



import getopt 
import sys 
import glob, os
import re
import fnmatch
import numpy as np
import collections
import subprocess
import math

from bisect import insort

import matplotlib.pyplot as plt

import pandas as pd

import logging

from pydumpi import DumpiTrace

from ctypes.util import find_library



rma_tracked_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence']


def set_log_level(option):

	level=logging.INFO

	if option=='critical':
		level=logging.CRITICAL
	elif option=='error':
		level=logging.ERROR
	elif option=='warn':
		level=logging.WARNING
	elif option=='warning':
		level=logging.WARNING
	elif option=='info':
		level=logging.INFO
	elif option=='debug':
		level=logging.DEBUG
	else:
		#print('rma profiler: set_log_level: log level must be one of: {critical, error, warn, warning, info, debug}')
		level=None

	return level



class MyTrace(DumpiTrace):

	def __init__(self, file_name):
		super().__init__(file_name)
		self.message_count = 0
		self.fence_count = 0
		self.win_count = 0
		self.windows = []

	def on_send(self, data, thread, cpu_time, wall_time, perf_info):
		self.message_count += 1
		time_diff = wall_time.stop - wall_time.start

	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		self.fence_count += 1
		print(f'win fence on window {data.win}')

	def on_win_create(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		self.win_count += 1
		# check out file dumpi/common/argtypes.h, typedef struct dumpi_win_create
		print(data.win)
		print(data.size)
		self.windows.append((data.win, data.size))

	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		print(f'on_get window: {data.win}')
		# when in doubt, check out pydumpi/dtypes.py
		print(f'on_get count: {data.origincount}')
		print(f'on_get data type: {data.origintype}')

	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		print(f'on_put window: {data.win}')
		# when in doubt, check out pydumpi/dtypes.py
		print(f'on_put count: {data.origincount}')
		print(f'on_put data type: {data.origintype}')


	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		print(f'on_acc window: {data.win}')
		# when in doubt, check out pydumpi/dtypes.py
		print(f'on_acc count: {data.origincount}')
		print(f'on_acc data type: {data.origintype}')


def parse_traces():



	rma_set = frozenset(rma_tracked_calls)
	
	# use this in order to later validate with the amount of each call detected in the trace footers
	rma_occurrences = { i : 0 for i in rma_tracked_calls }

	# use this in order to later validate with the amount of each call detected in the trace footers
	j = 0
	#rma_indexes = { i : a for i, a in enumerate(rma_tracked_calls) }
	rma_indexes = { i : a for a, i in enumerate(rma_tracked_calls) }
	logging.debug(f'rma profiler: parse_trace_per_epoch: rma indexes are {rma_indexes}')


	ordered_files_all = sorted(os.listdir(format(str(dirname))))
	ordered_files = []
	ordered_ascii_files = []

	for filename in ordered_files_all:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			filepath = format(str(dirname))+'/'+format(str(filename))
			ordered_files.append(filepath)

	totalRanks = len(ordered_files)
	totalCallTypes = len(rma_tracked_calls)


	windows = [None for x in range(totalRanks)]

	rank = 0

	for tracefile in ordered_files:

	    with MyTrace(tracefile) as trace:
	        print(f'now reading {tracefile}')
	        trace.read_stream()
	        windows[rank] = (trace.windows)

	        print(trace.fence_count)
	        print(windows)
	        rank+=1



def main():

	global dirname, timestamp
	global fenceDiscrepancy


	fenceDiscrepancy=0

	action = 'r'
	cmdlnaction = False

	# default log level:
	level=logging.INFO

	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]


	try: 
		if len(argv) < 4 or len(argv) > 8:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ]')
			sys.exit(2)
		else:
			opts, args = getopt.getopt(argv, 'd:t:a:l:')
			for o, a in opts:
				if o == "-d": 
					dirname = a
				elif o == "-t":
					timestamp = a
				elif o == "-a":
					action = a
					cmdlnaction = True
				elif o == "-l":
					level=set_log_level(a)
					if level is None:
						raise ValueError("No such logging level! Must be one of: {critical, error, warn, warning, info, debug}")
						#sys.exit(2)
				else: 
					assert False, "No such command-line option!"
					sys.exit(2)
			#logging.debug('rma profiler: Directory name is : ' + format(str(dirname)))
			#logging.debug('rma profiler: Timestamp is : ' + format(str(timestamp)))
			
	except getopt.GetoptError:
		print ('Exception: wrong usage. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ] instead')
		sys.exit()


	# adjust log level to command line option
	#logging.basicConfig(level=logging.INFO)
	logging.basicConfig(level=level)

	parse_traces()



# from https://realpython.com/python-main-function/#a-basic-python-main 
# "What if you want process_data() to execute when you run the script from 
# the command line but not when the Python interpreter imports the file?"
if __name__ == "__main__":
	main()