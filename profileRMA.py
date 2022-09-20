#!/usr/bin/python3

import getopt 
import sys 
import glob, os
import re
import fnmatch
import numpy as np
import collections
import subprocess
import math

from bisect import insort

import matplotlib.pyplot as plt

import pandas as pd

import logging



def set_log_level(option):

	level=logging.INFO

	if option=='critical':
		level=logging.CRITICAL
	elif option=='error':
		level=logging.ERROR
	elif option=='warn':
		level=logging.WARNING
	elif option=='warning':
		level=logging.WARNING
	elif option=='info':
		level=logging.INFO
	elif option=='debug':
		level=logging.DEBUG
	else:
		#print('rma profiler: set_log_level: log level must be one of: {critical, error, warn, warning, info, debug}')
		level=None

	return level



#rma_all_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait']
# in the following, for the purposes of economically storing data relevant to each call in 1D or 2D arrays, 
# we will use an index number to correspond to each of the calls in the order they appear in the list, i.e., 
# 0 -> MPI_Win_create, 2 -> MPI_Win_Get, etc. 
rma_all_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence']
	
callCountPerRank = []


def graph_per_call(totalRanks, perCallPerRankStatistics, perCallStatistics, rma_indexes):

	# create data in suitable format
	df = pd.DataFrame([['MPI_Win_create', perCallStatistics[rma_indexes["MPI_Win_create"]][0], perCallStatistics[rma_indexes["MPI_Win_create"]][1], perCallStatistics[rma_indexes["MPI_Win_create"]][2], perCallStatistics[rma_indexes["MPI_Win_create"]][3]],
	 				['MPI_Get', perCallStatistics[rma_indexes["MPI_Get"]][0], perCallStatistics[rma_indexes["MPI_Get"]][1], perCallStatistics[rma_indexes["MPI_Get"]][2], perCallStatistics[rma_indexes["MPI_Get"]][3]],
	 				['MPI_Put', perCallStatistics[rma_indexes["MPI_Put"]][0], perCallStatistics[rma_indexes["MPI_Put"]][1], perCallStatistics[rma_indexes["MPI_Put"]][2], perCallStatistics[rma_indexes["MPI_Put"]][3]],
					['MPI_Acc', perCallStatistics[rma_indexes["MPI_Accumulate"]][0], perCallStatistics[rma_indexes["MPI_Accumulate"]][1], perCallStatistics[rma_indexes["MPI_Accumulate"]][2], perCallStatistics[rma_indexes["MPI_Accumulate"]][3]],
	 				['MPI_Win_fence', perCallStatistics[rma_indexes["MPI_Win_fence"]][0], perCallStatistics[rma_indexes["MPI_Win_fence"]][1], perCallStatistics[rma_indexes["MPI_Win_fence"]][2], perCallStatistics[rma_indexes["MPI_Win_fence"]][3]],	 
	 				['MPI_Win_free', perCallStatistics[rma_indexes["MPI_Win_free"]][0], perCallStatistics[rma_indexes["MPI_Win_free"]][1], perCallStatistics[rma_indexes["MPI_Win_free"]][2], perCallStatistics[rma_indexes["MPI_Win_free"]][3]]],
					columns=['Durations (us)', 'min', 'max', 'avg', 'std dev'])

	# plot grouped bar chart
	df.plot(x='Durations (us)',
        kind='bar',
        stacked=False,
        title='PER RMA OP TYPE SUMMARY [ min  max  avg  std_dev ]')
	#plt.show()



