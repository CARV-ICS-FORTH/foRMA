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
#	My convention:
#	-> using # to comment out code
#	-> using ## to add comments and explanation
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
		#self.message_count = 0
		self.fence_count = 0
		self.win_count = 0
		self.wincreate_count = 0
		self.windows = dict()
		self.wintb = dict()



	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		# count mpi_win_fence occurrences
		self.fence_count += 1

		## identify window key to use on windows dictionary by looking into wintb
		win_id = self.wintb[data.win]

		## elements of self.windows[data.win] (value) are: window size [0], current window epoch [1], list of bytes moved per epoch [2]

		## increase epoch count on corresponding window
		## first fence ever on 
		# self.windows[data.win][1]+=1
		self.windows[win_id][1] += 1

		"""if (self.windows[data.win][1]>0):
			print(f'win fence on window {data.win}: Fence count is {self.fence_count} | Epoch (completed) count on window is {self.windows[data.win][1]}')
			print(f'curren data volumes per epoch are: {self.windows[data.win]}')"""

		## prepare dictionary for next iteration. i.e.:
		## add a zero element to list of bytes moved per epoch in order to save on a check on whether that epoch exists later on (in on_get, on_put, for ex.)
		# if (self.windows[data.win][1]>-1): ## epoch count in self.windows[data.win][1] has already been incremented, so the >-1 check is correct
		if (self.windows[win_id][1]>-1): 
			# self.windows[data.win][2].append(0)
			self.windows[win_id][2].append(0)
			# since I have no way of knowing whether the current fence call is the last one in the execution, 
			# there will always be a last, 0-value field in this list. so, the length of the list is epoch#+1
		#print(f'window {data.win} : current data volumes per epoch are: {self.windows[data.win]}')

	def on_win_create(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		self.win_count += 1
		self.wincreate_count += 1

		## on create, I update the window ID to index translation buffer
		## on free, I will free the corresponding entry
		## DEBUG attempt: I am using a check with -1 in order to detect eventual collisions
		if self.wintb: ## check first if dict is empty, otherwise nasty seg faults
			if data.win in (self.wintb).keys(): ## if NOT empty and key already exists... 
				if (self.wintb[data.win] != -1): ## ... check value, in case on_win_free has not yet been called on it
					print(f'COLLISION ON WINDOW ID {data.win}')
			#print('window tb not empty, key does not exist') 
			## otherwise, not empty, but key does not exist yet
			self.wintb[data.win] = self.win_count
		else:
			self.wintb[data.win] = self.win_count
			#print('window tb empty')
		

		## check out file dumpi/common/argtypes.h, typedef struct dumpi_win_create
		#print(data.win)
		#print(data.size)

		# elements of self.windows[data.win] (value) are: window size, current window epoch, list of bytes moved per epoch
		# initializing data volume of first epoch to zero anyway
		#self.windows[data.win] = [data.size, -1, []]
		self.windows[self.wintb[data.win]] = [data.size, -1, []]

	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		self.wintb[data.win] = -1

	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		win_id = self.wintb[data.win]
		#print(f'on_get window: {data.win}')
		## when in doubt, check out pydumpi/dtypes.py
		#print(f'on_get count: {data.origincount}')
		#print(f'on_get data type: {data.origintype}')
		#print(f'on_get size in bytes: {data.origincount*self.type_sizes[data.origintype]}')
		self.windows[data.win][2][self.windows[data.win][1]]+=data.origincount*self.type_sizes[data.origintype]
		#self.windows[win_id][2][self.windows[win_id][1]]+=data.origincount*self.type_sizes[data.origintype]


	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		win_id = self.wintb[data.win]
		#print(f'on_put window: {data.win}')
		## when in doubt, check out pydumpi/dtypes.py
		#print(f'on_put count: {data.origincount}')
		#print(f'on_put data type: {data.origintype}')
		#print(f'on_put size in bytes: {data.origincount*self.type_sizes[data.origintype]}')
		self.windows[data.win][2][self.windows[data.win][1]]+=data.origincount*self.type_sizes[data.origintype]
		#self.windows[win_id][2][self.windows[win_id][1]]+=data.origincount*self.type_sizes[data.origintype]


	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		win_id = self.wintb[data.win]
		#print(f'on_acc window: {data.win}')
		## when in doubt, check out pydumpi/dtypes.py
		#print(f'on_acc count: {data.origincount}')
		#print(f'on_acc data type: {data.origintype}')

		## TODO: refine this callback, depending on acc operation and transfer direction... :/
		#self.windows[data.win][2][self.windows[data.win][1]]+=data.origincount*self.type_sizes[data.origintype]
		self.windows[win_id][2][self.windows[win_id][1]]+=data.origincount*self.type_sizes[data.origintype]


def parse_traces():

	rma_set = frozenset(rma_tracked_calls)
	
	## use this in order to later validate with the amount of each call detected in the trace footers
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

	#print(ordered_files)

	totalRanks = len(ordered_files)
	totalCallTypes = len(rma_tracked_calls)


	windows = [None for x in range(totalRanks)]
	windowsums = [None for x in range(totalRanks)]


	rank = 0

	for tracefile in ordered_files:

	    with MyTrace(tracefile) as trace:
	    	## keeping next line in order to remember where to find sizes in -- check pydumpi/undumpi.py
	        print(f'now reading {tracefile}.')
	        trace.read_stream()
	        windows[rank] = (trace.windows)

	        print(f'Fence count for rank {rank} is: {trace.fence_count}')
	        print(f'Win_create occurrences for rank {rank} is: {trace.wincreate_count}')

	        #print(f'Different win IDs for rank {rank} is: {len(trace.windows)}')
	        #print(f'Win IDs for rank {rank} are: {(trace.windows).keys()}')




	        #print(windows)
	        rank+=1





	length = len(windows[0])
	prev_fences = 0
	for win in range(length):
		print(f'Window key is {win+1}, size is {windows[0][win+1][0]}')
		prev_rank_val = 0
		for rank in range(totalRanks):
			if rank > 0:
				if prev_rank_val != windows[rank][win+1][0]:
					print(f'size discrepancy on window {win+1} for rank {rank}!!!')
			prev_rank_val = windows[rank][win+1][0]

			
			"""
			if rank == 0:
				if prev_fences != windows[rank][win+1][1]:
					print(f'rank {rank}: epochs differ between windows {win} ({prev_fences}) and {win+1} ({windows[rank][win+1][1]})')
			prev_fences = windows[rank][win+1][1]
			"""



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


	## adjust log level to command line option
	#logging.basicConfig(level=logging.INFO)
	logging.basicConfig(level=level)


	print('RMA timing profiler initialized. Parsing traces...')

	parse_traces()

	"""
	windows_test = {1: [2, [3, 4]], 2: [4, [4,4,4,4]]}	
	print(windows_test)
	windows_test[1][1].append(3)
	windows_test[1][0]+=1
	print(windows_test)
	"""


if __name__ == "__main__":
	main()