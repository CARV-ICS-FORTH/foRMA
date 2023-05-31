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

import logging

import numpy as np

from pydumpi import DumpiTrace

import forma_trace as ft

from tabulate import tabulate



def forma_print_stats_x6(row_labels, row_data):

	## sanity check: are the row data of length==6?
#	if len(row_data) != 6 or len(row_labels) != 6:
#		return False

	try:
		rows = [[row_labels[i]]+row_data[i] for i in range(len(row_labels))]
	except TypeError:
		print('ERROR: forma_print_stats_x6: check row_labels and row_data types')
		sys.exit(2)

	print(f'{tabulate(rows, headers=["aggregate", "min", "max", "avg", "mean", "std dev"])}\n')
	
	return True
	

def forma_print_stats_x4(row_labels, row_data):

	try:
		rows = [[row_labels[i]]+row_data[i] for i in range(len(row_labels))]
	except TypeError:
		print('ERROR: forma_print_stats_x6: check row_labels and row_data types')
		sys.exit(2)

	print(f'{tabulate(rows, headers=["aggregate", "min", "max", "avg"])}\n')

	return True


def forma_print_timestamps_ranks(row_data):

	print(f'{tabulate([row_data], headers=["Epoch", "Earliest ts", "(rank)", "Latest ts", "(rank)", "Range"])}\n')

	return True


def forma_print_rank_stats(rank_id, total_exec_time, opduration_stats_for_rank):

	rma = sum(opduration_stats_for_rank[i][0] for i in range(4))

	print('\n------------------------------------------------------------------------------------------\n' + 
		f'RANK ID: {rank_id} \n\n' +
		f'-- Total exec. time\t:   {total_exec_time}\n' +
		f'-- Total time in RMA\t:   {rma}\n')

	print('Op durations (nsec) \n' +
		  '-------------------')

	#print(f'RANK {rank_id} Operation Durations\nTotal exec. time: {total_exec_time}\nTotal time in RMA: {rma}')
	#print(f'{tabulate([["MPI_Get"]+([0]*6), ["MPI_Put"]+([0]*6), ["MPI_Accumulate"]+([0]*6), ["MPI_Win_fence"]+([0]*6)], headers=["aggregate", "min", "max", "avg", "mean", "std dev"])}\n')
	forma_print_stats_x6(["MPI_Get", "MPI_Put", "MPI_Accumulate", "MPI_Win_fence"], opduration_stats_for_rank)
	
	return True

def forma_print_rank_dt_bounds(rank_id, dt_bounds_stats_for_rank):

	print('Data transfer bounds (nsec) \n' +
		  '---------------------------')
	forma_print_stats_x6(["MPI_Get", "MPI_Put", "MPI_Accumulate"], dt_bounds_stats_for_rank)
	
	return True


def forma_print_window_info(win_info):

	print(f'{tabulate([win_info], headers=["Size (B)", "# of epochs", "Total Bytes transferred"])}\n')

	return True


def forma_print_stats_summary(ranks, wins, opduration_stats, windata_stats, dtbound_stats, callcount_per_opcode):


	print('------------------------------------------------------------------------------------------\n' + 
		'----------------------------- EXECUTION SUMMARY ------------------------------------------\n' + 
		'------------------------------------------------------------------------------------------\n' +
		'\n' +
		f'-- # of ranks\t\t\t:   {ranks}\n' +
		f'-- # of memory windows\t\t:   {wins}\n' +
		f'-- # of MPI_Get calls\t\t:   {callcount_per_opcode[0]}\n' +
		f'-- # of MPI_Put calls\t\t:   {callcount_per_opcode[1]}\n' +
		f'-- # of MPI_Accumulate calls\t:   {callcount_per_opcode[2]}\n' +
		f'-- # of MPI_Win_fence calls\t:   {callcount_per_opcode[3]}\n' +
		'\n')


	print('------------------------------------------------------------------------------------------\n' +
	'------------------------ [Operation] Durations (nsec) ------------------------------------\n')
	forma_print_stats_x6(["Total exec. time", "Total time in RMA", "MPI_Get", "MPI_Put", "MPI_Accumulate", "MPI_Win_fence"], opduration_stats)
	
	print('------------------------------------------------------------------------------------------\n' +
	'---------------------------- Memory Windows ----------------------------------------------\n')
	forma_print_stats_x4(["Window sizes (B)", "Bytes transferred/win.", "Epochs per win.", "Window durations (nsec)"], windata_stats)

	print('------------------------------------------------------------------------------------------\n' +
	'-------------------------- Data Transfer Bounds ------------------------------------------\n')
	forma_print_stats_x4(["MPI_Get", "MPI_Put", "MPI_Accumulate"], dtbound_stats)
	
	return True



def forma_print_dtbounds_stats_for_epoch(dtbound_stats_for_epoch):

	forma_print_stats_x4(["MPI_Get", "MPI_Put", "MPI_Accumulate"], dtbound_stats_for_epoch)
	
	return True


def forma_print_opduration_stats_for_epoch(opduration_stats_for_epoch):

	forma_print_stats_x4(["MPI_Get", "MPI_Put", "MPI_Accumulate", "MPI_Win_fence"], opduration_stats_for_epoch)
	
	return True






""" the following are deprecated functions, but we are keeping them here for code snippets """


def forma_print_stats_to_files(ranks, wins):
	
	original_stdout = sys.stdout # Save a reference to the original standard output

	with open('summary.txt', 'w') as f:
	    sys.stdout = f # Change the standard output to the file we created.
	    #print('This message will be written to a file.')
	    forma_print_stats_summary(ranks, wins)

	with open('per_rank.txt', 'w') as f:
	    sys.stdout = f # Change the standard output to the file we created.
	    #print('This message will be written to a file.')
	    forma_print_stats_per_rank(ranks)

	with open('per_window.txt', 'w') as f:
	    sys.stdout = f # Change the standard output to the file we created.
	    #print('This message will be written to a file.')
	    forma_print_stats_per_window(ranks, wins)

	sys.stdout = original_stdout # Reset the standard output to its original value

	return True

def forma_print_rank_ops_per_window(wins, rank_opdata):

	for i in range(wins):
		print(f'opdata for WINDOW {i}')
		for j in range(len(rank_opdata[i])-1): # len(rank_opdata) corresponds to nr of epochs
			print(f'Epoch {j}: {rank_opdata[i][j]}')

	return True


def forma_print_stats_per_rank(ranks):

	print(f'RMA operation durations per rank -- Total ranks: {ranks}\n')

	for i in range(ranks):
		forma_print_rank_stats(i)
	return True


def forma_print_window_stats(win_id):

	epochs = 4

	print(f'WINDOW {win_id}')
	print(f'{tabulate([([0]*3)], headers=["Size (B)", "# of epochs", "Total Bytes transferred"])}\n')
	for j in range(epochs):
		print(f'{tabulate([[j]+[0]*5], headers=["Epoch", "Earliest ts", "(rank)", "Latest ts", "(rank)", "Range"])}\n')
		print(f'Arrival order: {[0]*4}\n')

	return True


def forma_print_stats_per_window(ranks, wins):

	epochs = 4

	print(f'Data transfer bounds per window -- Total ranks: {ranks} -- Total windows: {wins}\n')

	for i in range(wins):
		forma_print_window_stats(i)

	return True
