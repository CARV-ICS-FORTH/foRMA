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


# import forma_trace as ft
import forma_parse as fp
# import forma_stats as fs
# import forma_prints as fo
import forma_aux as fa
import forma_classes as fc
import forma_logging as fl


rma_tracked_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence']
#logger = fa.setup_forma_logger(logging.DEBUG)

def main():

	fl.forma_intro()
	fl.forma_print('Preparing analysis of trace.')

	global dirname, timestamp


	## user interaction initializations ##
	action = 'r'
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
	forma_arg_parse.add_argument("-a", "--all", help="Produce full analysis broken down per ranks and per windows, output to files epochs.txt, fences.txt, and calls.txt. Equivalent to -c -e -f.", action="store_true")
	forma_arg_parse.add_argument("-c", "--calls", help="Output time spent in calls (per rank), as well as data transfer bounds, in file calls.txt.", action="store_true")
	forma_arg_parse.add_argument("-e", "--epochs", help="Produce statistics per epoch (fence-based synchronization), output to file epochs.txt", action="store_true")
	forma_arg_parse.add_argument("-f", "--fences", help="Produce fence statistics, output to file fences.txt.", action="store_true")


	## ... and get the required parameters from the command-line arguments
	args = forma_arg_parse.parse_args()
	dirname = args.directory
	timestamp = args.timestamp
	cmdln_mode = args.summary

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



################ Stage #0 ends here ########################################

	exec_summary = fp.forma_parse_traces(tracefiles)

	exec_summary.print_summary()



################ Stage-independent #########################################
	
	while action != 'q':
		if (not cmdln_mode):
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
			print('Statistics per epoch (fence-based synchronization) can be found in file epochs.txt\n')
		elif action == 'f':
			print('Preparing results...')
			print('Fence statistics can be found in file fences.txt.\n')
		elif action == 'c':
			print('Preparing results...')
			print('Time spent in calls (per rank), as well as data transfer bounds, can be found in file calls.txt\n')
		elif action == 'a':
			print('Preparing results...')
			print('Full analysis broken down per ranks and per windows can be found in files epochs.txt, fences.txt, and calls.txt\n')
		elif action == 'r':
			pass
		else:
			print('Invalid action option!')
			action = 'r'

		if cmdln_mode:
			sys.exit()
	



if __name__ == "__main__":
	main()




##############################################################################
## Remnant code from previous versions, kept just in case
##############################################################################


	## main had a getopt way of obtaining command line parameters and options

	# try: 
	# 	if len(argv) < 4 or len(argv) > 6:
	# 		fl.forma_print('Input Error! Usage is: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -l <log level> ]')
	# 		sys.exit(2)
	# 	else:
	# 		opts, args = getopt.getopt(argv, 'd:t:l:')
	# 		for o, a in opts:
	# 			if o == "-d ": 
	# 				dirname = a
	# 			elif o == "-t ":
	# 				timestamp = a
	# 			elif o == "-l ":
	# 				log_level=fl.get_log_level(a)
	# 				if log_level is None:
	# 					raise fl.FormaValueError()
	# 				else:
	# 					fl.set_forma_loglevel(fl.forma_logger, log_level)
	# 			else: 
	# 				assert False, "No such command-line option!"
	# 				sys.exit(2)

	# except getopt.GetoptError as err:
	# 	fl.forma_print(f'Exception: {err}. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -l <log level> ] instead')
	# 	sys.exit()

	# except fl.FormaValueError:
	# 	fl.forma_print('No such logging level. Must be one of: {critical, error, warn, warning, info, debug}. Continuing with logging level set to INFO.')
	# 	# sys.exit(2)
