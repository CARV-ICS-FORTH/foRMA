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

def forma_print_timestamps_ranks():
	return True


def forma_print_rank_stats(rank_id):

	total = 0
	rma = 0

	print(f'RANK {rank_id} Operation Durations\nTotal exec. time: {total}\nTotal time in RMA: {rma}')
	print(f'{tabulate([["MPI_Get"]+([0]*6), ["MPI_Put"]+([0]*6), ["MPI_Accumulate"]+([0]*6), ["MPI_Win_fence"]+([0]*6)], headers=["aggregate", "min", "max", "avg", "mean", "std dev"])}\n')


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


def forma_print_stats_summary(ranks, wins):

	
	print(f'Total ranks: {ranks}\nTimes in ns')
	
	print('Operation Durations')
	forma_print_stats_x6(["Total exec. time", "Total time in RMA", "MPI_Get", "MPI_Put", "MPI_Accumulate", "MPI_Win_fence"], [[6, 6, 6, 6, 6, 6]]*6)
	
	print(f'Memory Windows: {wins}')
	forma_print_stats_x4(["Size (B)", "Bytes transferred/win.", "Epochs per win."], [[4, 4, 4, 4]]*3)

	print('Data Transfer Bounds')
	forma_print_stats_x6(["MPI_Get", "MPI_Put", "MPI_Accumulate"], [[6, 6, 6, 6, 6, 6]]*3)
	
	return True


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