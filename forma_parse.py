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

import numpy as np

from pympler import asizeof


import forma_trace as ft


def forma_parse_traces(tracefiles):

	rank = 0
	opdata_per_rank = []
	total_exec_time_per_rank = []
	all_window_sizes_per_rank = []
	all_window_durations_per_rank = []
	epochs_per_window_per_rank = []
	callcount_per_opcode = [0, 0, 0, 0, 0, 0, 0, 0]

	for tracefile in tracefiles:

		# csv_file = tracefile+".csv"
		# pickle_file = tracefile+".pickle"
		# parquet_file = tracefile+".parquet"

		# with ft.FormaIMTrace(tracefile, csv_file, pickle_file, parquet_file) as trace:
		with ft.FormaIMTrace(tracefile) as trace:
			## keeping next line in order to remember where to find sizes in -- check pydumpi/undumpi.py

			print(f'now reading {tracefile}...\t\t', end="")
			trace.read_stream()
			#print(f'Fence count for rank {rank} is: {trace.fence_count}')
			print('Done.\n')
		rank += 1
		opdata_per_rank.append(trace.opdata_per_window)
		total_exec_time_per_rank.append(trace.total_exec_time)
		all_window_sizes_per_rank.append(trace.all_window_sizes)
		all_window_durations_per_rank.append(trace.all_window_durations)
		epochs_per_window_per_rank.append(trace.epochcount_per_window)

		##
		# temp = np.array(trace.opdata_per_window, dtype=object) 
		# flatarray = np.concatenate(temp).ravel()
		# print(flatarray)
		# #binarray = np.array(flatarray, dtype='i4')
		# print(f'Size of opdata for rank: {asizeof.asizeof(trace.opdata_per_window)}')
		# print(f'Size of flattened list: {asizeof.asizeof(flatarray)}')
		# print(f'Size of flattened list data: {asizeof.asizeof(flatarray.data)}')
		#print(f'Size of binary list: {asizeof.asizeof(binarray)}')
		#np.savez("flatarraytest"+str(rank), flatarray)
		#flatarray.astype('i4').tofile("flatarraytest"+str(rank))
		##

		callcount_per_opcode = [sum(i) for i in zip(callcount_per_opcode, trace.callcount_per_opcode)]

		#print(f'current trace produced by a run of source code : {(c_char * trace.source_file).from_address(0)}')

		#print("{0}".format(trace.source_file.argv[0]), end="\n")

		#sourcefile = trace.source_file
		#print(f'current trace produced by a run of source code : {sourcefile}')


		# with open(tracefile+".avro", 'rb') as file_object: 
		# 	csv_file = csv.writer(open(tracefile+".rc.csv", "w+")) 
		# 	head = True 
		# 	for emp in reader(file_object): 
		# 		if head: # write
		# 			header = emp.keys() 
		# 			csv_file.writerow(header) 
		# 			head = False # write normal row 
		# 		csv_file.writerow(emp.values())


	return rank, trace.win_count, callcount_per_opcode, opdata_per_rank, total_exec_time_per_rank, all_window_sizes_per_rank, all_window_durations_per_rank, epochs_per_window_per_rank



def forma_calculate_dt_bounds_estimate(ranks, wins, opdata_per_rank):

	print('Calculating data transfer bounds in execution...\t\t', end="")

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
	print('Done.\n')
	return True



def forma_calculate_dt_bounds(ranks, wins, opdata_per_rank):

	print('Calculating data transfer bounds in execution...\t\t', end="")

	targetrank = 0

	for i in range(ranks): # rank
		#print(f'rank {i} out of {ranks}')
		for j in range(wins): # window
			#print(f'\twindow {j} out of {wins}')
			for k in range(len(opdata_per_rank[i][j])-1): # epoch
				#print(f'\t\tepoch {k} out of {len(opdata_per_rank[i][j])-1}')
				for l in range(len(opdata_per_rank[i][j][k])-1): # operation, except fence
					if opdata_per_rank[i][j][k][l][0] != 0:
						targetrank = opdata_per_rank[i][j][k][l][4]
					opdata_per_rank[i][j][k][l][4] = opdata_per_rank[targetrank][j][k][-1][3] - opdata_per_rank[i][j][k][l][1]
					#print(f'\t\t\toperation {l} out of {len(opdata_per_rank[i][j][k])}')
	print('Done.\n')
	return True