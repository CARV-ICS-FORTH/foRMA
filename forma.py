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



import argparse
import sys 
import glob, os
import re
import fnmatch

import numpy as np

import logging

from pydumpi import DumpiTrace
from pydumpi import util

from tabulate import tabulate

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
	total_file_size = round(total_file_size/1024)
	if total_file_size == 0:
		print('Trace files seem empty. Make sure that you are using well-formatted SST Dumpi outputs.')
		sys.exit(1)

	## Read metafile and print it -- TODO: to be used more extensively later
	try:
		metafile = util.read_meta_file(str(dirname)+'/dumpi-'+format(str(timestamp))+'.meta')
	except FileNotFoundError:
		print('Trace files not found. Check timestamp formatting.\n\n')
		sys.exit(1)

	print(f'\nAbout to parse a total of {total_file_size} KBytes of binary trace files size.\n')

	return(ordered_files)


def check_mem_capacity(tracefiles, rma_tracked_calls, rma_callcount_per_rank):

	total_rma_occurrences = 0


	for tf in tracefiles:

		rma_occurrences_for_rank = [0,0,0,0]

		with ft.FormaIMTrace(tf) as trace:
			print(f'Reading footer of {tf}.')
			#trace.print_footer()
			fcalls, icalls = trace.read_footer()
			
			for name, count in fcalls.items():
				#if name in {"on_get", "on_put", "on_accumulate", "on_win_fence"}:
				if name == "on_get": 
					print("  {0}: {1}".format(name, count))
					rma_occurrences_for_rank[0] = count
					total_rma_occurrences += count
				if name == "on_put": 
					print("  {0}: {1}".format(name, count))
					rma_occurrences_for_rank[1] = count
					total_rma_occurrences += count
				if name == "on_accumulate": 
					print("  {0}: {1}".format(name, count))
					rma_occurrences_for_rank[2] = count
					total_rma_occurrences += count
				if name == "on_win_fence": 
					print("  {0}: {1}".format(name, count))
					rma_occurrences_for_rank[3] = count
					total_rma_occurrences += count

		rma_callcount_per_rank.append(rma_occurrences_for_rank)

	in_mem_estimate = (total_rma_occurrences * 32) / 1024 ## how many KByte for in-memory version? (assuming 32 byte needed per op)

	#print(f'Total RMA occurrences to be considered: {total_rma_occurrences}')

	if in_mem_estimate > 9.766e+6: ## for now, checking whether I need more than 10 Giga
		return True
	else:
		return False


def check_consistency(ranks, wins, opdata_per_rank):

	print("Performing a format sanity check on extracted trace data...\t", end="")

	if len(opdata_per_rank) != ranks:
		return 1
	else:
		for i in range(ranks):
			if len(opdata_per_rank[i]) != wins:
				return 2
		for j in range(wins):
			epoch_cnt = len(opdata_per_rank[0][j])
			for i in range(ranks):
				if len(opdata_per_rank[i][j]) != epoch_cnt:
					return 3
	
	print("Sanity check ok.\n")
	return 0



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

