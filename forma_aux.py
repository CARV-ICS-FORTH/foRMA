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

import numpy as np

import logging

from pydumpi import DumpiTrace
from pydumpi import util


import forma_logging as fl



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
	total_file_size = total_file_size/1024
	fl.forma_print(f'About to parse a total of {round(total_file_size)} KBytes of binary trace files size.\n')

	## Read metafile and print it -- TODO: to be used more extensively later
	try:
		metafile = util.read_meta_file(str(dirname)+'/dumpi-'+format(str(timestamp))+'.meta')
	except FileNotFoundError:
		fl.forma_print('.meta file not found. Check directory name and timestamp formatting.\n')
		#sys.exit(1)
		return None


	return(ordered_files)