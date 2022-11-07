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

import gc

from bisect import insort

import matplotlib.pyplot as plt

import pandas as pd

import logging

from pydumpi import DumpiTrace

from ctypes.util import find_library

import forma_trace as ft
import forma_parse as fp
import forma_stats as fs
import forma_prints as fo


rma_tracked_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence']


def check_filepaths(dirname, timestamp):

	ordered_files_all = sorted(os.listdir(format(str(dirname))))
	ordered_files = []
	ordered_ascii_files = []

	total_file_size = 0

	for filename in ordered_files_all:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			filepath = format(str(dirname))+'/'+format(str(filename))

			total_file_size = total_file_size + os.path.getsize(filepath)

			ordered_files.append(filepath)

	#print(ordered_files)
	total_file_size = total_file_size/1024

	print(f'\nAbout to parse a total of {round(total_file_size)} KBytes of binary trace files size.\n')

	return(ordered_files)


def check_mem_capacity(tracefiles, rma_tracked_calls):

	total_rma_occurrences = 0

	for tf in tracefiles:
		with ft.FormaTrace(tf, []) as trace:
			print(f'Reading footer of {tf}.')
			fcalls, icalls = trace.read_footer()
			for name, count in fcalls.items():
				if name in {"on_get", "on_put", "on_accumulate", "on_win_fence"}:
					#print("  {0}: {1}".format(name, count))
					total_rma_occurrences += count

	in_mem_estimate = (total_rma_occurrences * 32) / 1024 ## how many KByte for in-memory version? (assuming 32 byte needed per op)

	print(f'Total RMA occurrences to be considered: {total_rma_occurrences}')

	if in_mem_estimate > 9.766e+6: ## for now, checking whether I need more than 10 Giga
		return True
	else:
		return False



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



def main():

	global dirname, timestamp
	global fenceDiscrepancy

	fenceDiscrepancy=0

	action = 'r'
	cmdlnaction = False
	version = 'i' ## can be 'i' for incremental or 'm' for in-mem

	# default log level:
	level=logging.INFO

	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]

	total_wins = 0
	min_win_size = 0
	max_win_size = 0
	avg_vol = 0
	avg_epoch = 0


	try: 
		if len(argv) < 4 or len(argv) > 8:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ] [ -v <version>]')
			sys.exit(2)
		else:
			opts, args = getopt.getopt(argv, 'd:t:a:v:l:')
			for o, a in opts:
				if o == "-d": 
					dirname = a
				elif o == "-t":
					timestamp = a
				elif o == "-a":
					action = a
					cmdlnaction = True
				elif o == "-v":
					version = a
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

	tracefiles = check_filepaths(dirname, timestamp)

	if version=='m':
		if check_mem_capacity(tracefiles, rma_tracked_calls):
			print("In-memory version for this trace will exhaust your system's resources. Opt for incremental version instead.")
			sys.exit(2)


	## adjust log level to command line option
	#logging.basicConfig(level=logging.INFO)
	logging.basicConfig(level=level)

	total_wins = fp.parse_traces(tracefiles)

	winsummary = [total_wins, min_win_size, max_win_size, avg_vol, avg_epoch]
	getsummary = [0 for x in range(5)]
	putsummary = [0 for x in range(5)]
	accsummary = [0 for x in range(5)]

	fo.forma_print_console_summary(winsummary, getsummary, putsummary, accsummary)




if __name__ == "__main__":
	main()