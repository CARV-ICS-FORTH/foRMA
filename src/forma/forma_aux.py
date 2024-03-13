

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
__version__ = "0.1.0"


import sys 
import glob, os
import re
import fnmatch

import numpy as np

import logging

from pydumpi import DumpiTrace
from pydumpi import util


import forma.forma_trace as ft
import forma.forma_logging as fl
import forma.forma_classes as fc
import forma.forma_config as fg

import avro.schema
from avro.datafile import DataFileReader, DataFileWriter
from avro.io import DatumReader, DatumWriter

import importlib.resources



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
	total_file_size = round(total_file_size/1024)
	if total_file_size == 0:
		fl.forma_print('Trace file size is 0. Make sure that you are using well-formatted SST Dumpi output files.')
		sys.exit(2)
	fl.forma_print(f'Total trace size: {total_file_size} KBytes of binary trace files.\n')

	## Read metafile and print it -- TODO: to be used more extensively later
	try:
		metafile = util.read_meta_file(str(dirname)+'/dumpi-'+format(str(timestamp))+'.meta')
	except FileNotFoundError:
		fl.forma_print('.meta file not found. Check directory name and timestamp formatting.\n')
		#sys.exit(1)
		return None, 0


	return(ordered_files, len(ordered_files))


def rank_to_host(tracefiles):

	for rank, tracefile in enumerate(tracefiles):
		with ft.FormaSTrace(tracefile, rank) as trace:
			header = trace.read_header().hostname.decode('utf-8')
			print(f'Rank {rank}: {header}')

	return 0



def forma_aggregate_epoch_files(rank_nr):
	epoch_count = -1
	epoch_summary = fc.epochSummary(rank_nr)
	# schema = avro.schema.parse(open("../schemas/summary.avsc", "rb").read())
	resource_string = importlib.resources.files('forma.schemas').joinpath('epochstats.avsc')
	with importlib.resources.as_file(resource_string) as resource:
		schema = avro.schema.parse(open(resource, "rb").read())
	epochfiles = []
	readers = []
	offsets = []
	epoch_cnt = 0
	curr_lines = 0

	#mydir =  "./forma_meta/epochs-"+format(str(timestamp))+"/"
	if not os.path.exists(fg.metadir):
		os.mkdir(fg.metadir)

	for rank_id in range(0, rank_nr):
		#epochsumfile = "./forma_meta/"+format(str(timestamp))+"/epochs-"+str(rank_id)+".avro"
		epochsumfile = fg.metadir+"/epochs-"+str(rank_id)+".avro"
		epochfiles.append(epochsumfile)
		readers.append(DataFileReader(open(epochsumfile, "rb"), DatumReader(schema)))
		#next(readers[rank_id])
		# offsets.append(1)
		# if epoch_cnt == 0:
		# 	epoch_cnt = sum(1 for line in readers[rank_id])
		# 	curr_lines = epoch_cnt
		# else:
		# 	curr_lines = sum(1 for line in readers[rank_id])
		# fl.forma_logger.debug(f'Current rank is {rank_id}, line count is {curr_lines}')
		# fl.forma_logger.debug(f'Current lines {curr_lines}, Epoch count {epoch_cnt}')
		# if curr_lines != epoch_cnt: 
		# 	fl.forma_error('Total epoch count discrepancy. Make sure you are using well-formatted SST Dumpi output files.')
		# 	sys.exit(2)
		#readers[rank_id].close()
		# next(readers[rank_id])

	keep_reading = True
	curr_win = 0
	prev_win = -1
	rank_win = 0
	prev_rank_win = 0
	iteration = 0
	original_stdout = sys.stdout # Save a reference to the original standard output
	#epoch_dir ="forma_out/"+format(str(timestamp))
	if not os.path.exists(fg.outdir):
		os.mkdir(fg.outdir)
	epochfile = fg.outdir+"/epochs.txt"
	#with open('forma_out/epochs.txt', 'w') as f:
	with open(epochfile, 'w') as f:	
		sys.stdout = f # Change the standard output to the file we created.
		aggregate_epoch_summary = fc.epochSummary(rank_nr)
		while(keep_reading):
			for rank_id in range(0, rank_nr):
				# check for window concordance
				#readers[rank_id].reader.seek(offsets[rank_id])
				try:
					summary = next(readers[rank_id])
				except StopIteration:
					#print('EXCEPT STOP ITERATION')
					keep_reading = False
					break
				epoch_summary.set_from_dict(summary)

				rank_win = epoch_summary.win_id
				if rank_win != prev_rank_win and rank_id != 0:
					# handle error at higher level
					# fl.forma_error('Window ID discrepancy among files. Make sure you are using well-formatted SST Dumpi output files.')
					sys.stdout = original_stdout # Reset the standard output to its original value
					print(f'ITERATION {iteration}: ERROR AT RANK id {rank_id}: curr win {curr_win}, prev win {prev_win}, rank win {rank_win}, prev rank win {prev_rank_win}')
					return 2

				aggregate_epoch_summary += epoch_summary
				aggregate_epoch_summary.set_averages()
				# print(f'Rank {rank_id} epoch summary: {summary}')
				prev_rank_win = rank_win

			if keep_reading == False:
				#print('KEEP READING IS FALSE')
				break

			curr_win = rank_win
			# check for window change
			if curr_win != prev_win:
				print('------------------------------------------------------------------------------------------\n' + 
					f'-------------------------------- WINDOW {curr_win} ---------------------------------------------\n' + 
					'------------------------------------------------------------------------------------------\n')
			aggregate_epoch_summary.print_summary()
			prev_win = curr_win
			#
			aggregate_epoch_summary.reset(rank_nr)
			#
			iteration += 1
	sys.stdout = original_stdout # Reset the standard output to its original value
	return 0





