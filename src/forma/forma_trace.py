__all__ = ["forma"]
__author__ = "Lena Kanellou"
__version__ = "0.1.0"



import getopt 
import sys 
import glob, os
import re
import fnmatch
import copy
import numpy as np

import ctypes

# import avro.schema
# from avro.datafile import DataFileReader, DataFileWriter
# from avro.io import DatumReader, DatumWriter
# from fastavro import reader

import logging

from pydumpi import dtypes
from pydumpi import DumpiTrace


import forma.forma_classes as fc
import forma.forma_logging as fl
import forma.forma_stats as fs
import forma.forma_prints as fo
from forma.forma_constants import *
import forma.forma_config as fg

import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter

import importlib.resources


## foRMA in-memory (IM) trace, one of the versions of the callback 
## implementations where all opdata are kept in dedicated vectors and 
## statistics are calculated a posteriori

class FormaSTrace(DumpiTrace):

	def __init__(self, file_name, rank): #, csv_filename, pickle_filename, parquet_filename):
		super().__init__(file_name)
		
		self.trace_summary = fc.formaSummary()
		#self.trace_summary.setRanks(1)
		
		self.rankID = rank
		self.wc_bias = 0

		## Window metrics are indexed by window ID but something strange is going on with 
		## sst dumpi window id numbers, so I'm using a window id lookaside translation buffer
		self.win_count = 0
		self.wintb = dict()

		## based on the above, the following are indexed by win_id, which is the value of 
		## wintb when the key is data.win
		self.epochcount_per_window = []
		self.data_xfer_per_window = []
		self.lifetime_of_window = []
		self.window_summaries = []

		## similarly but not exactly the same, we use win_id as key to the following dictionary
		## in order to access epoch statistics for the currently active epoch for this window
		self.epoch_stats_for_win = {}

		## the following is done to ensure that epoch stats are dumped into the avro file in the 
		## order in which their windows were created. we do this to facilitate epoch stats calculation
		## across ranks if the user selects the 'e' option from the interactive menu. specifically, 
		## we use curr_win_to_file to indicate the win id that is currently written to the avro file
		## and append all epoch data of other windows to the corresponding entry in the win_epochs_buffer
		## (key to which is win_id)
		self.win_epochs_buffer = {}
		self.curr_win_to_file = -1
		self.stashed_win_ids = set()
		self.stashed_closed_win_ids = set()
		
		## creating all necessary avro file book-keeping 
		if not os.path.exists('./forma_meta/'):
			os.mkdir('./forma_meta/')

		#resource_string = importlib.resources.path("forma", 'schemas/epochstats.avsc')
		# schema = avro.schema.parse(open("schemas/epochstats.avsc", "rb").read())
		resource_string = importlib.resources.files('forma.schemas').joinpath('epochstats.avsc')
		with importlib.resources.as_file(resource_string) as resource:
			schema = avro.schema.parse(open(resource, "rb").read())
		epochfilename = "./forma_meta/epochs-"+str(rank)+".avro"
		self.writer = DataFileWriter(open(epochfilename, "wb"), DatumWriter(), schema)



	def on_init(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		self.wc_bias = wall_time.stop.to_ns()
		
		#self.total_exec_time = cpu_time.start.to_ns()
		#self.total_exec_time = wall_time.start.to_ns()

		#self.callcount_per_opcode[6] = self.callcount_per_opcode[6] + 1

		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		self.trace_summary.exectime[0] = wall_time.start.to_ns()
		self.trace_summary.ranks += 1 

		# if self._profile:
		# 	print('Profile accessed')


	def on_finalize(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start

		#self.total_exec_time = cpu_time.stop.to_ns()- self.total_exec_time
		#self.total_exec_time = wall_time.stop.to_ns()- self.total_exec_time
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


		self.writer.close()


	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		fence_arrival = wall_time.start.to_ns() - self.wc_bias
		
		## identify window key to use on windows dictionary by looking into wintb
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			fl.forma_logger.debug(f'Key {data.win} not in wintb!')
			fl.forma_error(f'Window ID error. Please make sure that you are using a well-formed trace.\n'+
				'(Make sure that you are using entire and corrrectly formated SST Dumpi tracefiles '+
				'and notice that the current version of foRMA relies on detecting only MPI_Win_create '+
				'calls for window creation.')
			sys.exit(1)

		## TODO!!!
		## this if is here for backwards compatibility with the IM version
		## should be removed for precise profiling
		if (self.epochcount_per_window[win_id] > -1):
			self.trace_summary.callcount_per_opcode[FENCE] += 1
			fs.forma_streaming_stats_x3(self.trace_summary.opdurations[FENCE], wall_duration)

		## keeping score of win id and epoch count, so that we can write them in the avro file.
		## was done for the unordered epoch stats dumping to avro file, might be redundant.
		self.epochcount_per_window[win_id]+=1
		self.epoch_stats_for_win[win_id].win_id = win_id
		self.epoch_stats_for_win[win_id].epoch_nr = self.epochcount_per_window[win_id]
		self.epoch_stats_for_win[win_id].arrival = fence_arrival
				
		# print(f'forma trace: fence arrival in epoch {self.epochcount_per_window[win_id]} for window {win_id} is {self.epoch_stats_for_win[win_id].arrival}')

		## brief debug print, for reassurance...
		# print(f'Window is {self.epoch_stats_for_win[win_id].win_id}, epoch is {self.epochcount_per_window[win_id]}')
		
		# epoch_stats = []
		# for opcode in range(3):
		# 	div = self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]
		# 	if div != 0:
		# 		self.epoch_stats_for_win[win_id].opdurations[opcode][AVG] = self.epoch_stats_for_win[win_id].opdurations[opcode][AGR] / self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]
		# 	epoch_stats.append((self.epoch_stats_for_win[win_id].opdurations[opcode]).tolist())
		
		# fo.forma_print_stats_x4(["MPI_Get", "MPI_Put", "MPI_Accumulate"], epoch_stats, 0)
		## debug print end


		## fix data transfer bounds for epoch and then for trace summary
		for opcode in range(3):
			if self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode] != 0:
				self.epoch_stats_for_win[win_id].dtbounds[opcode][MIN] = wall_time.stop.to_ns() - self.epoch_stats_for_win[win_id].dtbounds[opcode][MIN]
				self.epoch_stats_for_win[win_id].dtbounds[opcode][MAX] = wall_time.stop.to_ns() - self.epoch_stats_for_win[win_id].dtbounds[opcode][MAX]
				self.epoch_stats_for_win[win_id].dtbounds[opcode][AGR] = (np.float64(self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode])*wall_time.stop.to_ns()) - self.epoch_stats_for_win[win_id].dtbounds[opcode][AGR]
				#self.epoch_stats_for_win[win_id].dtbounds[opcode][AVG] = self.epoch_stats_for_win[win_id].dtbounds[opcode][AGR] / self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]

				fs.forma_merge_stats_x4(self.trace_summary.dtbounds[opcode], self.epoch_stats_for_win[win_id].dtbounds[opcode])
		## 
