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


def setup_forma_logger(level):
	forma_logger = logging.getLogger(':: foRMA debug info')
	forma_logger.setLevel(level)

	ch = logging.StreamHandler()
	ch.setLevel(level)


	formatter = logging.Formatter('\n%(name)s - %(filename)s::%(lineno)d - %(levelname)s :: %(message)s')

	ch.setFormatter(formatter)

	forma_logger.addHandler(ch)

	return forma_logger


def set_forma_loglevel(logger, level):
	logger.setLevel(level)
	for handler in logger.handlers:
		handler.setLevel(level)
	return


forma_logger = setup_forma_logger(logging.INFO)
#forma_logger.info('Logger initialized.')


def forma_print(message):
	print('\nfoRMA info: ' + message)	
	return


def forma_error(message):
	print('\nfoRMA ERROR: ' + message)	
	return



def forma_intro():

	try:	
		f=open ('forma-banner.txt','r')
	except OSError as e:
		print('\n\n.: foRMA: RMA Profiling for MPI :.\n\n')
		return
		
	print(''.join([line for line in f]))