"""
Outputs data transfer bounds and data volume information into 
file epochs.txt. Data is calculated by memory window found in 
the execution. For each memory window, the relevant information 
is organized by synchronization epochs on that window. 
"""
def per_epoch_stats_to_file(ranks, wins, per_window_data_vol, opdata_per_rank, all_window_durations_per_rank):

	opdata_for_epoch = []
	per_opcode_dt_bound_aggregates_for_window = [0 for i in range(3)]
	per_opcode_count_for_window = [0 for i in range(4)]
	per_opcode_duration_aggregates_for_window = [0 for i in range(4)]
	epoch_data_vol_sum = 0
	win_duration = [[0,1,2,3], [4,5,6,7]]

	labels = ["- MPI_Get", "- MPI_Put", "- MPI_Accumulate", "- MPI_Win_fence"]

	original_stdout = sys.stdout # Save a reference to the original standard output
	with open('epochs.txt', 'w') as f:
		sys.stdout = f # Change the standard output to the file we created.
		print('------------------------------------------------------------------------------------------\n' + 
		'----------- RMA data transfer bounds - statistics per window per epoch -------------------\n' + 
		'------------------------------------------------------------------------------------------\n')

		for win_id in range(wins):
			print(f'WINDOW ID: {win_id} \n\n' +
				f'-- Total bytes transferred\t:   {per_window_data_vol[win_id]}\n' +
				f'-- Total epochs\t\t\t:   {len(opdata_per_rank[0][win_id])-1}\n')
			for epoch in range(len(opdata_per_rank[0][win_id])-1):
				for rank in range(ranks):
					for op in opdata_per_rank[rank][win_id][epoch]:
						#print(f'value is {opdata_per_rank[rank][win_id][epoch]}')
						opdata_for_epoch.append(op)
				#print(f'opdata_for_epoch: {opdata_for_epoch}')
				per_opcode_dt_bounds_for_epoch, per_opcode_durations_for_epoch, epoch_data_vol_sum = fs.forma_merge_dt_op_durations_for_epoch(opdata_for_epoch)

				##
				per_opcode_count_for_window = [sum(i) for i in zip(per_opcode_count_for_window, [len(x) for x in per_opcode_durations_for_epoch])]
				#print(f'per_opcode_count_for_window: {per_opcode_count_for_window}')
				##

				#dtbound_stats_for_epoch = fs.forma_calculate_dtbounds_stats_for_epoch(per_opcode_dt_bounds_for_epoch)
				##
				opduration_stats_for_epoch, dtbound_stats_for_epoch = fs.forma_calculate_opduration_dtbounds_stats_for_epoch(per_opcode_durations_for_epoch, per_opcode_dt_bounds_for_epoch)
				##

				#per_opcode_duration_aggregates_for_window = [sum(i) for i in zip(per_opcode_duration_aggregates_for_window, opduration_stats_for_epoch[:0])]
				#per_opcode_dt_bound_aggregates_for_window = [sum(i) for i in zip(per_opcode_dt_bound_aggregates_for_window, dtbound_stats_for_epoch[:0])]

				for i in range(4): # i is the opcode in range 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc, 3 - MPI_Win_fence
					if i != 3:
						per_opcode_duration_aggregates_for_window[i] = per_opcode_duration_aggregates_for_window[i]+opduration_stats_for_epoch[i][0]
						per_opcode_dt_bound_aggregates_for_window[i] = per_opcode_dt_bound_aggregates_for_window[i]+dtbound_stats_for_epoch[i][0]
					else:
						per_opcode_duration_aggregates_for_window[i] = per_opcode_duration_aggregates_for_window[i]+opduration_stats_for_epoch[i][1]


				print(f'-------> Epoch {epoch} \n\n' + 
					f'Total bytes transferred\t\t :   {epoch_data_vol_sum}\n\n' +
					'DT bound statistics\n' +
					'-------------------')
				fo.forma_print_dtbounds_stats_for_epoch(dtbound_stats_for_epoch)

				##
				print('Op duration statistics\n' +
					'-------------------')
				fo.forma_print_opduration_stats_for_epoch(opduration_stats_for_epoch)

				##

				opdata_for_epoch = []
				epoch_data_vol_sum = 0

			window_summary_rows = [[0 for i in range(3)] for j in range(4)]

			for i in range(4): # each of the opcodes considered
				window_summary_rows[i][0] = per_opcode_count_for_window[i]
				if per_opcode_count_for_window[i] != 0:
					window_summary_rows[i][1] = per_opcode_duration_aggregates_for_window[i] / per_opcode_count_for_window[i]
					if i != 3:
						window_summary_rows[i][2] = per_opcode_dt_bound_aggregates_for_window[i] / per_opcode_count_for_window[i]


			win_duration[0]	= fs.forma_calculate_stats_x4([all_window_durations_per_rank[i][win_id][0] for i in range(ranks)])
			win_duration[1] = fs.forma_calculate_stats_x4([all_window_durations_per_rank[i][win_id][1] for i in range(ranks)])

			print('------------------------------------------------------------------------------------------\n' + 
				f'SUMMARY for Window {win_id}:\n\n' + 
				f'-- Total bytes transferred\t:   {per_window_data_vol[win_id]}\n' +
				f'-- Total epochs\t\t\t:   {len(opdata_per_rank[0][win_id])-1}\n\n' +
				'-- Op duration and DT bound averages per op code --')
			print(f'{tabulate([[labels[i]]+window_summary_rows[i] for i in range(4)], headers=["instances", "average duration", "average DT bound"])}\n')
			print(f'{tabulate([["MPI_Win_create duration"]+win_duration[0], ["Window lifetime"]+win_duration[1]], headers=["aggregate", "min", "max", "average"])}\n')
			print('------------------------------------------------------------------------------------------\n')

			##
			# per_opcode_dt_bounds_for_window = []
			# per_opcode_durations_for_window = []
			##

			per_opcode_duration_aggregates_for_window = [0 for i in range(4)]
			per_opcode_dt_bound_aggregates_for_window = [0 for i in range(3)	]
			per_opcode_count_for_window = [0 for i in range(4)]


	sys.stdout = original_stdout # Reset the standard output to its original value
	
	return True