def print_per_call(totalRanks, perCallPerRankStatistics, perCallStatistics, rma_indexes):

	print('\t\t * * * PER RANK / PER RMA OP TYPE SUMMARY [ min  max  avg  std dev ] * * *')
	print('\t MPI_Win_create \t|\t MPI_Get \t|\t MPI_Put \t|\t MPI_Acc \t|\t MPI_Win_fence \t|\t MPI_Win_free')
	for i in range(0, totalRanks):
		print(f'Rank {i}:\t {perCallPerRankStatistics[i][rma_indexes["MPI_Win_create"]]}\t{perCallPerRankStatistics[i][rma_indexes["MPI_Get"]]}\t{perCallPerRankStatistics[i][rma_indexes["MPI_Put"]]}\t{perCallPerRankStatistics[i][rma_indexes["MPI_Accumulate"]]}\t{perCallPerRankStatistics[i][rma_indexes["MPI_Win_fence"]]}\t{perCallPerRankStatistics[i][rma_indexes["MPI_Win_free"]]}')

	print('\t\t * * * PER RMA OP TYPE SUMMARY [ min  max  avg  std dev ] * * *')
	print('\t MPI_Win_create \t|\t MPI_Get \t|\t MPI_Put \t|\t MPI_Acc \t|\t MPI_Win_fence \t|\t MPI_Win_free')
	print(f'\t {perCallStatistics[rma_indexes["MPI_Win_create"]]}\t{perCallStatistics[rma_indexes["MPI_Get"]]}\t{perCallStatistics[rma_indexes["MPI_Put"]]}\t{perCallStatistics[rma_indexes["MPI_Accumulate"]]}\t{perCallStatistics[rma_indexes["MPI_Win_fence"]]}\t{perCallStatistics[rma_indexes["MPI_Win_free"]]}')

	graph_per_call(totalRanks, perCallPerRankStatistics, perCallStatistics, rma_indexes)


def produce_epoch_statistics(epochData):

	if all(i is None for i in epochData):
		logging.debug('rma profiler: produce_epoch_statistics: Starting Epochs')
	else:
		logging.debug('rma profiler: produce_epoch_statistics: Creating epoch statistics . . .')


