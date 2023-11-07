

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
__version__ = "0.1.0"


import sys 
import glob, os
import re
import fnmatch

import numpy as np

import logging

from pydumpi import DumpiTrace
from pydumpi import util


import forma_logging as fl
import forma_classes as fc

import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter

def check_filepaths(dirname, timestamp):

	try:
		ordered_files_all = sorted(os.listdir(format(str(dirname))))
	except FileNotFoundError:
		fl.forma_print('Directory not found or empty. Check provided directory name (-d option).\n')
		return None 

	ordered_files = []
	ordered_ascii_files = []

	total_file_size = 0

	for filename in ordered_files_all:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			filepath = format(str(dirname))+'/'+format(str(filename))

			total_file_size = total_file_size + os.path.getsize(filepath)

			ordered_files.append(filepath)

	if ordered_files == []:
		fl.forma_print('Trace files not found. Check timestamp formatting (-t option).\n')
		return None

	#print(ordered_files)
	total_file_size = round(total_file_size/1024)
	if total_file_size == 0:
		fl.forma_print('Trace file size is 0. Make sure that you are using well-formatted SST Dumpi output files.')
		sys.exit(2)
	fl.forma_print(f'About to parse a total of {total_file_size} KBytes of binary trace files size.\n')

	## Read metafile and print it -- TODO: to be used more extensively later
	try:
		metafile = util.read_meta_file(str(dirname)+'/dumpi-'+format(str(timestamp))+'.meta')
	except FileNotFoundError:
		fl.forma_print('.meta file not found. Check directory name and timestamp formatting.\n')
		#sys.exit(1)
		return None


	return(ordered_files)


def forma_aggregate_epoch_files(rank_nr):
	epoch_count = -1
	epoch_summary = fc.epochSummary()
	schema = avro.schema.parse(open("schemas/summary.avsc", "rb").read())
	epochfiles = []
	readers = []
	offsets = []
	epoch_cnt = 0
	curr_lines = 0
	for rank_id in range(0, rank_nr):
		epochsumfile = "./forma_meta/epochs-"+str(rank_id)+".avro"
		epochfiles.append(epochsumfile)
		readers.append(DataFileReader(open(epochsumfile, "rb"), DatumReader(schema)))
		next(readers[rank_id])
		# offsets.append(1)
		# if epoch_cnt == 0:
		# 	epoch_cnt = sum(1 for line in readers[rank_id])
		# 	curr_lines = epoch_cnt
		# else:
		# 	curr_lines = sum(1 for line in readers[rank_id])
		# fl.forma_logger.debug(f'Current rank is {rank_id}, line count is {curr_lines}')
		# fl.forma_logger.debug(f'Current lines {curr_lines}, Epoch count {epoch_cnt}')
		# if curr_lines != epoch_cnt: 
		# 	fl.forma_error('Total epoch count discrepancy. Make sure you are using well-formatted SST Dumpi output files.')
		# 	sys.exit(2)
		#readers[rank_id].close()
		# next(readers[rank_id])

	keep_reading = True
	curr_win = 0
	prev_win = -1
	rank_win = 0
	prev_rank_win = 0
	original_stdout = sys.stdout # Save a reference to the original standard output
	with open('epochs.txt', 'w') as f:
		sys.stdout = f # Change the standard output to the file we created.
		aggregate_epoch_summary = fc.epochSummary()
		while(keep_reading):
			for rank_id in range(0, rank_nr):
				# check for window concordance
				#readers[rank_id].reader.seek(offsets[rank_id])
				try:
					summary = next(readers[rank_id])
				except StopIteration:
					keep_reading = False
					break
				epoch_summary.set_from_dict(summary)

				rank_win = epoch_summary.win_id
				if rank_win != prev_rank_win:
					# handle error at higher level
					# fl.forma_error('Window ID discrepancy among files. Make sure you are using well-formatted SST Dumpi output files.')
					sys.stdout = original_stdout # Reset the standard output to its original value
					return 2

				aggregate_epoch_summary += epoch_summary
				aggregate_epoch_summary.set_averages()
				# print(f'Rank {rank_id} epoch summary: {summary}')
				prev_rank_win = rank_win

			if keep_reading == False:
				break

			curr_win = rank_win
			# check for window change
			if curr_win != prev_win:
				print('------------------------------------------------------------------------------------------\n' + 
					f'-------------------------------- WINDOW {curr_win} ---------------------------------------------\n' + 
					'------------------------------------------------------------------------------------------\n')
			aggregate_epoch_summary.print_summary()
			prev_win = curr_win
	sys.stdout = original_stdout # Reset the standard output to its original value
	return 0