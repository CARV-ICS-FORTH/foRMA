#!/usr/bin/python3

import getopt 
import sys 
import glob, os
import re
import fnmatch
import numpy as np
import collections
import subprocess

import matplotlib.pyplot as plt


#rma_all_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait']
# in the following, for the purposes of economically storing data relevant to each call in 1D or 2D arrays, 
# we will use an index number to correspond to each of the calls in the order they appear in the list, i.e., 
# 0 -> MPI_Win_create, 2 -> MPI_Win_Get, etc. 
rma_all_calls = ['MPI_Win_create', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free', 'MPI_Win_fence']
	
callCountPerRank = []

def parse_trace_per_epoch(rma_tracked_calls):


	rma_set = frozenset(rma_tracked_calls)
	
	# use this in order to later validate with the amount of each call detected in the trace footers
	rma_occurrences = { i : 0 for i in rma_tracked_calls }

	# use this in order to later validate with the amount of each call detected in the trace footers
	j = 0
	#rma_indexes = { i : a for i, a in enumerate(rma_tracked_calls) }
	rma_indexes = { i : a for a, i in enumerate(rma_tracked_calls) }
	print(rma_indexes)


	ordered_files_all = sorted(os.listdir(format(str(dirname))))
	ordered_files = []
	ordered_ascii_files = []

	for filename in ordered_files_all:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			filepath = format(str(dirname))+'/'+format(str(filename))
			ordered_files.append(filepath)
			ascii_filepath = filepath.strip('.bin')+'.ascii'
			os.system('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > ' + ascii_filepath)
			ordered_ascii_files.append(ascii_filepath)
	#print(ordered_ascii_files)

	totalRanks = len(ordered_files)
	totalCallTypes = len(rma_tracked_calls)

	rmaCallDurationSums = np.zeros((totalRanks, totalCallTypes), float)
	rmaOcurrencesPerRank = np.zeros((totalRanks, totalCallTypes), int)


	fileOffsets = np.zeros(totalRanks, int)

	filesFinished = np.full(totalRanks, False)

	
	while (not np.all(filesFinished)):
		rank = 0 # will use this as index  to numpy arrays with statistics

		for filepath in ordered_ascii_files:
			print('not done!'+str(rank))
			print('rma profiler: File path is: '+filepath)

			monitoring_call = 0
			
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
					if linesplit[1] == 'returning':
						monitoring_call = 0
						end_cpu_time = float(linesplit[6]) * 1000000 # convert to usec right away
						current_duration_cpu = end_cpu_time - start_cpu_time

						#print(rma_indexes[current_call])

						rmaCallDurationSums[rank][int(rma_indexes[current_call])] += current_duration_cpu

						if current_call == 'MPI_Win_fence':
							fileOffsets[rank] = file.tell()
							break;
				line = file.readline()
			print(f'File left at position {fileOffsets[rank]}')

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
	print('done')

	print("Average RMA durations per rank:")
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
	#fence_summary(rma_allranks, windows_per_node)

	for file in ordered_ascii_files:
		os.system('rm '+ file)

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
		#print(tracefile)
		for call in rma_all_calls:
			callLine = str(subprocess.check_output('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -F '+tracefile+' | grep -w '+call, shell=True))
			cleanline = callLine.strip("b'|\\n|\n").split(' ')			
			(k, v) = (str(call), int(cleanline[2]))
			#print(cleanline, k, v)

			cc[k] = v+cc[k]
		#print (cc)
	return cc


def validate_count(call_count, rma_occurrences):

	totalCallCount = 0

	if len(call_count) != len(rma_occurrences):
		print ('Exception: discrepancy in tracked calls list!')
		sys.exit()
	for (k,v), (kk, vv) in zip(call_count.items(), rma_occurrences.items()):
		if k.strip(' ') != kk.strip(' '):
			print(f'rma profiler: Exception: discrepancy of tracked RMA calls! {k} vs {kk}')
			sys.exit()
		if v != vv:
			print(f'rma profiler: Exception: discrepancy of occurence count for RMA call {kk}!')
			sys.exit()
		totalCallCount += v
	print('rma profiler: RMA occurrence count validation successful.')

	callCountPerRankSum = sum(callCountPerRank)

	if (totalCallCount != callCountPerRankSum):
		print(f'rma profiler: Exception: discrepancy of total calls count and rma call count sum!')
		sys.exit()
	print('rma profiler: total calls count consistent.')
	os.system('rm -f validate.temp')




def main():

	global dirname, timestamp

	action = 'r'
	cmdlnaction = False


	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]

	# from https://www.datacamp.com/community/tutorials/argument-parsing-in-python

	try: 
		if len(argv) < 4 or len(argv) > 6:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ]')
			sys.exit(2)
		else:
			opts, args = getopt.getopt(argv, 'd:t:a:')
			for o, a in opts:
				if o == "-d": 
					dirname = a
				elif o == "-t":
					timestamp = a
				elif o == "-a":
					action = a
					cmdlnaction = True
				else: 
					assert False, "No such command-line option!"
					sys.exit(2)
			#print('rma profiler: Directory name is : ' + format(str(dirname)))
			#print('rma profiler: Timestamp is : ' + format(str(timestamp)))
			
	except getopt.GetoptError:
		print ('Exception: wrong usage. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ] instead')
		sys.exit()


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