def parse_trace_per_epoch(rma_tracked_calls):

	rma_set = frozenset(rma_tracked_calls)
	
	# use this in order to later validate with the amount of each call detected in the trace footers
	rma_occurrences = { i : 0 for i in rma_tracked_calls }

	# use this in order to later validate with the amount of each call detected in the trace footers
	j = 0
	#rma_indexes = { i : a for i, a in enumerate(rma_tracked_calls) }
	rma_indexes = { i : a for a, i in enumerate(rma_tracked_calls) }
	logging.debug(f'rma profiler: parse_trace_per_epoch: rma indexes are {rma_indexes}')


	ordered_files_all = sorted(os.listdir(format(str(dirname))))
	ordered_files = []
	ordered_ascii_files = []

	for filename in ordered_files_all:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			filepath = format(str(dirname))+'/'+format(str(filename))
			ordered_files.append(filepath)
			ascii_filepath = filepath.strip('.bin')+'.ascii'
			if (not os.path.exists(ascii_filepath)):
				# create ascii file if necessary
				print('rma profiler: parse_trace_per_epoch: creating file')
				os.system('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > ' + ascii_filepath)

			ordered_ascii_files.append(ascii_filepath)
	#logging.debug(ordered_ascii_files)

	totalRanks = len(ordered_files)
	totalCallTypes = len(rma_tracked_calls)

	rmaCallDurationSums = np.zeros((totalRanks, totalCallTypes), float)
	rmaCallDurationSquares = np.zeros((totalRanks, totalCallTypes), float)
	rmaOcurrencesPerRank = np.zeros((totalRanks, totalCallTypes), int)

	# 3rd dimension is 4 for min, max, average, std dev
	perCallPerRankStatistics = np.zeros((totalRanks, totalCallTypes, 4), float)
	perCallStatistics = np.zeros((totalCallTypes, 4), float)

	fileOffsets = np.zeros(totalRanks, int)

	filesFinished = np.full(totalRanks, False)

	windows = set()
	communicators = set()

	current_fence_data = 0
	epochs = 0 # we may have multiple windows
	
	epochData = [[] for x in range(totalRanks)]
	epochDataPerRank = []

	logging.debug(f'rma profiler: parse_trace_per_epoch: epochData is {epochData}')

	
	while (not np.all(filesFinished)):
		rank = 0 # will use this as index  to numpy arrays with statistics
		
		produce_epoch_statistics(epochData)

		epochData = [[] for x in range(totalRanks)]

		for filepath in ordered_ascii_files:

			if filesFinished[rank] == False:

				monitoring_call = 0
				epochDataPerRank = []
				
				if len(callCountPerRank) > rank:
					callCount = callCountPerRank[rank]
				else:
					callCount = 0


				file = open(filepath, 'r')

				if fileOffsets[rank] == 0:
					line = next(file)
					line = line.strip()
					linesplit = re.split(' |, ', line)

					start_time = float(linesplit[6]) * 1000000 # convert to usec right away

					
				file.seek(fileOffsets[rank])

				# from https://www.geeksforgeeks.org/python-how-to-search-for-a-string-in-text-files/
				line = file.readline()
				while line:
					line = line.strip()
					linesplit = re.split(' |, ', line)

					if monitoring_call == 0:
						if linesplit[0] in rma_set and linesplit[1] == 'entering':
							monitoring_call = 1
							current_call = linesplit[0]
							rma_occurrences[current_call] += 1
							rmaOcurrencesPerRank[rank][int(rma_indexes[current_call])] += 1
							callCount+=1
							start_cpu_time = float(linesplit[6]) * 1000000 # convert to usec right away

					elif monitoring_call == 1:

						if 'win' in linesplit[1]: 
							#logging.debug((linesplit[1].split('='))[1])
							current_window = int((linesplit[1].split('='))[1])
							if current_call in  ('MPI_Win_create', 'MPI_Accumulate', 'MPI_Get', 'MPI_Put'):
								windows.add(current_window)

							"""if current_call == "MPI_Win_create":
								logging.debug(f'Rank {rank}: MPI_Win_create window {current_window}')
							if current_call == "MPI_Win_free":
								logging.debug(f'Rank {rank}: MPI_Win_free window {current_window}')
							"""

							if current_call == "MPI_Win_fence":
								logging.debug(f'rma profiler: parse_trace_per_epoch: Rank {rank}: MPI_Win_fence on window {current_window}')



						if 'comm' in linesplit[1]:
							if current_call == "MPI_Win_create":
								current_communicator = int((linesplit[1].split('='))[1])
								communicators.add(current_communicator)

							
						if linesplit[1] == 'returning':
							monitoring_call = 0
							end_cpu_time = float(linesplit[6]) * 1000000 # convert to usec right away
							current_duration_cpu = end_cpu_time - start_cpu_time


							curr_op_data = [current_window, current_call, start_cpu_time]
							logging.debug(f'rma profiler: parse_trace_per_epoch: curr_op_data: {curr_op_data}')
							epochDataPerRank.append(curr_op_data)

							#logging.debug(rma_indexes[current_call])

							rmaCallDurationSums[rank][int(rma_indexes[current_call])] += current_duration_cpu
							rmaCallDurationSquares[rank][int(rma_indexes[current_call])] += (current_duration_cpu*current_duration_cpu)

							if current_duration_cpu < perCallPerRankStatistics[rank][int(rma_indexes[current_call])][0] or perCallPerRankStatistics[rank][int(rma_indexes[current_call])][0] == 0:
								perCallPerRankStatistics[rank][int(rma_indexes[current_call])][0] = current_duration_cpu #new min

							if current_duration_cpu > perCallPerRankStatistics[rank][int(rma_indexes[current_call])][1]:
								perCallPerRankStatistics[rank][int(rma_indexes[current_call])][1] = current_duration_cpu #new max

							if current_call == 'MPI_Win_fence':
								fileOffsets[rank] = file.tell()
								logging.debug(f'rma profiler: parse_trace_per_epoch: epochDataPerRank: {epochDataPerRank}')
								epochData[rank].append(epochDataPerRank)
								break
					line = file.readline()
				#logging.debug(f'File left at position {fileOffsets[rank]}')

				if line == '':
					filesFinished[rank] = True
					file.seek(fileOffsets[rank])
					line = file.readlines()[-1]
					line = line.strip()
					linesplit = re.split(' |, ', line)
					end_time = float(linesplit[6]) * 1000000 # convert to usec right away

					exec_time = end_time - start_time

				if len(callCountPerRank) > rank:
					callCountPerRank[rank] = callCount
				else:
					callCountPerRank.append(callCount)

				rank+=1
			else:
				# should I zero out something on perCallPerRankStatistics here?
				rank+=1
					#if(current_call == 'MPI_Win_fence'): # if the last rank has a finished file, the epoch does not get counted!

		if rank == totalRanks:
			logging.debug(f'rma profiler: parse_trace_per_epoch: -> Finished epoch: {epochs}')
			epochDataPerRank.append(current_fence_data)
			epochs+=1

	print(f'rma profiler: parse_trace_per_epoch:\tTotal epochs detected: {epochs-1}\n\t\t\t\t\tTotal windows detected: {len(windows)}\n\t\t\t\t\tTotal communicators detected: {len(communicators)}\n')

	
	# create summary per call and rank and per call in total
	# calculates min, max, average (mean) and std deviation
	
	for call in rma_tracked_calls:
		for i in range(0, totalRanks):
			if rmaOcurrencesPerRank[i][int(rma_indexes[call])] == 0:
				perCallPerRankStatistics[i][int(rma_indexes[call])][2] = 0
			else:
				perCallPerRankStatistics[i][int(rma_indexes[call])][2] = round(rmaCallDurationSums[i][int(rma_indexes[call])]/rmaOcurrencesPerRank[i][int(rma_indexes[call])], 3) # average

			if rmaOcurrencesPerRank[i][int(rma_indexes[call])] == 0 or rmaOcurrencesPerRank[i][int(rma_indexes[call])] == 1:
				perCallPerRankStatistics[i][int(rma_indexes[call])][3] = 0
			else:
				perCallPerRankStatistics[i][int(rma_indexes[call])][3] = round(math.sqrt(rmaCallDurationSquares[i][int(rma_indexes[call])]/rmaOcurrencesPerRank[i][int(rma_indexes[call])] - perCallPerRankStatistics[i][int(rma_indexes[call])][2]*perCallPerRankStatistics[i][int(rma_indexes[call])][2]), 3)  # std deviation
				
			if perCallStatistics[int(rma_indexes[call])][0] == 0 or perCallStatistics[int(rma_indexes[call])][0] > perCallPerRankStatistics[i][int(rma_indexes[call])][0]:
				perCallStatistics[int(rma_indexes[call])][0] = perCallPerRankStatistics[i][int(rma_indexes[call])][0]

			if perCallStatistics[int(rma_indexes[call])][1] < perCallPerRankStatistics[i][int(rma_indexes[call])][1]:
				perCallStatistics[int(rma_indexes[call])][1] = perCallPerRankStatistics[i][int(rma_indexes[call])][1]

		# compact way: 
		#print(perCallPerRankStatistics[:,int(rma_indexes[call]),1])

		if rma_occurrences[call] == 0:
			perCallStatistics[int(rma_indexes[call])][2] = 0
			perCallStatistics[int(rma_indexes[call])][3] = 0
		else:
			perCallStatistics[int(rma_indexes[call])][2] = round(sum(rmaCallDurationSums[:,int(rma_indexes[call])])/rma_occurrences[call], 3)
			if rma_occurrences[call] == 1:
				perCallStatistics[int(rma_indexes[call])][3] = 0
			else:
				perCallStatistics[int(rma_indexes[call])][3] = round(math.sqrt(sum(rmaCallDurationSquares[:,int(rma_indexes[call])])/rma_occurrences[call] - (perCallStatistics[int(rma_indexes[call])][2]*perCallStatistics[int(rma_indexes[call])][2])), 3)


	print_per_call(totalRanks, perCallPerRankStatistics, perCallStatistics, rma_indexes)	






	"""
		perCallStatistics[int(rma_indexes[call])][0] = min(rmaCallDurationSums[:,int(rma_indexes[call])])
		perCallStatistics[int(rma_indexes[call])][1] = max(rmaCallDurationSums[:,int(rma_indexes[call])])

		if rmaOcurrencesPerRank[i][int(rma_indexes[call])] == 0:
			perCallStatistics[int(rma_indexes[call])][2] = 0
			perCallStatistics[int(rma_indexes[call])][3] = 0
		else:
			perCallStatistics[int(rma_indexes[call])][2] = round(sum(rmaCallDurationSums[:,int(rma_indexes[call])])/rma_occurrences[call], 3)	
			perCallStatistics[int(rma_indexes[call])][3] = round((sum(rmaCallDurationSquares[:,int(rma_indexes[call])])/rma_occurrences[call]) - (perCallStatistics[int(rma_indexes[call])][2]*perCallStatistics[int(rma_indexes[call])][2]), 3)


	print_per_call(totalRanks, perCallPerRankStatistics, perCallStatistics, rma_indexes)

	"""

	"""print("Average RMA durations per rank:")
	for i in range(0, totalRanks):
		print("Rank " + str(i) + ":")
		print('MPI_Win_create: ' + str(rmaCallDurationSums[i][int(rma_indexes['MPI_Win_create'])]/rmaOcurrencesPerRank[i][int(rma_indexes['MPI_Win_create'])]) + 
				' | MPI_Get:' + str(rmaCallDurationSums[i][int(rma_indexes['MPI_Get'])]/rmaOcurrencesPerRank[i][int(rma_indexes['MPI_Get'])]) +
				' | MPI_Put:' + str(rmaCallDurationSums[i][int(rma_indexes['MPI_Put'])]/rmaOcurrencesPerRank[i][int(rma_indexes['MPI_Put'])]) +
				' | MPI_Accumulate:' + str(rmaCallDurationSums[i][int(rma_indexes['MPI_Accumulate'])]/rmaOcurrencesPerRank[i][int(rma_indexes['MPI_Accumulate'])]) +
				' | MPI_Win_free:' + str(rmaCallDurationSums[i][int(rma_indexes['MPI_Win_free'])]/rmaOcurrencesPerRank[i][int(rma_indexes['MPI_Win_free'])]) +
				' | MPI_Win_fence:' + str(rmaCallDurationSums[i][int(rma_indexes['MPI_Win_fence'])]/rmaOcurrencesPerRank[i][int(rma_indexes['MPI_Win_fence'])]))
		
	print("\nAverage RMA durations in total:")
	print('MPI_Win_create: ' + str(sum(rmaCallDurationSums[:,int(rma_indexes['MPI_Win_create'])])/rma_occurrences['MPI_Win_create']) + 
				' | MPI_Get:' + str(sum(rmaCallDurationSums[:,int(rma_indexes['MPI_Get'])])/rma_occurrences['MPI_Get']) + 
				' | MPI_Put:' + str(sum(rmaCallDurationSums[:,int(rma_indexes['MPI_Put'])])/rma_occurrences['MPI_Put']) + 
				' | MPI_Accumulate:' + str(sum(rmaCallDurationSums[:,int(rma_indexes['MPI_Accumulate'])])/rma_occurrences['MPI_Accumulate']) + 
				' | MPI_Win_free:' + str(sum(rmaCallDurationSums[:,int(rma_indexes['MPI_Win_free'])])/rma_occurrences['MPI_Win_free']) + 
				' | MPI_Win_fence:' + str(sum(rmaCallDurationSums[:,int(rma_indexes['MPI_Win_fence'])])/rma_occurrences['MPI_Win_fence']))
	#filter_calls_per_rank(rma_allranks, windows_per_node, total_exec_times)
	#fence_summary(rma_allranks, windows_per_node) """


	return rma_occurrences





