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

__all__ = ["forma"]
__author__ = "Lena Kanellou"
__version__ = "0.1.1"

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
import forma_aux as fa
import forma_classes as fc
import forma_logging as fl
from forma_constants import *


import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter



def forma_parse_traces(tracefiles):


	exec_summary = fc.formaSummary()

	ranks = 0
	wins = 0
	exec_time = 0

	fl.forma_logger.debug('Inside forma parse traces.')

	schema = avro.schema.parse(open("schemas/summary.avsc", "rb").read())
	writer = DataFileWriter(open("rank_summaries.avro", "wb"), DatumWriter(), schema)

	for rank, tracefile in enumerate(tracefiles):
		with ft.FormaSTrace(tracefile, rank) as trace:
			fl.forma_print(f'Now parsing {tracefile}.\n')

			trace.read_stream() ## this will activate the callbacks and the computations therein.

			# fl.forma_logger.debug(f'Callcount for rank: {trace.trace_summary.callcount_per_opcode}\n' +
			# 	f'Win count for rank: {trace.trace_summary.wins}\n' +
			# 	f'Rank count initialized to: {trace.trace_summary.ranks}\n' +
			# 	f'Execution time: {trace.trace_summary.exectime}\n' +
			# 	f'Total RMA time: {trace.trace_summary.rmatime}\n' + 
			# 	f'Opduration metrics: {trace.trace_summary.opdurations}\n' +
			# 	f'Data transfer sizes metrics: {trace.trace_summary.xfer_per_opcode}\n' +
			# 	f'Window size stats: {trace.trace_summary.winsizes}\n' + 
			# 	f'Epochs/window stats: {trace.trace_summary.epochs}\n' +
			# 	f'Window lifetime stats: {trace.trace_summary.windurations}')

			writer.append({"rank_nr": rank, 
				"wins": trace.trace_summary.wins, 
				"mpi_gets": int(trace.trace_summary.callcount_per_opcode[GET]), 
				"mpi_puts": int(trace.trace_summary.callcount_per_opcode[PUT]), 
				"mpi_accs": int(trace.trace_summary.callcount_per_opcode[ACC]), 
				"mpi_fences" : int(trace.trace_summary.callcount_per_opcode[FENCE]), 
				"total_exec_times": trace.trace_summary.exectime.tolist(), 
				"total_rma_times": trace.trace_summary.rmatime.tolist(), 
				"mpi_get_times": trace.trace_summary.opdurations[GET].tolist(), 
				"mpi_put_times": trace.trace_summary.opdurations[PUT].tolist(), 
				"mpi_acc_times": trace.trace_summary.opdurations[ACC].tolist(), 
				"mpi_fence_times": trace.trace_summary.opdurations[FENCE].tolist(), 
				"window_sizes": trace.trace_summary.winsizes.tolist(), 
				"tf_per_win": trace.trace_summary.xfer_per_win.tolist(), 
				"epochs_per_win": trace.trace_summary.epochs.tolist(), 
				"win_durations": trace.trace_summary.windurations.tolist(), 
				"mpi_get_dtb": trace.trace_summary.dtbounds[GET].tolist(), 
				"mpi_put_dtb": trace.trace_summary.dtbounds[PUT].tolist(), 
				"mpi_acc_dtb": trace.trace_summary.dtbounds[ACC].tolist() })
			
			exec_summary += trace.trace_summary

	writer.close()
	exec_summary.set_averages()

	# reader = DataFileReader(open("rank_summaries.avro", "rb"), DatumReader())
	# for summary in reader:
	# 	print(summary)
	# reader.close()
      

	return exec_summary




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