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
import forma_constants as fx


def forma_parse_traces(tracefiles):


	exec_summary = fc.formaSummary()

	ranks = 0
	wins = 0
	exec_time = 0

	fl.forma_logger.debug('Inside forma parse traces.')

	for tracefile in tracefiles:
		with ft.FormaSTrace(tracefile) as trace:
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

			exec_summary += trace.trace_summary

	exec_summary.set_averages()

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