def read_footers_native(dirname, timestamp):

	cc = { i : 0 for i in rma_all_calls } # for Call Count

	os.system('rm -f validate.temp')

	filenames = []

	for file in glob.glob(str(dirname)+'/dumpi-'+str(timestamp)+'*.bin'):
		filenames.append(file)


	# ordered_files = sorted(os.listdir(format(str(dirname))))
	ordered_files = sorted(filenames)

	for tracefile in ordered_files:
		#if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
		#logging.debug(tracefile)
		for call in rma_all_calls:
			callLine = str(subprocess.check_output('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -F '+tracefile+' | grep -w '+call, shell=True))
			cleanline = callLine.strip("b'|\\n|\n").split(' ')			
			(k, v) = (str(call), int(cleanline[2]))
			#logging.debug(cleanline, k, v)

			cc[k] = v+cc[k]
		#logging.debug (cc)
	return cc


def validate_count(call_count, rma_occurrences):

	totalCallCount = 0

	if len(call_count) != len(rma_occurrences):
		print ('Exception: discrepancy in tracked calls list!')
		sys.exit()
	for (k,v), (kk, vv) in zip(call_count.items(), rma_occurrences.items()):
		if k.strip(' ') != kk.strip(' '):
			print(f'rma profiler: validate_count: Exception: discrepancy of tracked RMA calls! {k} vs {kk}')
			sys.exit()
		if v != vv:
			print(f'rma profiler: validate_count: Exception: discrepancy of occurence count for RMA call {kk}!')
			sys.exit()
		totalCallCount += v
	print('rma profiler: validate_count: RMA occurrence count validation successful.')

	callCountPerRankSum = sum(callCountPerRank)

	if (totalCallCount != callCountPerRankSum):
		print(f'rma profiler: validate_count: Exception: discrepancy of total calls count and rma call count sum!')
		sys.exit()
	print('rma profiler: validate_count: total calls count consistent.')
	os.system('rm -f validate.temp')




