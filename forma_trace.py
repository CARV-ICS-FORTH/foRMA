#!/usr/bin/python3

import getopt 
import sys 
import glob, os
import re
import fnmatch

import ctypes

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

		self.source_file = ctypes.create_string_buffer(64)
		
		## DataVolumes per epoch per detected window for current trace. 
		## indexed by window ID (cf. window lookaside translation buffer wintb)
		#self.dv_perEpoch_perWindow = dict()
		self.wintb = dict()

		self.epochcount_per_window = []
		self.opdata_per_window = []

		self.total_exec_time = 0
		self.all_window_sizes = []

		## will use the convention: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc, 3 - MPI_Win_fence
		## will add the following: 4 - MPI_Win_create, 5 - MPI_Win_free, 6 - MPI_Init, 7 - MPI_Finalize
		self.callcount_per_opcode = [0, 0, 0, 0, 0, 0, 0, 0]


	def on_init(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		#self.total_exec_time = cpu_time.start.to_ns()
		self.total_exec_time = wall_time.start.to_ns()

		self.callcount_per_opcode[6] = self.callcount_per_opcode[6] + 1

		"""

		self.source_file = ctypes.create_string_buffer(data.argv[0].contents.value, 64)
		print(repr(data.argv[0].contents.value))

		"""

		#self.source_file =pathinfo(data.argv[0].contents.value, 64)

		#print(repr(data.argv[0].contents.value))

		#print(data.argv[0].contents.value) #.contents.contents.value 

	def on_finalize(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		#self.total_exec_time = cpu_time.stop.to_ns()- self.total_exec_time
		self.total_exec_time = wall_time.stop.to_ns()- self.total_exec_time

		self.callcount_per_opcode[7] = self.callcount_per_opcode[7] + 1



	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		# count mpi_win_fence occurrences
		self.fence_count += 1

		self.callcount_per_opcode[3] = self.callcount_per_opcode[3] + 1


		## identify window key to use on windows dictionary by looking into wintb
		win_id = self.wintb[data.win]
		""" for vectors that refer to RMA ops, we use the following 
		convention for indexing: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc
		and if present, then 3 - MPI_Win_fence
		"""
		#opdata = [3, wall_time.start.to_ns(), cpu_duration, cpu_time.stop.to_ns()]
		opdata = [3, wall_time.start.to_ns(), wall_duration, wall_time.stop.to_ns()]
		

		## log opdata into corresponding list entry in self.opdata_per_window
		self.opdata_per_window[win_id].append([])
		win_epoch = self.epochcount_per_window[win_id]
		if (win_epoch>-1): 
			self.opdata_per_window[win_id][win_epoch].append(opdata)

		## increase epoch count on corresponding window
		## first fence ever on 
		self.epochcount_per_window[win_id]+=1


	def on_win_create(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		self.win_count += 1


		self.callcount_per_opcode[4] = self.callcount_per_opcode[4] + 1


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

		self.all_window_sizes.append(data.size)

	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		self.wintb[data.win] = -1


		self.callcount_per_opcode[5] = self.callcount_per_opcode[5] + 1


	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		win_id = self.wintb[data.win]


		self.callcount_per_opcode[0] = self.callcount_per_opcode[0] + 1


		""" for vectors that refer to RMA ops, we use the following 
		convention for indexing: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc
		and if present, then 3 - MPI_Win_fence
		"""
		# opdata = ['g', wall_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		#opdata = [0, cpu_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		opdata = [0, wall_time.start.to_ns(), wall_duration, data.origincount*self.type_sizes[data.origintype], data.targetrank]

		win_epoch = self.epochcount_per_window[win_id]
		self.opdata_per_window[win_id][win_epoch].append(opdata)

	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		win_id = self.wintb[data.win]


		self.callcount_per_opcode[1] = self.callcount_per_opcode[1] + 1


		""" for vectors that refer to RMA ops, we use the following 
		convention for indexing: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc
		and if present, then 3 - MPI_Win_fence
		"""
		# opdata = ['p', wall_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		#opdata = [1, cpu_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		opdata = [1, wall_time.start.to_ns(), wall_duration, data.origincount*self.type_sizes[data.origintype], data.targetrank]

		win_epoch = self.epochcount_per_window[win_id]
		self.opdata_per_window[win_id][win_epoch].append(opdata)

	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		win_id = self.wintb[data.win]


		self.callcount_per_opcode[2] = self.callcount_per_opcode[2] + 1


		""" for vectors that refer to RMA ops, we use the following 
		convention for indexing: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc
		and if present, then 3 - MPI_Win_fence
		"""
		# opdata = ['a', wall_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		#opdata = [2, cpu_time.start.to_ns(), cpu_duration, data.origincount*self.type_sizes[data.origintype], 0]
		opdata = [2, wall_time.start.to_ns(), wall_duration, data.origincount*self.type_sizes[data.origintype], data.targetrank]

		win_epoch = self.epochcount_per_window[win_id]
		self.opdata_per_window[win_id][win_epoch].append(opdata)