# 
		## update window summary
		#self.epoch_stats_for_win[win_id].print_summary()
		self.window_summaries[win_id] += self.epoch_stats_for_win[win_id]
		#self.window_summaries[win_id].print_summary()
		##

		## ensuring that epoch stats are written to avro file in the order in which 
		## the windows were created. 
		if win_id == self.curr_win_to_file:
			# dump to avro file and reset 
			self.writer.append({"win_id": self.epoch_stats_for_win[win_id].win_id, 
				"epoch_nr": self.epochcount_per_window[win_id], 
				"arrival" : fence_arrival,
				"mpi_gets": int(self.epoch_stats_for_win[win_id].callcount_per_opcode[GET]), 
				"mpi_puts": int(self.epoch_stats_for_win[win_id].callcount_per_opcode[PUT]), 
				"mpi_accs": int(self.epoch_stats_for_win[win_id].callcount_per_opcode[ACC]), 
				"mpi_get_times": self.epoch_stats_for_win[win_id].opdurations[GET].tolist(), 
				"mpi_put_times": self.epoch_stats_for_win[win_id].opdurations[PUT].tolist(), 
				"mpi_acc_times": self.epoch_stats_for_win[win_id].opdurations[ACC].tolist(), 
				"tf_per_op": self.epoch_stats_for_win[win_id].xfer_per_opcode.tolist(), 
				"mpi_get_dtb": self.epoch_stats_for_win[win_id].dtbounds[GET].tolist(), 
				"mpi_put_dtb": self.epoch_stats_for_win[win_id].dtbounds[PUT].tolist(), 
				"mpi_acc_dtb": self.epoch_stats_for_win[win_id].dtbounds[ACC].tolist()})
			#self.epoch_stats_for_win[win_id].reset()

		else:
			# another window is currently written to avro file -- so, we have to stash 
			# the epoch data 
			#print(f'WIN FENCE - new epoch data to be stashed for window {win_id} at epoch {self.epochcount_per_window[win_id]}: ')
			#self.epoch_stats_for_win[win_id].print_summary()

			#print(f'current data in epoch stash for window {win_id} is ', end='')
			if self.win_epochs_buffer.get(win_id) == None:
				self.win_epochs_buffer[win_id] = []
			#	print(': NONE')
			#else:
			#	print('')
			
			# for epoch in self.win_epochs_buffer.get(win_id):
			# 	epoch.print_summary()
			

			self.win_epochs_buffer[win_id].append(copy.copy(self.epoch_stats_for_win[win_id]))
			# print('------------------- AFTER APPEND -----------------------')
			# for epoch in self.win_epochs_buffer[win_id]:
			# 	epoch.print_summary()

			# print(f'---> UPDATED data in epoch stash for window {win_id} is ')
			# epoch_stash_upd = self.win_epochs_buffer.get(win_id)
			# if epoch_stash_upd == None:
			# 	epoch_stash_upd = []
	
			# for epoch in epoch_stash_upd:
			# 	epoch.print_summary()

		self.epoch_stats_for_win[win_id].reset()
		#self.epoch_stats_for_win[win_id].win_id = win_id
	

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
					#fl.forma_logger.warning(f'COLLISION ON WINDOW ID {data.win}')
					fl.forma_error('Window count discrepancy. Does each MPI_Win_create have a matching MPI_Win_free? Make sure you are using well-formatted SST Dumpi output files.')
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
		self.window_summaries.append(fc.windowSummary(data.size))
		##

		self.epoch_stats_for_win[win_id] = fc.epochSummary()

		self.trace_summary.callcount_per_opcode[WIN_CR] += 1
		self.trace_summary.wins += 1 
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[WIN_CR], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.winsizes, data.size)

		#print(f'WIN CREATE: curr win to file: {self.curr_win_to_file} / win_id: {win_id} / stashed: {self.stashed_win_ids}')
		if self.curr_win_to_file != win_id:
			if self.curr_win_to_file == -1:
				self.curr_win_to_file = win_id
			else:
				if self.curr_win_to_file in self.stashed_closed_win_ids and not self.stashed_win_ids:
					self.curr_win_to_file = win_id
				#else:
		self.stashed_win_ids.add(win_id)
		#print(f'WIN CREATE: STASHED WINDOWS: {self.stashed_win_ids}')


	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)

		self.lifetime_of_window[win_id] = wall_time.stop.to_ns() - self.lifetime_of_window[win_id]

		##

		self.window_summaries[win_id].set_finals(self.data_xfer_per_window[win_id], self.lifetime_of_window[win_id], self.epochcount_per_window[win_id])


		## ## ##

		self.stashed_closed_win_ids.add(win_id)

		## ensuring that epoch stats are written to avro file in the order in which 
		## the windows were created. 
		if win_id == self.curr_win_to_file:
			#self.stashed_win_ids.discard(win_id)

		#	print(f'win_id == self.curr_win_to_file - {win_id}')

			#self.curr_win_to_file += 1

			#for i in range(len(self.stashed_win_ids)):
			stashed_ids_list = sorted(self.stashed_win_ids)

			#print(f'--> Active Window: {win_id} -- CURRENTLY STASHED IDs: {self.stashed_win_ids}')

			# for stashed_id in self.stashed_win_ids:
			for i, stashed_id in enumerate(stashed_ids_list):
				#print(f'entering for i in range(len(self.stashed_win_ids)) with i = {i}')
				#self.curr_win_to_file += 1
				#print(f'curr win id to file is now: {self.curr_win_to_file}')
				#print(f'stashed win ids is {self.stashed_win_ids}')
				#print(f'win id type: {type(win_id)}\ncurr_win_to_file type: {type(self.curr_win_to_file)}\ni type: {type(i)}')

				try:
					assert self.curr_win_to_file + i == stashed_id
				except AssertionError:
					print(f'Curr win to file is {self.curr_win_to_file}, counter is {i}, while current stashed id is {stashed_id}')
					sys.exit(2) 

				if stashed_id != self.curr_win_to_file:

					#print(f'foRMA PRINTING STASHED WINDOW DATA to file for win {stashed_id}')
					epoch_stash = self.win_epochs_buffer.get(stashed_id)
					if epoch_stash:
						for epochstats in epoch_stash:
							# print(f'arrival is : {epochstats.arrival}')
							self.writer.append({"win_id": epochstats.win_id, 
								"epoch_nr": epochstats.epoch_nr, 
								"arrival" : epochstats.arrival,
								"mpi_gets": int(epochstats.callcount_per_opcode[GET]), 
								"mpi_puts": int(epochstats.callcount_per_opcode[PUT]), 
								"mpi_accs": int(epochstats.callcount_per_opcode[ACC]), 
								"mpi_get_times": epochstats.opdurations[GET].tolist(), 
								"mpi_put_times": epochstats.opdurations[PUT].tolist(), 
								"mpi_acc_times": epochstats.opdurations[ACC].tolist(), 
								"tf_per_op": epochstats.xfer_per_opcode.tolist(), 
								"mpi_get_dtb": epochstats.dtbounds[GET].tolist(), 
								"mpi_put_dtb": epochstats.dtbounds[PUT].tolist(), 
								"mpi_acc_dtb": epochstats.dtbounds[ACC].tolist()})


				#self.stashed_win_ids.discard(stashed_id)

				if stashed_id not in self.stashed_closed_win_ids:
					self.curr_win_to_file = stashed_id
					break
				else:
					self.stashed_win_ids.discard(stashed_id)
							
			# self.curr_win_to_file = stashed_id
			# print(f'Setting current window to file to stashed id {stashed_id}')
			# print(f'currently stashed windows: {self.stashed_win_ids}')

		# else:
		# 	self.stashed_closed_win_ids.add(win_id)
		# 	#self.stashed_win_ids.remove(win_id)

		#print(f'WIN FREE for {win_id} - CLOSED WINDOWS: {self.stashed_closed_win_ids}')
		

		del self.epoch_stats_for_win[win_id]

		self.wintb[data.win] = -1

		self.trace_summary.callcount_per_opcode[WIN_FREE] += 1


	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		try:

			self.trace_summary.callcount_per_opcode[GET] += 1
			fs.forma_streaming_stats_x3(self.trace_summary.opdurations[GET], wall_duration)
			fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[GET], data.origincount*self.type_sizes[data.origintype])

			win_id = self.wintb[data.win]
			self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]

			self.epoch_stats_for_win[win_id].callcount_per_opcode[GET] += 1
			fs.forma_streaming_stats_x3(self.epoch_stats_for_win[win_id].opdurations[GET], wall_duration)

			## dt bound for epoch
			if self.epoch_stats_for_win[win_id].dtbounds[GET][MAX] == 0:
				self.epoch_stats_for_win[win_id].dtbounds[GET][MAX] = wall_time.start.to_ns()
			self.epoch_stats_for_win[win_id].dtbounds[GET][MIN] = wall_time.start.to_ns()
			self.epoch_stats_for_win[win_id].dtbounds[GET][AGR] += wall_time.start.to_ns()
			##

		except Exception as e:
			fl.forma_error('Unexpected error occurred: {e}')
			exit(2)


	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		try: 

			self.trace_summary.callcount_per_opcode[PUT] += 1
			fs.forma_streaming_stats_x3(self.trace_summary.opdurations[PUT], wall_duration)
			fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[PUT], data.origincount*self.type_sizes[data.origintype])


			win_id = self.wintb[data.win]
			self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]

			self.epoch_stats_for_win[win_id].callcount_per_opcode[PUT] += 1
			fs.forma_streaming_stats_x3(self.epoch_stats_for_win[win_id].opdurations[PUT], wall_duration)

			## dt bound for epoch
			if self.epoch_stats_for_win[win_id].dtbounds[PUT][MAX] == 0:
				self.epoch_stats_for_win[win_id].dtbounds[PUT][MAX] = wall_time.start.to_ns()
			self.epoch_stats_for_win[win_id].dtbounds[PUT][MIN] = wall_time.start.to_ns()
			self.epoch_stats_for_win[win_id].dtbounds[PUT][AGR] += wall_time.start.to_ns()
			##

		except Exception as e:
			fl.forma_error('Unexpected error occurred: {e}')
			exit(2)


	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		try:

			self.trace_summary.callcount_per_opcode[ACC] += 1
			fs.forma_streaming_stats_x3(self.trace_summary.opdurations[ACC], wall_duration)
			fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[ACC], data.origincount*self.type_sizes[data.origintype])

			win_id = self.wintb[data.win]
			self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]

			self.epoch_stats_for_win[win_id].callcount_per_opcode[ACC] += 1
			fs.forma_streaming_stats_x3(self.epoch_stats_for_win[win_id].opdurations[ACC], wall_duration)

			## dt bound for epoch
			if self.epoch_stats_for_win[win_id].dtbounds[ACC][MAX] == 0:
				self.epoch_stats_for_win[win_id].dtbounds[ACC][MAX] = wall_time.start.to_ns()
			self.epoch_stats_for_win[win_id].dtbounds[ACC][MIN] = wall_time.start.to_ns()
			self.epoch_stats_for_win[win_id].dtbounds[ACC][AGR] += wall_time.start.to_ns()
			##


		except Exception as e:
			fl.forma_error('Unexpected error occurred: {e}')
			exit(2)