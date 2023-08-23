#!/usr/bin/python3


__all__ = ["forma"]
__author__ = "Lena Kanellou"
__version__ = "0.1.1"



import getopt 
import sys 
import glob, os
import re
import fnmatch

import ctypes

# import avro.schema
# from avro.datafile import DataFileReader, DataFileWriter
# from avro.io import DatumReader, DatumWriter
# from fastavro import reader

import logging

from pydumpi import dtypes
from pydumpi import DumpiTrace

import forma_classes as fc
import forma_logging as fl
import forma_stats as fs
from forma_constants import *


## foRMA in-memory (IM) trace, one of the versions of the callback 
## implementations where all opdata are kept in dedicated vectors and 
## statistics are calculated a posteriori

class FormaSTrace(DumpiTrace):

	def __init__(self, file_name): #, csv_filename, pickle_filename, parquet_filename):
		super().__init__(file_name)
		
		self.trace_summary = fc.formaSummary()
		#self.trace_summary.setRanks(1)
		

		## Window metrics are indexed by window ID but something strange is going on with 
		## sst dumpi window id numbers, so I'm using a window id lookaside translation buffer
		self.win_count = 0
		self.wintb = dict()

		## based on the above, the following are indexed by win_id, which is the value of 
		## wintb when the key is data.win
		self.epochcount_per_window = []
		self.data_xfer_per_window = []
		self.lifetime_of_window = []


	def on_init(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		
		#self.total_exec_time = cpu_time.start.to_ns()
		#self.total_exec_time = wall_time.start.to_ns()

		#self.callcount_per_opcode[6] = self.callcount_per_opcode[6] + 1

		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		self.trace_summary.exectime[0] = wall_time.start.to_ns()
		self.trace_summary.ranks += 1 


	def on_finalize(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start

		#self.total_exec_time = cpu_time.stop.to_ns()- self.total_exec_time
	#	self.total_exec_time = wall_time.stop.to_ns()- self.total_exec_time
		#self.trace_summary.setExectime(self.total_exec_time)

		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		total_exec_time = wall_time.stop.to_ns() - self.trace_summary.exectime[0]
		self.trace_summary.exectime.fill(total_exec_time)

		## Window metrics have not been calculated as streaming, so produce them here statically:

		#self.trace_summary.xfer_per_opcode	= np.zeros((5, 4), dtype=float)	# 4 statistics for transfer sizes, tracking 5 opcodes
		# self.trace_summary.epochs = fs.forma_static_stats_x4(self.epochcount_per_window)
		# self.trace_summary.windurations	= fs.forma_static_stats_x4(self.lifetime_of_window)
		fs.forma_static_stats_x4(self.epochcount_per_window, self.trace_summary.epochs)
		fs.forma_static_stats_x4(self.lifetime_of_window, self.trace_summary.windurations)
		fs.forma_static_stats_x4(self.data_xfer_per_window, self.trace_summary.xfer_per_win)

		## Wrap up pending metrics from the streaming stats:

		for opcode in (GET, PUT, ACC): # time spent in remote memory ops is spent in put, get, acc
			self.trace_summary.rmatime[0] += self.trace_summary.opdurations[opcode][AGR] # sum all aggregates together to get total rma time
			if self.trace_summary.callcount_per_opcode[opcode] != 0:
				self.trace_summary.xfer_per_opcode[opcode][AVG] = self.trace_summary.xfer_per_opcode[opcode][AGR] / self.trace_summary.callcount_per_opcode[opcode]
		self.trace_summary.rmatime.fill(self.trace_summary.rmatime[0])
 
		## rma op callbacks have produced the aggregate duration and call-count, 
		## which both can be used for calculation of average opduration per opcode
		for opcode in (GET, PUT, ACC, FENCE, WIN_CR):
			if self.trace_summary.callcount_per_opcode[opcode] != 0:
				self.trace_summary.opdurations[opcode][AVG] = self.trace_summary.opdurations[opcode][AGR] / self.trace_summary.callcount_per_opcode[opcode]


	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()


		## identify window key to use on windows dictionary by looking into wintb
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			fl.forma_logger.warning(f'Key {data.win} not in wintb!')
			sys.exit(1)

		## TODO!!!
		## this if is here for backwards compatibility with the IM version
		## should be removed for precise profiling
		if (self.epochcount_per_window[win_id] > -1):
			self.trace_summary.callcount_per_opcode[FENCE] += 1
			fs.forma_streaming_stats_x3(self.trace_summary.opdurations[FENCE], wall_duration)

		self.epochcount_per_window[win_id]+=1

	def on_win_create(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		self.win_count += 1
		## on create, I update the window ID to index translation buffer
		## on free, I will free the corresponding entry
		## DEBUG attempt: I am using a check with -1 in order to detect eventual collisions
		if self.wintb: ## check first if dict is empty, otherwise nasty seg faults
			if data.win in (self.wintb).keys(): ## if NOT empty and key already exists... 
				if (self.wintb[data.win] != -1): ## ... check value, in case on_win_free has not yet been called on it
					fl.forma_logger.warning(f'COLLISION ON WINDOW ID {data.win}')
					sys.exit(1)
			#fl.forma_logger.debug('window tb not empty, key does not exist') 
			## otherwise, not empty, but key does not exist yet
			self.wintb[data.win] = self.win_count-1
		else:
			self.wintb[data.win] = self.win_count-1
			#fl.forma_logger.debug('window tb empty')

		win_id = self.wintb[data.win]

		## after determining a safe win id, i use it to initialize the local book-keeping
		self.epochcount_per_window.append(-1)
		self.data_xfer_per_window.append(0)
		self.lifetime_of_window.append(wall_time.start.to_ns())
		##

		self.trace_summary.callcount_per_opcode[WIN_CR] += 1
		self.trace_summary.wins += 1 
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[WIN_CR], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.winsizes, data.size)

	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)

		self.lifetime_of_window[win_id] = wall_time.stop.to_ns() - self.lifetime_of_window[win_id]

		self.wintb[data.win] = -1

		self.trace_summary.callcount_per_opcode[WIN_FREE] += 1


	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		self.trace_summary.callcount_per_opcode[GET] += 1
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[GET], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[GET], data.origincount*self.type_sizes[data.origintype])

		win_id = self.wintb[data.win]
		self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]

	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		self.trace_summary.callcount_per_opcode[PUT] += 1
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[PUT], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[PUT], data.origincount*self.type_sizes[data.origintype])

		win_id = self.wintb[data.win]
		self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]


	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		self.trace_summary.callcount_per_opcode[ACC] += 1
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[ACC], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[ACC], data.origincount*self.type_sizes[data.origintype])

		win_id = self.wintb[data.win]
		self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]