def tracked_calls_get():

	rma_tracked_calls = []

	with open('rmacalls.conf') as callfile:
		for line in callfile:
			if line[0] != '#':
				cleanline = line.strip('\n')
				rma_tracked_calls.append(cleanline)
	return rma_tracked_calls



def read_footers_bash(dirname, timestamp):

	cc = {} # for Call Count

	os.system('rm -f validate.temp')

	#subprocess.call('./footer_reader.sh rmacalls.conf ' + dirname + ' ' + timestamp + ' validate.temp', shell=True)
	os.system('./footer_reader.sh rmacalls.conf ' + dirname + ' ' + timestamp + ' validate.temp')
	print("Counting calls.")
	with open('validate.temp', 'r') as countfile:
		for line in countfile:
			cleanline = line.strip("\n")
			(k, v) = cleanline.split(":")
			cc[k] = int(v)
	return cc



def parse_trace(rma_tracked_calls):

	global rma_allranks
	global windows_per_node
	global total_exec_times
	global start_wall_times


	global statistic_labels

	rma_set = frozenset(rma_tracked_calls)
	
	# use this in order to later validate with the amount of each call detected in the trace footers
	rma_occurrences = { i : 0 for i in rma_tracked_calls }

	# use this in order to later validate with the amount of each call detected in the trace footers
	j = 0
	#rma_indexes = { i : a for i, a in enumerate(rma_tracked_calls) }
	rma_indexes = { i : a for a, i in enumerate(rma_tracked_calls) }
	print(rma_indexes)


	statistic_labels = ['Min', 'Max', 'Avg', 'Std Dev', 'Median', '90%ile', '95%ile', '99%ile']

	ordered_files_all = sorted(os.listdir(format(str(dirname))))
	ordered_files = []
	ordered_ascii_files = []

	for filename in ordered_files_all:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			filepath = format(str(dirname))+'/'+format(str(filename))
			ordered_files.append(filepath)
			ascii_filepath = filepath.strip('.bin')+'.ascii'
			os.system('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > ' + ascii_filepath)
			ordered_ascii_files.append(ascii_filepath)
	#print(ordered_ascii_files)

	totalRanks = len(ordered_files)
	totalCallTypes = len(rma_tracked_calls)

	rmaCallDurationSums = np.zeros((totalRanks, totalCallTypes), float)
	rmaOcurrencesPerRank = np.zeros((totalRanks, totalCallTypes), int)

	current_call = ''
	start_wall_time = 0
	end_wall_time = 0
	start_cpu_time = 0
	end_cpu_time = 0
	current_window = 0
	current_bytes = 0
	current_size = 0
	current_type = ''
	current_target = 0
	current_op = ''
	current_duration_wall = 0
	current_duration_cpu = 0


	callCount = 0


	start_wall_times = []
	fileOffsets = np.zeros((totalRanks, totalCallTypes), int)

	rank = 0 # will use this as index  to numpy arrays with statistics
	#for filename in os.listdir(format(str(dirname))):
	for filepath in ordered_ascii_files:
		print('rma profiler: File path is: '+filepath)
		# os.system('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > d2atemp.out')


		rma_node_timeseries = []

		monitoring_call = 0

		i = 0 # read second line

		#file = open('d2atemp.out', 'r')
		file = open(filepath, 'r')
		#next(file)
		line = next(file)
		line = line.strip()
		linesplit = re.split(' |, ', line)

		start_time = float(linesplit[6]) * 1000000 # convert to usec right away

		#start_times.append(start_time)

		start_wall_times.append(float(linesplit[4])*1000000)

		#print(start_times)
		file.seek(0)

		callCount = 0

		# from https://www.geeksforgeeks.org/python-how-to-search-for-a-string-in-text-files/
		for line in file:
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
				if linesplit[1] == 'returning':
					monitoring_call = 0
					end_cpu_time = float(linesplit[6]) * 1000000 # convert to usec right away
					current_duration_cpu = end_cpu_time - start_cpu_time

					#print(rma_indexes[current_call])

					rmaCallDurationSums[rank][int(rma_indexes[current_call])] += current_duration_cpu

				#elif
		#print(rmaCallDurationSums)


		end_time = float(linesplit[6]) * 1000000 # convert to usec right away
		#end_times.append(end_time)
		#print(end_times)

		exec_time = end_time - start_time
		#print(total_exec_times)
		
		#file.seek(0)
		#bdata = file.read()
		#print('rma profiler: Binary sentence', bdata)

		callCountPerRank.append(callCount)
		
		file.close()
		#os.system('rm d2atemp.out')
		rank+=1
#		print(rma_node_timeseries)

	print("Average RMA durations per rank:")
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
	#fence_summary(rma_allranks, windows_per_node)

	for file in ordered_ascii_files:
		os.system('rm '+ file)

	return rma_occurrences