def forma_aggregate_fence_arrivals(rank_nr):

	epoch_count = -1
	epoch_summary = fc.epochSummary(rank_nr)
	# schema = avro.schema.parse(open("../schemas/summary.avsc", "rb").read())
	resource_string = importlib.resources.files('forma.schemas').joinpath('epochstats.avsc')
	with importlib.resources.as_file(resource_string) as resource:
		schema = avro.schema.parse(open(resource, "rb").read())
	epochfiles = []
	readers = []
	offsets = []
	epoch_cnt = 0
	curr_lines = 0

	#mydir =  "./forma_meta/epochs-"+format(str(timestamp))+"/"
	if not os.path.exists(fg.metadir):
		os.mkdir(fg.metadir)

	for rank_id in range(0, rank_nr):
		epochsummaryfile = fg.metadir+"/epochs-"+str(rank_id)+".avro"
		epochfiles.append(epochsummaryfile)
		readers.append(DataFileReader(open(epochsummaryfile, "rb"), DatumReader(schema)))
		#next(readers[rank_id])

	arrivals = np.zeros(rank_nr)
	epoch = 0

	keep_reading = True
	curr_win = 0
	prev_win = -1
	rank_win = 0
	prev_rank_win = 0
	iteration = 0
	original_stdout = sys.stdout # Save a reference to the original standard output
	#fence_dir ="forma_out/"+format(str(timestamp))
	if not os.path.exists(fg.outdir):
		os.mkdir(fg.outdir)
	fencefile = fg.outdir+"/fences.txt"
	#with open('forma_out/fences.txt', 'w') as f:
	with open(fencefile, 'w') as f:
		sys.stdout = f # Change the standard output to the file we created.
		#aggregate_epoch_summary = fc.epochSummary()
		while(keep_reading):
			for rank_id in range(0, rank_nr): # for each rank, go through all epochs, window after window
				# check for window concordance
				#readers[rank_id].reader.seek(offsets[rank_id])
				try:
					summary = next(readers[rank_id])
				except StopIteration:
					#print('EXCEPT STOP ITERATION')
					keep_reading = False
					break
				epoch_summary.set_from_dict(summary)

				rank_win = epoch_summary.win_id
				if rank_win != prev_rank_win and rank_id != 0:
					# handle error at higher level
					# fl.forma_error('Window ID discrepancy among files. Make sure you are using well-formatted SST Dumpi output files.')
					sys.stdout = original_stdout # Reset the standard output to its original value
					print(f'ITERATION {iteration}: ERROR AT RANK id {rank_id}: curr win {curr_win}, prev win {prev_win}, rank win {rank_win}, prev rank win {prev_rank_win}')
					return 2

				# aggregate_epoch_summary += epoch_summary
				# aggregate_epoch_summary.set_averages()
				arrivals[rank_id] = epoch_summary.arrival
				# print(f'Rank {rank_id} arrival from epoch summary: {epoch_summary.arrival}')
				# print(f'Rank {rank_id} arrival: {arrivals[rank_id]}')
				prev_rank_win = rank_win

			if keep_reading == False:
				#print('KEEP READING IS FALSE')
				break

			curr_win = rank_win
			# check for window change
			if curr_win != prev_win:
				print('------------------------------------------------------------------------------------------\n' + 
					f'-------------------------------- WINDOW {curr_win} ---------------------------------------------\n' + 
					'------------------------------------------------------------------------------------------\n')
			# aggregate_epoch_summary.print_summary()
			epoch = epoch_summary.epoch_nr
			print(f'----------------------------- FENCE ARRIVALS for EPOCH {epoch} ------------------------------------------\n')
			#print(f'ALL: {arrivals}\n')
			first = np.min(arrivals)
			last = np.max(arrivals)
			print(f'First [ timestamp (rank) ]: {first} nsec ({np.argmin(arrivals)}) | Last [ timestamp (rank) ] : {last} nsec ({np.argmax(arrivals)}) | Difference: {(last-first)} nsec\n')
			prev_win = curr_win
			#
			# aggregate_epoch_summary.reset()
			arrivals.fill(0)
			#
			iteration += 1
	sys.stdout = original_stdout # Reset the standard output to its original value
	return 0


	fl.forma_print(f'Aggregating results from {rank_nr} meta-files.')

	return 0