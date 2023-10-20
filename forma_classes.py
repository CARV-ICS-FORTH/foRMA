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


import sys 
import glob, os
import re
import fnmatch

import numpy as np

import logging

from pydumpi import DumpiTrace
from pydumpi import util

import forma_logging as fl
import forma_stats as fs
import forma_prints as fp
from forma_constants import *

class formaSummary:

	def __init__(self):

		self.initialized	= 0
		self.wins 			= 0
		self.ranks 			= 0
		self.exectime		= np.zeros(6, dtype=float)		# total execution time of process -- providing for the case where this is used as execution summary
		self.rmatime		= np.zeros(6, dtype=float)		# total time spent in RMA ops (put, get and acc) -- same as above
		self.callcount_per_opcode	= np.zeros(6, dtype=int)
		self.xfer_per_opcode		= np.zeros((3, 4), dtype=float)	# 4 statistics for transfer sizes, tracking 5 opcodes
		self.opdurations	= np.zeros((5, 6), dtype=float)	# tracking 5 opcodes, 6 statistics for each
		self.dtbounds		= np.zeros((5, 6), dtype=float)	#  -"-
		self.winsizes		= np.zeros(4, dtype=float)	# 4 statistics for window sizes
		self.xfer_per_win	= np.zeros(4, dtype=float)	# 4 statistics for total bytes transferred 
		self.epochs			= np.zeros(4, dtype=float)	# 4 statistics for epochs per window
		self.windurations	= np.zeros(4, dtype=float)	# 4 statistics for window lifetime durations


	def set_from_dict(self, dict):

		self.initialized	= 0
		self.wins 			= dict['wins']
		self.ranks 			= dict['rank_nr']
		self.exectime		= dict['total_exec_times']
		self.rmatime		= dict['total_rma_times']
		self.callcount_per_opcode[GET]	= dict['mpi_gets']
		self.callcount_per_opcode[PUT]	= dict['mpi_puts']
		self.callcount_per_opcode[ACC]	= dict['mpi_accs']
		self.callcount_per_opcode[FENCE]	= dict['mpi_fences']
		self.xfer_per_opcode	= np.zeros((3, 4), dtype=float)	# 4 statistics for transfer sizes, tracking 5 opcodes
		self.opdurations[GET]	= dict['mpi_get_times']
		self.opdurations[PUT]	= dict['mpi_put_times']
		self.opdurations[ACC]	= dict['mpi_acc_times']
		self.opdurations[FENCE]	= dict['mpi_fence_times']
		self.dtbounds[GET]	= dict['mpi_get_dtb']
		self.dtbounds[PUT]	= dict['mpi_put_dtb']
		self.dtbounds[ACC]	= dict['mpi_acc_dtb']
		self.winsizes		= dict['window_sizes']
		self.xfer_per_win	= dict['tf_per_win']
		self.epochs			= dict['epochs_per_win']
		self.windurations	= dict['win_durations']

	def __iadd__(self, other):

		if not self.initialized: 
			self.wins = other.wins
			self.winsizes = other.winsizes
			self.epochs = other.epochs
			self.initialized = 1

		if self.wins != other.wins:
			fl.forma_logger.warning(f'Discrepancy of # of memory windows among processes. Are you profiling MPI_Win_fence-based executions?')
			sys.exit(1)

		for metric in range(len(self.winsizes)):
			if self.winsizes[metric] != other.winsizes[metric]:
				fl.forma_logger.warning(f'Discrepancy of # of memory window sizes among processes. Are you profiling MPI_Win_fence-based executions?')
				sys.exit(1)
			if self.epochs[metric] != other.epochs[metric]:
				fl.forma_logger.warning(f'Discrepancy of # of memory window epochs among processes. Are you profiling MPI_Win_fence-based executions?')
				sys.exit(1)

		self.ranks += other.ranks

		fs.forma_merge_stats_x4(self.exectime, other.exectime)
		fs.forma_merge_stats_x4(self.rmatime, other.rmatime)

		self.callcount_per_opcode += other.callcount_per_opcode

		for opcode in (GET, PUT, ACC, FENCE):
			if opcode != FENCE:
				fs.forma_merge_stats_x4(self.xfer_per_opcode[opcode], other.xfer_per_opcode[opcode])
				fs.forma_merge_stats_x4(self.dtbounds[opcode], other.dtbounds[opcode])
			fs.forma_merge_stats_x4(self.opdurations[opcode], other.opdurations[opcode])

		#fs.forma_merge_stats_x4(self.winsizes, other.winsizes)
		# for opcode in (GET, PUT, ACC):
		# 	fs.forma_merge_stats_x4(self.xfer_per_win[opcode], other.xfer_per_win[opcode])
		fs.forma_merge_stats_x4(self.xfer_per_win, other.xfer_per_win)
		#fs.forma_merge_stats_x4(self.epochs, other.epochs)
		fs.forma_merge_stats_x4(self.windurations, other.windurations)

		return self


	def set_averages(self):

		for opcode in (GET, PUT, ACC, FENCE):
			if self.callcount_per_opcode[opcode] != 0:
				if opcode != FENCE:
					self.xfer_per_opcode[opcode][AVG] = self.xfer_per_opcode[opcode][AGR] / self.callcount_per_opcode[opcode]
					self.dtbounds[opcode][AVG] = self.dtbounds[opcode][AGR] / self.callcount_per_opcode[opcode]
				self.opdurations[opcode][AVG] = self.opdurations[opcode][AGR] / self.callcount_per_opcode[opcode]

		
		self.xfer_per_win[AVG] = self.xfer_per_win[AGR] / (sum([self.callcount_per_opcode[opcode] for opcode in (GET, PUT, ACC)]))

		if self.wins != 0:
			self.winsizes[AVG] = self.winsizes[AGR] / self.wins ## not sure it's correctly calculated 
			self.epochs[AVG] = self.epochs[AGR] / self.wins ## not sure it's correctly calculated 
			self.windurations[AVG] = self.windurations[AGR] / (self.wins*self.ranks) # is that the right way?

		self.exectime[AVG] = self.exectime[AGR] / self.ranks
		self.rmatime[AVG] = self.rmatime[AGR] / self.ranks




	def print_summary(self):
		print('------------------------------------------------------------------------------------------\n' + 
		'----------------------------- EXECUTION SUMMARY ------------------------------------------\n' + 
		'------------------------------------------------------------------------------------------\n' +
		'\n' +
		f'-- # of ranks\t\t\t:   {self.ranks}\n' +
		f'-- # of memory windows\t\t:   {self.wins}\n' +
		f'-- # of MPI_Get calls\t\t:   {self.callcount_per_opcode[GET]}\n' +
		f'-- # of MPI_Put calls\t\t:   {self.callcount_per_opcode[PUT]}\n' +
		f'-- # of MPI_Accumulate calls\t:   {self.callcount_per_opcode[ACC]}\n' +
		f'-- # of MPI_Win_fence calls\t:   {self.callcount_per_opcode[FENCE]}\n' +
		'\n')


		## if we use forma_print_stats_x6, which is a function written for a previous version 
		## of foRMA, we have to convert numpy arrays to list of lists, for backwards compatibility.
		## this is why variables overalls, winstats, and dtbounds_stats, as well as method tolist()
		## are necessary 
		overalls = np.stack((self.exectime, self.rmatime))
		print('------------------------------------------------------------------------------------------\n' +
		'------------------------ [Operation] Durations (nsec) ------------------------------------\n')
		fp.forma_print_stats_x6(["Total exec. time", "Total time in RMA", "MPI_Get", "MPI_Put", "MPI_Accumulate", "MPI_Win_fence"], (np.concatenate((overalls, self.opdurations[0:4]))).tolist())


		winstats = np.stack((self.winsizes, self.xfer_per_win, self.epochs, self.windurations))
		print('------------------------------------------------------------------------------------------\n' +
		'---------------------------- Memory Windows ----------------------------------------------\n')
		fp.forma_print_stats_x4(["Window sizes (B)", "Bytes transferred/win.", "Epochs per win.", "Window durations (nsec)"], winstats.tolist())

		dtbounds_stats = []
		for i in range(len(self.dtbounds)):
			dtbounds_stats.append((self.dtbounds[i][0:4]).tolist())
		print('------------------------------------------------------------------------------------------\n' +
		'-------------------------- Data Transfer Bounds ------------------------------------------\n')
		fp.forma_print_stats_x4(["MPI_Get", "MPI_Put", "MPI_Accumulate"], dtbounds_stats)
		
		return True




