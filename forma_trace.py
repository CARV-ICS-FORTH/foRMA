#!/usr/bin/python3

import getopt 
import sys 
import glob, os
import re
import fnmatch


import logging

from pydumpi import DumpiTrace


## foRMA in-memory (IM) trace, one of the versions of the callback 
## implementations where all opdata are kept in dedicated vectors and 
## statistics are calculated a posteriori

class FormaIMTrace(DumpiTrace):

	def __init__(self, file_name):
		super().__init__(file_name)
		self.fence_count = 0
		self.win_count = 0
		
		## DataVolumes per epoch per detected window for current trace. 
		## indexed by window ID (cf. window lookaside translation buffer wintb)
		#self.dv_perEpoch_perWindow = dict()
		self.wintb = dict()

		self.epochcount_per_window = []
		self.opdata_per_window = []

		self.total_exec_time = 0


	def on_init(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		self.total_exec_time = cpu_time.start.to_ns()

	def on_finalize(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		self.total_exec_time = self.total_exec_time - cpu_time.stop.to_ns()


	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		# count mpi_win_fence occurrences
		self.fence_count += 1

		## identify window key to use on windows dictionary by looking into wintb
		win_id = self.wintb[data.win]
		opdata = ['f', wall_time.start.to_ns(), cpu_time.stop.to_ns(), cpu_duration]
		

		## log opdata into corresponding list entry in self.opdata_per_window
		self.opdata_per_window[win_id].append([])
		win_epoch = self.epochcount_per_window[win_id]
		if (win_epoch>-1): 
			self.opdata_per_window[win_id][win_epoch].append(opdata)

		## increase epoch count on corresponding window
		## first fence ever on 
		self.epochcount_per_window[win_id]+=1


	def on_win_create(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		self.win_count += 1

		## on create, I update the window ID to index translation buffer
		## on free, I will free the corresponding entry
		## DEBUG attempt: I am using a check with -1 in order to detect eventual collisions
		if self.wintb: ## check first if dict is empty, otherwise nasty seg faults
			if data.win in (self.wintb).keys(): ## if NOT empty and key already exists... 
				if (self.wintb[data.win] != -1): ## ... check value, in case on_win_free has not yet been called on it
					print(f'COLLISION ON WINDOW ID {data.win}')
			#print('window tb not empty, key does not exist') 
			## otherwise, not empty, but key does not exist yet
			self.wintb[data.win] = self.win_count-1
		else:
			self.wintb[data.win] = self.win_count-1
			#print('window tb empty')


		win_id = self.wintb[data.win]

		## create self.epochcount_per_window list entry for new window, 
		## so that on_fence can safely increment the epoch count
		self.epochcount_per_window.append(-1)

		## same for self.opdata_per_window
		self.opdata_per_window.append([])

	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		self.wintb[data.win] = -1

	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		win_id = self.wintb[data.win]
		# opdata = ['g', wall_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		opdata = ['g', cpu_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		win_epoch = self.epochcount_per_window[win_id]
		self.opdata_per_window[win_id][win_epoch].append(opdata)

	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		win_id = self.wintb[data.win]
		# opdata = ['p', wall_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		opdata = ['p', cpu_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		win_epoch = self.epochcount_per_window[win_id]
		self.opdata_per_window[win_id][win_epoch].append(opdata)

	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		win_id = self.wintb[data.win]
		# opdata = ['a', wall_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		opdata = ['a', cpu_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		win_epoch = self.epochcount_per_window[win_id]
		self.opdata_per_window[win_id][win_epoch].append(opdata)