#!/usr/bin/python3

import sys 
import glob, os
import re
import fnmatch

import ctypes

import logging

from pydumpi import dtypes
from pydumpi import DumpiTrace


## foRMA in-memory (IM) trace, one of the versions of the callback 
## implementations where all opdata are kept in dedicated vectors and 
## statistics are calculated a posteriori

class FormaIMTrace(DumpiTrace):

	def __init__(self, file_name): #, csv_filename, pickle_filename, parquet_filename):
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

		self.all_window_durations = []

		## will use the convention: 0 - MPI_Get, 1 - MPI_Put, 2 - MPI_Acc, 3 - MPI_Win_fence
		## will add the following: 4 - MPI_Win_create, 5 - MPI_Win_free, 6 - MPI_Init, 7 - MPI_Finalize
		self.callcount_per_opcode = [0, 0, 0, 0, 0, 0, 0, 0]

		self.myProfile = ctypes.POINTER(dtypes.DumpiProfile)

		# self.myCsv = open(csv_filename, 'w')
		# self.writer = csv.writer(self.myCsv)

		# self.myPickle = open(pickle_filename, 'wb')

		# table = pa.Table.from_arrays([[0, 0, 0, 0, 0]], names=["col1"])

		# self.PqFilename = parquet_filename

		# self.pqwriter = pq.ParquetWriter(self.PqFilename, table.schema)

		# schema = avro.schema.parse(open("opdata.avsc", "rb").read())

		# self.avroWriter = DataFileWriter(open(file_name+".avro", "wb"), DatumWriter(), schema)
		

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


		#self.wallOffset = (self._profile).cpu_time_offset
		# print(f'\nDUMPI TRACE READING HEADER: {self.read_header().starttime}')

		# self.myProfile = self._profile
		# print(f'DUMPI TRACE WALL OFFSET: {self.myProfile.contents.wall_time_offset}')

	def on_finalize(self, data, thread, cpu_time, wall_time, perf_info):
		#time_diff = wall_time.stop - wall_time.start
		## capture start time of init and end time of finalize in order 
		## to get the total execution time of the rank for this trace
		#self.total_exec_time = cpu_time.stop.to_ns()- self.total_exec_time
		self.total_exec_time = wall_time.stop.to_ns()- self.total_exec_time

		self.callcount_per_opcode[7] = self.callcount_per_opcode[7] + 1

		#self.myCsv.close()
		#self.myPickle.close()
		#self.pqwriter.close()
		#self.avroWriter.close()



	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		# count mpi_win_fence occurrences
		self.fence_count += 1

		self.callcount_per_opcode[3] = self.callcount_per_opcode[3] + 1


		## identify window key to use on windows dictionary by looking into wintb
		#win_id = self.wintb[data.win]
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)

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

		# self.writer.writerow(opdata)
		# pickle.dump(opdata, self.myPickle)
		# table = pa.Table.from_arrays([opdata], names=["col1"])
		# #pq.write_table(table, self.PqFilename, compression=None)
		# self.pqwriter.write_table(table)

		# self.avroWriter.append({"opcode": 3, "wt_start": wall_time.start.to_ns(), "wt_duration": wall_duration, "numbytes": wall_time.stop.to_ns(), "tg_rank": 0})



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
					#sys.exit(1)
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

		self.all_window_durations.append([wall_duration, wall_time.start.to_ns(), 0])



	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!'+
				'Window ID error. Please make sure that you are using a well-formed trace.\n'+
				'(Make sure that you are using entire and corrrectly formated SST Dumpi tracefiles '+
				'and notice that the current version of foRMA relies on detecting only MPI_Win_create '+
				'calls for window creation.')
			sys.exit(1)

		self.wintb[data.win] = -1

		self.callcount_per_opcode[5] = self.callcount_per_opcode[5] + 1

		window_start_time = self.all_window_durations[win_id][1]

		window_life_time = (wall_time.stop.to_ns() - window_start_time)

		## each element is of all_window_durations contains info for window with ID data.win and is of the form:
		## [ MPI_Win_create wall clock duration,  total window life time (wall clock), MPI_Win_free wall clock duration]		
		self.all_window_durations[win_id] = [self.all_window_durations[win_id][0], window_life_time, wall_duration]


	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()
		
		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)

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

		# self.writer.writerow(opdata)
		# pickle.dump(opdata, self.myPickle)
		# table = pa.Table.from_arrays([opdata], names=["col1"])
		# #pq.write_table(table, self.PqFilename, compression=None)
		# self.pqwriter.write_table(table)

		# self.avroWriter.append({"opcode": 0, "wt_start": wall_time.start.to_ns(), "wt_duration": wall_duration, "numbytes": data.origincount*self.type_sizes[data.origintype], "tg_rank": data.targetrank})



	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)


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

		# self.writer.writerow(opdata)
		# pickle.dump(opdata, self.myPickle)
		# table = pa.Table.from_arrays([opdata], names=["col1"])
		# #pq.write_table(table, self.PqFilename, compression=None)
		# self.pqwriter.write_table(table)

		# self.avroWriter.append({"opcode": 1, "wt_start": wall_time.start.to_ns(), "wt_duration": wall_duration, "numbytes": data.origincount*self.type_sizes[data.origintype], "tg_rank": data.targetrank})



	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		wall_duration = (wall_time.stop - wall_time.start).to_ns()
		#cpu_duration = (cpu_time.stop - cpu_time.start).to_ns()

		try:
			win_id = self.wintb[data.win]
		except KeyError:
			print(f'Key {data.win} not in wintb!')
			sys.exit(1)


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

		# self.writer.writerow(opdata)
		# pickle.dump(opdata, self.myPickle)
		# table = pa.Table.from_arrays([opdata], names=["col1"])
		# #pq.write_table(table, self.PqFilename, compression=None)
		# self.pqwriter.write_table(table)

		# self.avroWriter.append({"opcode": 2, "wt_start": wall_time.start.to_ns(), "wt_duration": wall_duration, "numbytes": data.origincount*self.type_sizes[data.origintype], "tg_rank": data.targetrank})