def main():

	global dirname, timestamp

	action = 'r'
	cmdlnaction = False

	# default log level:
	level=logging.INFO

	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]

	# from https://www.datacamp.com/community/tutorials/argument-parsing-in-python

	try: 
		if len(argv) < 4 or len(argv) > 8:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ]')
			sys.exit(2)
		else:
			opts, args = getopt.getopt(argv, 'd:t:a:l:')
			for o, a in opts:
				if o == "-d": 
					dirname = a
				elif o == "-t":
					timestamp = a
				elif o == "-a":
					action = a
					cmdlnaction = True
				elif o == "-l":
					level=set_log_level(a)
					if level is None:
						raise ValueError("No such logging level! Must be one of: {critical, error, warn, warning, info, debug}")
						#sys.exit(2)
				else: 
					assert False, "No such command-line option!"
					sys.exit(2)
			#logging.debug('rma profiler: Directory name is : ' + format(str(dirname)))
			#logging.debug('rma profiler: Timestamp is : ' + format(str(timestamp)))
			
	except getopt.GetoptError:
		print ('Exception: wrong usage. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ] instead')
		sys.exit()


	# adjust log level to command line option
	#logging.basicConfig(level=logging.INFO)
	logging.basicConfig(level=level)


	rma_occurrences = parse_trace_per_epoch(rma_all_calls)


	cc = read_footers_native(dirname, timestamp)
	validate_count(cc, rma_occurrences)



"""

	while action != 'q':
		if (not cmdlnaction):
			if action == 'r':
				print('--------------------------------------------\n- Options -\n' + 
				'\te: Statistics per epoch (fence-based synchronization)\n' + 
				'\tf: Fence statistics\n' + 
				'\tc: Time spent in calls (per rank)\n' + 
				'\tr: Reprint options\n' + 
				'\tq: Quit\n')
			action = input('Please select action: ')

		if action == 'q':
			sys.exit()
		elif action == 'e': #
			find_epochs()
		elif action == 'f':
			fence_summary()
		elif action == 'c':
			filter_calls_per_rank()
		elif action == 'r':
			pass
		else:
			print('Invalid action option!')
			action = 'r'

		if cmdlnaction:
			sys.exit()

""" 	


# from https://realpython.com/python-main-function/#a-basic-python-main 
# "What if you want process_data() to execute when you run the script from 
# the command line but not when the Python interpreter imports the file?"
if __name__ == "__main__":
	main()