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

import ctypes


import logging

from pydumpi import DumpiTrace


import forma_trace as ft


def forma_parse_traces(tracefiles):

	rank = 0
	opdata_per_rank = []
	total_exec_time_per_rank = []
	all_window_sizes_per_rank = []
	epochs_per_window_per_rank = []

	for tracefile in tracefiles:
		with ft.FormaIMTrace(tracefile) as trace:
			## keeping next line in order to remember where to find sizes in -- check pydumpi/undumpi.py

			print(f'now reading {tracefile}.')
			trace.read_stream()
			print(f'Fence count for rank {rank} is: {trace.fence_count}')
		rank += 1
		opdata_per_rank.append(trace.opdata_per_window)
		total_exec_time_per_rank.append(trace.total_exec_time)
		all_window_sizes_per_rank.append(trace.all_window_sizes)
		epochs_per_window_per_rank.append(trace.epochcount_per_window)

		#print(f'current trace produced by a run of source code : {(c_char * trace.source_file).from_address(0)}')

		#print("{0}".format(trace.source_file.argv[0]), end="\n")

		sourcefile = trace.source_file
		print(f'current trace produced by a run of source code : {sourcefile.argv}')

	return rank, trace.win_count, opdata_per_rank, total_exec_time_per_rank, all_window_sizes_per_rank, epochs_per_window_per_rank



def forma_calculate_dt_bounds(ranks, wins, opdata_per_rank):

	print('Calculating data transfer bounds in execution...')

	#print(opdata_per_rank)

	for i in range(ranks): # rank
		#print(f'rank {i} out of {ranks}')
		for j in range(wins): # window
			#print(f'\twindow {j} out of {wins}')
			for k in range(len(opdata_per_rank[i][j])-1): # epoch
				#print(f'\t\tepoch {k} out of {len(opdata_per_rank[i][j])-1}')
				for l in range(len(opdata_per_rank[i][j][k])-1): # operation, except fence
					opdata_per_rank[i][j][k][l][4] = opdata_per_rank[i][j][k][-1][3] - opdata_per_rank[i][j][k][l][1]
					#print(f'\t\t\toperation {l} out of {len(opdata_per_rank[i][j][k])}')
	return True