"""
Creates statistics on fence execution. Outputs first and 
last arrival to MPI_Win_fence instances in execution, into 
file fences.txt. Information is provided both as timestamp 
and rank ID.  
"""
def fence_stats_to_file(ranks, wins, per_window_data_vol, all_window_sizes, opdata_per_rank):

	timestamps_ranks = [0]*6

	original_stdout = sys.stdout # Save a reference to the original standard output
	with open('fences.txt', 'w') as f:
		sys.stdout = f # Change the standard output to the file we created.
		print('------------------------------------------------------------------------------------------\n' + 
		'----------------------- Rank arrivals to fences per window  ------------------------------\n' + 
		'------------------------------------------------------------------------------------------\n' +
		f'-- Total ranks\t\t:   {ranks}\n' +
		f'-- Total windows\t:   {wins}\n\n')

		for win_id in range(wins):	
			print(f'WINDOW ID:  {win_id}\n\n')
			win_total_epochs = len(opdata_per_rank[0][win_id])-1
			#print(f'all_window_sizes[win_id]: {all_window_sizes[win_id]}, win_total_epochs: {win_total_epochs}, per_window_data_vol[win_id]: {per_window_data_vol[win_id]}')
			fo.forma_print_window_info([all_window_sizes[win_id], win_total_epochs, per_window_data_vol[win_id]])
			for epoch in range(win_total_epochs):
				fence_arrivals_for_epoch = []
				for rank in range(ranks):
					fence_arrivals_for_epoch.append(opdata_per_rank[rank][win_id][epoch][-1][1])

				timestamps_ranks, arrival_order = fs.forma_calculate_stragglers_for_fence(fence_arrivals_for_epoch)
				timestamps_ranks[0] = epoch # used for correctly printing the epoch nr in the first column in forma_print_timestamps_ranks()

				fo.forma_print_timestamps_ranks(timestamps_ranks)
				print(f'Arrival order: {arrival_order}\n')
	sys.stdout = original_stdout # Reset the standard output to its original value

	return True

"""
Creates statistics on time spent inside various MPI calls. Outputs 
MPI RMA call durations and statistics on them, into file calls.txt. 
Data is calculated by rank found to participate in the execution. 
For each rank, information is organized by RMA opcode.
"""
def per_op_durations_to_file(ranks, total_exec_times_per_rank, per_opcode_op_durations_per_rank, per_opcode_dt_bounds_per_rank):

	opduration_stats_for_rank = []
	dt_bounds_stats_for_rank = []

	original_stdout = sys.stdout # Save a reference to the original standard output
	with open('calls.txt', 'w') as f:
		sys.stdout = f # Change the standard output to the file we created.
		print('------------------------------------------------------------------------------------------\n' + 
		'------------------------ RMA operation durations per rank  -------------------------------\n' + 
		'------------------------------------------------------------------------------------------\n' +
		f'-- Total ranks\t\t:   {ranks}\n')

		for i in range(ranks):
			per_opcode_op_durations_for_rank = per_opcode_op_durations_per_rank[i]
			per_opcode_dt_bounds_for_rank = per_opcode_dt_bounds_per_rank[i]
			opduration_stats_for_rank, dt_bounds_stats_for_rank = fs.forma_calculate_opduration_dtbounds_stats_for_rank(per_opcode_op_durations_for_rank, per_opcode_dt_bounds_for_rank)
			fo.forma_print_rank_stats(i, total_exec_times_per_rank[i], opduration_stats_for_rank)
			fo.forma_print_rank_dt_bounds(i, dt_bounds_stats_for_rank)
	sys.stdout = original_stdout # Reset the standard output to its original value
	return True


