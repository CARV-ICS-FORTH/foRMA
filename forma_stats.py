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
# import forma_prints as fo
import forma_classes as fc
import forma_logging as fl
from forma_constants import *


""" The following function should be used to update 
the min, max, and aggregate values of a stream of 
values. The current values of those metrics are in 
current_vals, new_val is the next value in the stream. 
The function is 'stream-agnostic', so to speak. """

def forma_streaming_stats_x3(current_vals, new_val):

	## update min
	if current_vals[MIN] > new_val or current_vals[MIN] == 0:
		#new_min = new_val
		current_vals[MIN] = new_val
	# else:
	# 	new_min = current_vals[MIN]

	## update max
	# if current_vals[MAX] > new_val:
	# 	new_max = current_vals[MAX]
	# else:
	if current_vals[MAX] < new_val:
		current_vals[MAX] = new_val

	## update aggregate
	#new_agr = current_vals[AGR] + new_val
	current_vals[AGR] += new_val

	#return new_min, new_max, new_agr



def forma_static_stats_x4(values_vector, stats_vector):

	# output_stats = []

	# if values_vector == []:
	# 	output_stats = [0]*4
	# else:
	# 	output_stats.append(min(values_vector))
	# 	output_stats.append(max(values_vector))
	# 	output_stats.append(output_stats[0]/len(values_vector))
	# 	output_stats.append(sum(values_vector))

	# return output_stats
	stats_vector[MIN] = min(values_vector)
	stats_vector[MAX] = max(values_vector)
	stats_vector[AGR] = sum(values_vector)
	stats_vector[AVG] = stats_vector[AGR] / len(values_vector)




def forma_merge_stats_x4(current_stats, new_stats):

	if current_stats[MIN] > new_stats[MIN] or current_stats[MIN] == 0:
	#new_min = new_val
		if new_stats[MIN] != 0:
			current_stats[MIN] = new_stats[MIN]
	# else:
	# 	new_min = current_stats[MIN]

	## update max
	# if current_stats[MAX] > new_val:
	# 	new_max = current_stats[MAX]
	# else:
	if current_stats[MAX] < new_stats[MAX]:
		current_stats[MAX] = new_stats[MAX]

	## update aggregate
	#new_agr = current_stats[AGR] + new_val
	current_stats[AGR] += new_stats[AGR]
