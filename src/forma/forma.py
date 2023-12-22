#!/usr/bin/env python3



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

import pydumpi as pd

import forma_trace as ft
import forma_parse as fp
import forma_stats as fs
# import forma_prints as fo
import forma_aux as fa
import forma_classes as fc
import forma_logging as fl
from forma_constants import *
import forma_config as fg

import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter

from contextlib import redirect_stderr

rma_tracked_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence']
#logger = fa.setup_forma_logger(logging.DEBUG)

def main():

	fl.forma_intro()
	fl.forma_print('Preparing analysis of trace.')

	global dirname, timestamp


	## user interaction initializations ##
	action = 'p'
	cmdln_mode = False

	log_level = logging.INFO
	# fl.forma_logger.info('INITIALLY: INFO LEVEL')
	

	## set up how foRMA has to be invoked ...
	forma_arg_parse = argparse.ArgumentParser(description="foRMA -- a methodology and a tool for profiling MPI RMA operation timing, designed to process traces produced by SST Dumpi.")
	forma_arg_parse.add_argument("directory", help="Specifies the path to the directory in which the tracefiles to be parsed are located.", type=str)
	forma_arg_parse.add_argument("timestamp", help="Specifies the timestamp that makes up the filenames of the tracefiles to be parsed.", type=str)
	forma_arg_parse.add_argument("-d", "--debug", help="Turns on debug messages and is meant to be used for developing the tool and not when using it to profile traces.",
                    action="store_true")
	forma_arg_parse.add_argument("-s", "--summary", help="When specified, foRMA only produces a summary of statistics and exits without offering the interactive prompt.", action="store_true")
	forma_arg_parse.add_argument("-t", "--transfers", help="When specified, foRMA also produces a summary of data transfer bounds statistics while parsing the tracefiles.", action="store_true")
	forma_arg_parse.add_argument("-a", "--all", help="Produce full analysis broken down per ranks and per windows, output to files epochs.txt, fences.txt, and calls.txt in directory forma_out/. Equivalent to -c -e -f.", action="store_true")
	forma_arg_parse.add_argument("-c", "--calls", help="Output time spent in calls (per rank), as well as data transfer bounds, in file forma_out/calls.txt.", action="store_true")
	forma_arg_parse.add_argument("-e", "--epochs", help="Produce statistics per epoch (fence-based synchronization), output to file forma_out/epochs.txt", action="store_true")
	forma_arg_parse.add_argument("-f", "--fences", help="Produce fence statistics, output to file forma_out/fences.txt.", action="store_true")
	forma_arg_parse.add_argument("-m", "--meta", help="Access submenu that works on SST Dumpi meta-data for the trace.", action="store_true")


	## ... and get the required parameters from the command-line arguments
	args = forma_arg_parse.parse_args()
	dirname = args.directory
	timestamp = args.timestamp
	cmdln_mode = args.summary
	# dt_summary = args.transfers
	fg.transfers = args.transfers


	if args.debug:
		log_level = logging.DEBUG
		fl.set_forma_loglevel(fl.forma_logger, log_level)


	## check whether the given input corresponds to valid trace files
	fl.forma_logger.debug(f'debug level is {log_level}.')
	fl.forma_logger.debug(f'Directory name is : {dirname}')
	fl.forma_logger.debug(f'Timestamp is {timestamp}')

	tracefiles = fa.check_filepaths(dirname, timestamp)
	if tracefiles == None:
		fl.forma_print('No trace files found. Exiting.\n')
		sys.exit(-1)



	metafile =  format(str(dirname))+'/'+format(str('dumpi-'+format(str(timestamp))+'.meta'))
	keyvals = pd.util.read_meta_file(metafile)

	for key, val in keyvals.items():
		fl.forma_print(f'Key {key} has value {val}')


	for rank, tracefile in enumerate(tracefiles):
		with ft.FormaSTrace(tracefile, rank) as trace:
			fl.forma_print(f'Now parsing {tracefile}.\n')

			trace.print_footer()
	#return


