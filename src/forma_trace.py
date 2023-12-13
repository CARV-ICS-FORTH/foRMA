__all__ = ["forma"]
__author__ = "Lena Kanellou"
__version__ = "0.1.0"



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
import forma_prints as fo
from forma_constants import *
import forma_config as fg

import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter


## foRMA in-memory (IM) trace, one of the versions of the callback 
## implementations where all opdata are kept in dedicated vectors and 
## statistics are calculated a posteriori

class FormaSTrace(DumpiTrace):

	def __init__(self, file_name, rank): #, csv_filename, pickle_filename, parquet_filename):
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
		self.curr_win_to_file = 0
		self.to_print_wins = set()
		self.to_print_done_wins = set()
		
		## creating all necessary avro file book-keeping 
		if not os.path.exists('./forma_meta/'):
			os.mkdir('./forma_meta/')

		schema = avro.schema.parse(open("schemas/epochstats.avsc", "rb").read())
		epochfilename = "./forma_meta/epochs-"+str(rank)+".avro"
		self.writer = DataFileWriter(open(epochfilename, "wb"), DatumWriter(), schema)



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

		## brief debug print, for reassurance...
		# print(f'Window is {self.epoch_stats_for_win[win_id].win_id}, epoch is {self.epochcount_per_window[win_id]}')
		
		# epoch_stats = []
		# for opcode in range(3):
		# 	div = self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]
		# 	if div != 0:
		# 		self.epoch_stats_for_win[win_id].opdurations[opcode][AVG] = self.epoch_stats_for_win[win_id].opdurations[opcode][AGR] / self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]
		# 	epoch_stats.append((self.epoch_stats_for_win[win_id].opdurations[opcode]).tolist())
		
		# fo.forma_print_stats_x4(["MPI_Get", "MPI_Put", "MPI_Accumulate"], epoch_stats)
		## debug print end


		## fix data transfer bounds for epoch and then for trace summary
		for opcode in range(3):
			if self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode] != 0:
				self.epoch_stats_for_win[win_id].dtbounds[opcode][MIN] = wall_time.stop.to_ns() - self.epoch_stats_for_win[win_id].dtbounds[opcode][MIN]
				self.epoch_stats_for_win[win_id].dtbounds[opcode][MAX] = wall_time.stop.to_ns() - self.epoch_stats_for_win[win_id].dtbounds[opcode][MAX]
				self.epoch_stats_for_win[win_id].dtbounds[opcode][AGR] = (self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]*wall_time.stop.to_ns()) - self.epoch_stats_for_win[win_id].dtbounds[opcode][AGR]
				#self.epoch_stats_for_win[win_id].dtbounds[opcode][AVG] = self.epoch_stats_for_win[win_id].dtbounds[opcode][AGR] / self.epoch_stats_for_win[win_id].callcount_per_opcode[opcode]

				fs.forma_merge_stats_x4(self.trace_summary.dtbounds[opcode], self.epoch_stats_for_win[win_id].dtbounds[opcode])
		## 
# 
		## ensuring that epoch stats are written to avro file in the order in which 
		## the windows were created. 
		if win_id == self.curr_win_to_file:
			# dump to avro file and reset 
			self.writer.append({"win_id": self.epoch_stats_for_win[win_id].win_id, 
				"epoch_nr": self.epochcount_per_window[win_id], 
				"arrival" : wall_time.start.to_ns(),
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
			epoch_stash = self.win_epochs_buffer.get(win_id)
			if epoch_stash == None:
				epoch_stash = []
			epoch_stash.append(self.epoch_stats_for_win)
			self.win_epochs_buffer[win_id] = epoch_stash
			# fl.forma_logger.debug(f'window data stashed for {win_id}')
		self.epoch_stats_for_win[win_id].reset()
	

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
		##

		self.epoch_stats_for_win[win_id] = fc.epochSummary()

		self.trace_summary.callcount_per_opcode[WIN_CR] += 1
		self.trace_summary.wins += 1 
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[WIN_CR], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.winsizes, data.size)

		if self.curr_win_to_file != win_id:
			self.to_print_wins.add(win_id)


	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)

		self.lifetime_of_window[win_id] = wall_time.stop.to_ns() - self.lifetime_of_window[win_id]

		
		## ensuring that epoch stats are written to avro file in the order in which 
		## the windows were created. 
		if win_id == self.curr_win_to_file:
			self.to_print_wins.discard(win_id)
			
			for i in range(len(self.to_print_wins)):
				self.curr_win_to_file += 1
				if i in self.to_print_wins:
					#print("foRMA PRINTING STASHED WINDOW DATA!")
					for epochstats in self.win_epochs_buffer[i]:
						self.writer.append({"win_id": epochstats.win_id, 
							"epoch_nr": epochstats.epoch_nr, 
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

				if i not in self.to_print_done_wins:
					break
				else:
					self.self.to_print_wins.discard(i)

		else:
			self.to_print_done_wins.add(win_id)
			#self.to_print_wins.remove(win_id)


		del self.epoch_stats_for_win[win_id]

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

		self.epoch_stats_for_win[win_id].callcount_per_opcode[GET] += 1
		fs.forma_streaming_stats_x3(self.epoch_stats_for_win[win_id].opdurations[GET], wall_duration)

		## dt bound for epoch
		if self.epoch_stats_for_win[win_id].dtbounds[GET][MAX] == 0:
			self.epoch_stats_for_win[win_id].dtbounds[GET][MAX] = wall_time.start.to_ns()
		self.epoch_stats_for_win[win_id].dtbounds[GET][MIN] = wall_time.start.to_ns()
		self.epoch_stats_for_win[win_id].dtbounds[GET][AGR] += wall_time.start.to_ns()
		##

	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		self.trace_summary.callcount_per_opcode[PUT] += 1
		fs.forma_streaming_stats_x3(self.trace_summary.opdurations[PUT], wall_duration)
		fs.forma_streaming_stats_x3(self.trace_summary.xfer_per_opcode[PUT], data.origincount*self.type_sizes[data.origintype])


		win_id = self.wintb[data.win]
		self.data_xfer_per_window[win_id] += data.origincount*self.type_sizes[data.origintype]

		self.epoch_stats_for_win[win_id].callcount_per_opcode[PUT] += 1
		fs.forma_streaming_stats_x3(self.epoch_stats_for_win[win_id].opdurations[GET], wall_duration)

		## dt bound for epoch
		if self.epoch_stats_for_win[win_id].dtbounds[PUT][MAX] == 0:
			self.epoch_stats_for_win[win_id].dtbounds[PUT][MAX] = wall_time.start.to_ns()
		self.epoch_stats_for_win[win_id].dtbounds[PUT][MIN] = wall_time.start.to_ns()
		self.epoch_stats_for_win[win_id].dtbounds[PUT][AGR] += wall_time.start.to_ns()
		##

	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

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