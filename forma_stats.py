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

import logging

from pydumpi import DumpiTrace

import forma_trace as ft


def forma_calculate_stats_x4(values_vector):

	""" this is a vector that contains the output values in the 
		order followed in all printing functions, namely:
		[ aggregate,    min,    max,    avg,   mean,   std dev ]
	"""

	output_stats = []

	if values_vector == []:
		output_stats = ['-']*4
	else:
		output_stats.append(sum(values_vector))
		output_stats.append(min(values_vector))
		output_stats.append(max(values_vector))
		output_stats.append(output_stats[0]/len(values_vector))

	return output_stats


def forma_calculate_stats_x6(values_vector):

	""" this is a vector that contains the output values in the 
		order followed in all printing functions, namely:
		[ aggregate,    min,    max,    avg,   mean,   std dev ]
	"""
	output_stats = []

	if values_vector == []:
		output_stats = ['-']*6
	else:
		output_stats.append(sum(values_vector))
		output_stats.append(min(values_vector))
		output_stats.append(max(values_vector))
		output_stats.append(output_stats[0]/len(values_vector))
		output_stats.append(np.median(values_vector))
		output_stats.append(np.std(values_vector))

	return output_stats

def forma_break_down_per_rank_per_window(ranks, wins, opdata_per_rank):

	per_opcode_op_durations = []
	per_window_data_vol = []

	""" for vectors that refer to RMA ops, we use the following 
	convention for indexing: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc
	and if present, then 3 - MPI_Win_fence
	"""
	#total_ops_num = [0]*4
	per_opcode_op_durations = [[[] for i in range(4)] for j in range(ranks)]
	per_opcode_dt_bounds = [[[] for i in range(3)] for j in range(ranks)]
	per_window_data_vol = [0 for i in range(wins)]


	for rank in range(ranks):
		for win_id in range(wins):
			for epoch in (range(len(opdata_per_rank[rank][win_id])-1)):
				#for op in range(len(epoch)):
				for op in opdata_per_rank[rank][win_id][epoch]:
					#total_ops_num[op[0]] = total_ops_num[op[0]] + 1
					per_opcode_op_durations[rank][op[0]].append(op[2])
					if op[0] != 3:
						per_opcode_dt_bounds[rank][op[0]].append(op[4])
						#per_opcode_data_vol[op[0]].append(op[3])
						per_window_data_vol[win_id] = per_window_data_vol[win_id] + op[3]


	return per_opcode_op_durations, per_opcode_dt_bounds, per_window_data_vol


def forma_calc_stats_summary(ranks, wins, total_exec_times_per_rank, all_window_sizes, epochs_per_window, opdata_per_rank):

	opduration_stats = []
	windata_stats = []
	dtbound_stats = []

	""" for vectors that refer to RMA ops, we use the following 
	convention for indexing: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc
	and if present, then 3 - MPI_Win_fence
	"""
	#total_ops_num = [0]*4
	per_opcode_op_durations = [[] for i in range(4)]
	per_opcode_dt_bounds = [[] for i in range(3)]
	per_window_data_vol = [0 for i in range(wins)]
	
	for rank in range(ranks):
		for win_id in range(wins):
			for epoch in (range(len(opdata_per_rank[rank][win_id])-1)):
				#for op in range(len(epoch)):
				for op in opdata_per_rank[rank][win_id][epoch]:
					#total_ops_num[op[0]] = total_ops_num[op[0]] + 1
					per_opcode_op_durations[op[0]].append(op[2])
					if op[0] != 3:
						per_opcode_dt_bounds[op[0]].append(op[4])
						#per_opcode_data_vol[op[0]].append(op[3])
						per_window_data_vol[win_id] = per_window_data_vol[win_id] + op[3]


	opduration_stats = forma_calc_opduration_summary(ranks, total_exec_times_per_rank, per_opcode_op_durations)

	windata_stats = forma_calc_windata_summary(wins, all_window_sizes, per_window_data_vol, epochs_per_window)

	dtbound_stats = forma_calc_dtbounds_summary(per_opcode_dt_bounds)

	return opduration_stats, windata_stats, dtbound_stats


def forma_calc_opduration_summary(ranks, total_exec_times_per_rank, per_opcode_op_durations):

	opduration_stats = [[5]*6 for i in range(6)]

	opduration_stats[0] = forma_calculate_stats_x6(total_exec_times_per_rank)

	# print(f'passing {per_opcode_op_durations[0]+per_opcode_op_durations[1]+per_opcode_op_durations[2]+per_opcode_op_durations[3]} to calc_stats_x6')
		
	opduration_stats[1] = forma_calculate_stats_x6(per_opcode_op_durations[0]+per_opcode_op_durations[1]+per_opcode_op_durations[2]+per_opcode_op_durations[3])

	for i in range(4):
		opduration_stats[i+2] = forma_calculate_stats_x6(per_opcode_op_durations[i])

	return opduration_stats

def forma_calc_windata_summary(wins, all_window_sizes, per_window_data_vol, epochs_per_window):

	windata_stats = [[9]*4 for i in range(3)]

	windata_stats[0] = forma_calculate_stats_x4(all_window_sizes)
	windata_stats[1] = forma_calculate_stats_x4(per_window_data_vol)
	windata_stats[2] = forma_calculate_stats_x4(epochs_per_window)
	return windata_stats


def forma_calc_dtbounds_summary(per_opcode_dt_bounds):

	dtbound_stats = [[0]*4 for i in range(4)]

	for i in range(3):
		dtbound_stats[i] = forma_calculate_stats_x4(per_opcode_dt_bounds[i])
		#print(per_opcode_dt_bounds[i])

	return dtbound_stats


def forma_calculate_stats_overall_x6(ranks, wins, opdata_per_rank, calc_type):

	opsum = 0
	opmin = 0
	opmax = 0
	opavg = 0
	opmed = 0
	opstd = 0

	total_ops_num = 0
	all_ops_durations = []

	""" if calc_typ is 't', we are calculating stats for 
	data transfer bounds and need the last element of an 
	op tuple. otherwise, we should calculate durations, so
	we access the 3rd element of the op tuple. 
	"""

	if calc_type == 't':
		opindex = 4
	else:
		opindex = 2

	for rank in range(ranks):
		for win_id in range(wins):
			for epoch in (range(len(opdata_per_rank[rank][win_id])-1)):
				#for op in range(len(epoch)):
				for op in opdata_per_rank[rank][win_id][epoch]:
					all_ops_durations.append(op[opindex])
					total_ops_num = total_ops_num + 1
					opsum = opsum + op[opindex]
					if opmin > op[opindex] or opmin == 0:
						opmin = op[opindex]
					if opmax < op[opindex]:
						opmax = op[opindex]

	opavg = opsum / total_ops_num
	opmed = np.median(all_ops_durations)
	opstd = np.std(all_ops_durations)

	return [opsum, opmin, opmax, opavg, opmed, opstd]


def forma_calculate_stats_per_type_x6():
	return True