def main():

	global dirname, timestamp

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


	## set up how foRMA has to be invoked ...
	forma_arg_parse = argparse.ArgumentParser(description="foRMA -- a methodology and a tool for profiling MPI RMA operation timing, designed to process traces produced by SST Dumpi.")
	forma_arg_parse.add_argument("directory", help="Specifies the path to the directory in which the tracefiles to be parsed are located.", type=str)
	forma_arg_parse.add_argument("timestamp", help="Specifies the timestamp that makes up the filenames of the tracefiles to be parsed.", type=str)
	forma_arg_parse.add_argument("-d", "--debug", help="Turns on debug messages and is meant to be used for developing the tool and not when using it to profile traces.",
                    action="store_true")
	forma_arg_parse.add_argument("-s", "--summary", help="When specified, foRMA only produces a summary of statistics and exits without offering the interactive prompt.", action="store_true")
	forma_arg_parse.add_argument("-a", "--all", help="Produce full analysis broken down per ranks and per windows, output to files epochs.txt, fences.txt, and calls.txt. Equivalent to -c -e -f.", action="store_true")
	forma_arg_parse.add_argument("-c", "--calls", help="Output time spent in calls (per rank), as well as data transfer bounds, in file calls.txt.", action="store_true")
	forma_arg_parse.add_argument("-e", "--epochs", help="Produce statistics per epoch (fence-based synchronization), output to file epochs.txt", action="store_true")
	forma_arg_parse.add_argument("-f", "--fences", help="Produce fence statistics, output to file fences.txt.", action="store_true")


	## ... and get the required parameters from the command-line arguments
	args = forma_arg_parse.parse_args()
	dirname = args.directory
	timestamp = args.timestamp
	cmdlnaction = args.summary


	#print('\nfoRMA - RMA timing profiling. Preparing analysis of trace.')

	try:	
		f=open ('forma-banner.txt','r')
		print(''.join([line for line in f]))
	except OSError as e:
		print('\n\n.: foRMA: RMA Profiling for MPI :.\n\n')


	tracefiles = check_filepaths(dirname, timestamp)

	
	rma_callcount_per_rank = []
	#check_mem_capacity(tracefiles, rma_tracked_calls, rma_callcount_per_rank)
	"""
	if version=='m':
		if check_mem_capacity(tracefiles, rma_tracked_calls, rma_callcount_per_rank):
			print("In-memory version for this trace will exhaust your system's resources. Opt for incremental version instead.")
			sys.exit(2)
	"""
	
	## adjust log level to command line option
	#logging.basicConfig(level=logging.INFO)
	logging.basicConfig(level=level)


	ranks, wins, callcount_per_opcode, opdata_per_rank, total_exec_times_per_rank, all_window_sizes_per_rank, all_window_durations_per_rank, epochs_per_window_per_rank = fp.forma_parse_traces(tracefiles)
	
	sanity_check = check_consistency(ranks, wins, opdata_per_rank)
	if sanity_check != 0:
		print(f'Warning: the present version of foRMA is intended for applications with fence-based synchronization. Detected inconsistency in the provided traces.\nTotal ranks: {ranks}')
		if sanity_check == 1:
			print("Inconsistency between provided trace files and number of ranks in application.\n")
		elif sanity_check == 2:
			print("Inconsistency in nr of windows per communicator per rank.\n")
		elif sanity_check == 3:
			print("Inconsisten nr of epochs per window across ranks.\n")
		sys.exit(2)

	#print(f'WINDOW sizes per rank: {all_window_sizes_per_rank}')

	fp.forma_calculate_dt_bounds(ranks, wins, opdata_per_rank)

	"""
	for i in range(ranks):
		print(f'opdata for RANK {i}')
		fo.forma_print_rank_ops_per_window(wins, opdata_per_rank[i])
	"""

	#print(f'Total durations: {fs.forma_calculate_stats_x6(total_exec_times_per_rank)}')

	#print(f'Total durations stats: {fs.forma_calculate_stats_manual_x6(ranks, wins, opdata_per_rank, 1)}')


	per_opcode_op_durations_per_rank, per_opcode_dt_bounds_per_rank, per_window_data_vol = fs.forma_break_down_per_rank_per_window(ranks, wins, opdata_per_rank)

	
	opdurations, windata, dtbounds = fs.forma_calc_stats_summary(ranks, wins, total_exec_times_per_rank, 
																all_window_sizes_per_rank[0], 
																all_window_durations_per_rank,
																epochs_per_window_per_rank[0], 
																per_opcode_op_durations_per_rank, 
																per_opcode_dt_bounds_per_rank, 
																per_window_data_vol)
	

	# opdurations, windata, dtbounds = fs.forma_calc_stats_summary_coarse(ranks, wins, total_exec_times_per_rank, all_window_sizes_per_rank[0], epochs_per_window_per_rank[0], opdata_per_rank)


	print("\n\n\n")


	fo.forma_print_stats_summary(ranks, wins, opdurations, windata, dtbounds, callcount_per_opcode)

	#print(all_window_durations_per_rank)
	
	while action != 'q':
		if (not cmdlnaction):
			if action == 'r':
				print('\n\n\n------------------------------------------------------------------------------------------\n' + 
				'------------------------------------ OPTIONS ---------------------------------------------\n' + 
				'------------------------------------------------------------------------------------------\n' + 
				'\te: Statistics per epoch (fence-based synchronization)\n' + 
				'\tf: Fence statistics\n' + 
				'\tc: Time spent in calls (per rank)\n' + 
				'\ta: Full analysis (i.e. all of the above)\n' + 
				'\tr: Reprint options\n' + 
				'\tq: Quit\n')
			action = input('Please select action: ')

		if action == 'q':
			sys.exit()
		elif action == 'e': #
			print('Preparing results...')
			per_epoch_stats_to_file(ranks, wins, per_window_data_vol, opdata_per_rank, all_window_durations_per_rank)
			print('Statistics per epoch (fence-based synchronization) can be found in file epochs.txt\n')
		elif action == 'f':
			print('Preparing results...')
			fence_stats_to_file(ranks, wins, per_window_data_vol, all_window_sizes_per_rank[0], opdata_per_rank)
			print('Fence statistics can be found in file fences.txt.\n')
		elif action == 'c':
			print('Preparing results...')
			per_op_durations_to_file(ranks, total_exec_times_per_rank, per_opcode_op_durations_per_rank, per_opcode_dt_bounds_per_rank)
			print('Time spent in calls (per rank), as well as data transfer bounds, can be found in file calls.txt\n')
		elif action == 'a':
			print('Preparing results...')
			per_epoch_stats_to_file(ranks, wins, per_window_data_vol, opdata_per_rank, all_window_durations_per_rank)
			fence_stats_to_file(ranks, wins, per_window_data_vol, all_window_sizes_per_rank[0], opdata_per_rank)
			per_op_durations_to_file(ranks, total_exec_times_per_rank, per_opcode_op_durations_per_rank, per_opcode_dt_bounds_per_rank)
			print('Full analysis broken down per ranks and per windows can be found in files epochs.txt, fences.txt, and calls.txt\n')
		elif action == 'r':
			pass
		else:
			print('Invalid action option!')
			action = 'r'

		if cmdlnaction:
			sys.exit()
	



if __name__ == "__main__":
	main()