class epochSummary:

	def __init__(self):

		self.initialized	= 0
		self.win_id			= 0
		self.epoch_nr		= 0
		self.callcount_per_opcode	= np.zeros(3, dtype=int) 	# tracking 3 opcodes
		self.opdurations	= np.zeros((3, 4), dtype=float)	# tracking 3 opcodes, 4 statistics for each
		self.xfer_per_opcode	= np.zeros(3, dtype=float)	# 4 statistics for transfer sizes, tracking 3 opcodes
		self.dtbounds		= np.zeros((3, 6), dtype=float)	#  -"-

	def reset(self):
		self.initialized	= 0
		self.win_id			= 0
		self.epoch_nr		= 0
		self.callcount_per_opcode	= np.zeros(3, dtype=int) 	# tracking 3 opcodes
		self.opdurations	= np.zeros((3, 4), dtype=float)	# tracking 3 opcodes, 4 statistics for each
		self.xfer_per_opcode	= np.zeros(3, dtype=float)	# 4 statistics for transfer sizes, tracking 3 opcodes
		self.dtbounds		= np.zeros((3, 6), dtype=float)	#  -"-

	def set_from_dict(self, dict):
		self.win_id			= dict["win_id"]
		self.epoch_nr		= dict["epoch_nr"]
		self.callcount_per_opcode[GET]	= dict["mpi_gets"]
		self.callcount_per_opcode[PUT]	= dict["mpi_puts"]
		self.callcount_per_opcode[ACC]	= dict["mpi_accs"]
		self.opdurations[GET]	= dict["mpi_get_times"]
		self.opdurations[PUT]	= dict["mpi_put_times"]
		self.opdurations[ACC]	= dict["mpi_acc_times"]
		self.xfer_per_opcode	= dict["tf_per_op"]
		self.dtbounds[GET]		= dict["mpi_get_dtb"]
		self.dtbounds[PUT]		= dict["mpi_put_dtb"]
		self.dtbounds[ACC]		= dict["mpi_acc_dtb"]