################ Stage #0 ends here ########################################

	#os.system("exec 2> /dev/null")
	exec_summary = fp.forma_parse_traces(tracefiles)
	#os.system("exec 2>1")

	total_callbacks = np.sum(exec_summary.callcount_per_opcode)
	if total_callbacks == 0:
		fl.forma_error('Zero callbacks detected. Make sure you are using well-formatted SST Dumpi output files.')
		sys.exit(1)
	total_rmas = exec_summary.callcount_per_opcode[GET]+exec_summary.callcount_per_opcode[PUT]+exec_summary.callcount_per_opcode[ACC]
	if total_rmas== 0:
		fl.forma_error('Zero RMA callbacks detected. Make sure you are profiling traces of an RMA-based application.')
		sys.exit(1)
	rma_pc = round((total_rmas/total_callbacks)*100, 2)
	total_synch = exec_summary.callcount_per_opcode[FENCE]
	synch_pc = round((total_synch/total_callbacks)*100, 2)
	total_win = exec_summary.callcount_per_opcode[WIN_CR]+exec_summary.callcount_per_opcode[WIN_FREE]
	if exec_summary.callcount_per_opcode[WIN_CR] != exec_summary.callcount_per_opcode[WIN_FREE]:
		fl.forma_error('Discrepancy between MPI_Win_create/MPI_Win_free call counts. Make sure you are using well-formatted SST Dumpi output files.')
		sys.exit(1)
	if total_win== 0:
		fl.forma_error('Zero MPI_Win_create detected. Currently, foRMA only supports MPI_Win_create/MPI_Win_free -based window creation.')
		sys.exit(1)
	win_pc = round((total_win/total_callbacks)*100, 2)

	fl.forma_print(f'Handled {total_callbacks} callbacks during the parsing of {exec_summary.ranks} trace files.\n' +
		f'\t    Out of those, {total_rmas} (i.e. {rma_pc}% of callbacks) refer to remote memory accesses.\n' +
		f'\t    Out of those, {total_synch} (i.e. {synch_pc}% of callbacks) refer to fence synchronization.\n'+
		f'\t    Out of those, {total_win} (i.e. {win_pc}% of callbacks) refer to window creation/destruction.\n')

	exec_summary.print_summary()

	if not os.path.exists('./forma_out/'):
		os.mkdir('./forma_out/')



################ Stage-independent #########################################
	
	while action != 'q':
		if (not cmdln_mode):
			if action == 'p':
				print('\n\n\n------------------------------------------------------------------------------------------\n' + 
				'------------------------------------ OPTIONS ---------------------------------------------\n' + 
				'------------------------------------------------------------------------------------------\n' + 
				'\te: Statistics per epoch (fence-based synchronization)\n' + 
				'\tf: Fence statistics\n' + 
				'\tc: Per rank summaries to file (time spent in calls, data transfer bounds per rank)\n' + 
				'\tr: Print summary for specific rank\n' + 
				'\ta: Full analysis (i.e. all of the above)\n' + 
				'\tp: Reprint options\n' + 
				'\tq: Quit\n')
			action = input('Please select action: ')

		if action == 'q':
			sys.exit()
		elif action == 'e': #
			fl.forma_print('Preparing results...')
			err = fa.forma_aggregate_epoch_files(exec_summary.ranks)
			if err == 2:
				fl.forma_error('Window ID discrepancy among files. Make sure you are using well-formatted SST Dumpi output files.')
				sys.exit(2)
			fl.forma_print('Statistics per epoch (fence-based synchronization) can be found in file forma_out/epochs.txt\n')
		elif action == 'f':
			fl.forma_print('Output not yet fully supported by current foRMA version. Please find intermediate results in file(s) ./forma_meta/epochs-<rank ID>.avro. ')
			# fl.forma_print('Preparing results...')
			# err = fa.forma_aggregate_fence_arrivals(exec_summary.ranks)
			# if err == 2:
			# 	fl.forma_error('Window ID discrepancy among files. Make sure you are using well-formatted SST Dumpi output files.')
			# 	sys.exit(2)
			# fl.forma_print('Fence statistics can be found in file forma_out/fences.txt.\n')
		elif action == 'c':
			fl.forma_print('Preparing results...')
			rank_summary = fc.formaSummary()
			schema = avro.schema.parse(open("../schemas/summary.avsc", "rb").read())
			reader = DataFileReader(open("forma_meta/rank_summaries.avro", "rb"), DatumReader(schema))
			original_stdout = sys.stdout # Save a reference to the original standard output
			with open('forma_out/calls.txt', 'w') as f:
				sys.stdout = f # Change the standard output to the file we created.
				for rid, summary in enumerate(reader):
					rank_summary.set_from_dict(summary)
					rank_summary.print_summary()
				reader.close()
			sys.stdout = original_stdout # Reset the standard output to its original value
			fl.forma_print('Time spent in calls (per rank), as well as data transfer bounds, can be found in file forma_out/calls.txt\n')
		elif action == 'r':
			try:
				rank_id = int(input(f'Please select rank ID [0 - {exec_summary.ranks-1}]: '))
				# if rank_input.isnumeric():
				#     rank_id = int(rank_input)
			except ValueError:
				#if isinstance(rank_input, (str)):
				fl.forma_error('Invalid rank ID!')
				continue
			if rank_id not in range(0, exec_summary.ranks):
			    fl.forma_error('Invalid rank ID!')
			    continue
			fl.forma_print(f'Summary for rank {rank_id}\n')
			rank_summary = fc.formaSummary()
			schema = avro.schema.parse(open("../schemas/summary.avsc", "rb").read())
			reader = DataFileReader(open("forma_meta/rank_summaries.avro", "rb"), DatumReader(schema))
			for rid, summary in enumerate(reader):
				if rid == rank_id:
					rank_summary.set_from_dict(summary)
					#print(summary)
					rank_summary.print_summary()
			reader.close()
		elif action == 'a':
			fl.forma_print('Preparing results...')
			original_stdout = sys.stdout # Save a reference to the original standard output

			rank_summary = fc.formaSummary()
			schema = avro.schema.parse(open("../schemas/summary.avsc", "rb").read())
			reader = DataFileReader(open("forma_meta/rank_summaries.avro", "rb"), DatumReader(schema))
			with open('forma_out/calls.txt', 'w') as f:
				sys.stdout = f # Change the standard output to the file we created.
				for rid, summary in enumerate(reader):
					rank_summary.set_from_dict(summary)
					rank_summary.print_summary()
				reader.close()

			with open('forma_out/epochs.txt', 'w') as f:
				sys.stdout = f # Change the standard output to the file we created.

				epoch_summary = fc.epochSummary()
				schema = avro.schema.parse(open("../schemas/summary.avsc", "rb").read())
				for rank_id in range(0, exec_summary.ranks):
					epochsumfile = "./forma_meta/epochs-"+str(rank_id)+".avro"
					reader = DataFileReader(open(epochsumfile, "rb"), DatumReader(schema))
					for rid, summary in enumerate(reader):
						epoch_summary.set_from_dict(summary)
						epoch_summary.print_summary()
					reader.close()
				fa.forma_aggregate_epoch_files(exec_summary.ranks)

			with open('forma_out/fences.txt', 'w') as f:
				sys.stdout = f # Change the standard output to the file we created.
				
			sys.stdout = original_stdout # Reset the standard output to its original value
			#fl.forma_print('Full analysis broken down per ranks and per windows can be found in files epochs.txt, fences.txt, and calls.txt\n')
			fl.forma_print('Full analysis broken down per ranks and per windows can be found in files epochs.txt and calls.txt in directory forma_out/\n')
		elif action == 'p':
			pass
		else:
			fl.forma_print('Invalid action option!')
			action = 'r'

		if cmdln_mode:
			sys.exit()
	



if __name__ == "__main__":
	main()
