#!/usr/bin/python3

import getopt 
import sys 
import os
import re
import fnmatch
import numpy as np
import collections

def filter_calls_per_rank():

	
	window_union = set().union(*windows_per_node)
	#print(window_union)

	print('Total of ' + str(len(window_union)) + ' windows in application.\n')

	for i in window_union:
		print('Summary for window ' + str(i) + '\n')
		transfers_per_window = []
		transfer_bytes_per_window = []
		for rma_calls in rma_allranks: # i.e. for each rank
			transfer_bytes = []
			transfers_per_rank = filter(lambda c: ((c[0] == 'MPI_Get' or c[0] == 'MPI_Put') and c[2] == i), rma_calls)
			transfers_per_window.append(transfers_per_rank)
			for transfer in transfers_per_rank:
				transfer_bytes.append(transfer[3])
			transfer_bytes_per_window.append(transfer_bytes)
		#atransfer_bytes_per_window = np.array(transfer_bytes_per_window)
		if len(transfer_bytes_per_window) == 0:
			print('No transfers for this window.')
			return
		bytes_for_window = 0
		for transfers in transfer_bytes_per_window:
			bytes_for_window = bytes_for_window + sum(transfers)
		print('Total bytes moved for window: ' + str(bytes_for_window) + '\n')

	print('\n>>> Creating MPI_Put/MPI_Get/MPI_Accumulate summary.\n')
	print('Op durations per rank (in u seconds):')
	
	get_op_durations = []
	put_op_durations = []
	acc_op_durations = []
	other_op_durations = []

	for i, rma_calls in enumerate(rma_allranks):
		print('\n*** RANK ' + str(i) + ' ***')
		
		#get_ops_per_rank = filter(lambda c: c[0] == 'MPI_Get', rma_calls)
		#put_ops_per_rank = filter(lambda c: c[0] == 'MPI_Put', rma_calls)

		get_ops_per_rank = []
		put_ops_per_rank = []
		acc_ops_per_rank = []
		other_ops_per_rank = []

		for call in rma_calls:
			if call[0] == 'MPI_Get':
				get_ops_per_rank.append(call)
			elif call[0] == 'MPI_Put':
				put_ops_per_rank.append(call)
			elif call[0] == 'MPI_Accumulate':
				acc_ops_per_rank.append(call)
			else:
				other_ops_per_rank.append(call)

		other_op_durations_per_rank = []
		for other_op in other_ops_per_rank:
			other_op_durations_per_rank.append(other_op[1])
		if len(other_op_durations_per_rank) != 0:
			other_op_durations.append(other_op_durations_per_rank)

		other_total = sum(other_op_durations_per_rank)

		get_op_durations_per_rank = []
		for get_op in get_ops_per_rank:
			get_op_durations_per_rank.append(get_op[1])
		if len(get_op_durations_per_rank) != 0:
			get_op_durations.append(get_op_durations_per_rank)
		#print('Get durations: ' + str(get_op_durations_per_rank))
		get_total = sum(get_op_durations_per_rank)
		
		put_op_durations_per_rank = []
		for put_op in put_ops_per_rank:
			put_op_durations_per_rank.append(put_op[1])
		if len(put_op_durations_per_rank) != 0:
			put_op_durations.append(put_op_durations_per_rank)
		#print('Put durations: ' + str(put_op_durations_per_rank))
		put_total = sum(put_op_durations_per_rank)
	
		acc_op_durations_per_rank = []
		acc_op_durations_per_op = collections.defaultdict(list)
		for acc_op in acc_ops_per_rank:
			acc_op_durations_per_rank.append(acc_op[1])
			acc_op_durations_per_op[acc_op[7]].append(acc_op[1])
		if len(acc_op_durations_per_rank) != 0:
			acc_op_durations.append(acc_op_durations_per_rank)
		#print('Put durations: ' + str(put_op_durations_per_rank))
		acc_total = sum(acc_op_durations_per_rank)


		
		total_rma_durations_per_rank = other_total + get_total + put_total + acc_total
		print('Total execution time: ' + str(round(total_exec_times[i], 3)) + ' | Total time spent in tracked RMA calls: ' 
										+ str(round(total_rma_durations_per_rank, 3)) + '\n')

		if len(get_op_durations_per_rank) != 0:
			print('Total time spent in MPI_Get: ' + str(round(get_total, 3)))
			print('(% of total exec time: ' + str(round((get_total/total_exec_times[i])*100, 3)) + '%)')
			print('Total MPI_Get observations processed: ' + str(len(get_op_durations_per_rank)))
			get_avg = get_total/len(get_op_durations_per_rank)
			get_min = min(get_op_durations_per_rank)
			get_max = max(get_op_durations_per_rank)
			print('Average \t\t| Min \t\t\t| Max')
			print(str(round(get_avg, 3)) + ' \t| ' 
				+ str(round(get_min, 3)) + ' \t| ' 
				+ str(round(get_max, 3)) + '\n' )
			print('Std dv: ' + str(round(np.std(get_op_durations_per_rank), 3)) + ' | Median: ' +  str(round(np.median(get_op_durations_per_rank), 3)) 
					+ ' |\n90%ile: ' + str(round(np.percentile(get_op_durations_per_rank, 90), 3)) 
					+ ' | 95%ile: '  + str(round(np.percentile(get_op_durations_per_rank, 95), 3)) 
					+ ' | 99%ile: '  + str(round(np.percentile(get_op_durations_per_rank, 99), 3)) + '\n')
		else:
			print('No MPI_Get instances for this rank.')

			
		if (len(put_op_durations_per_rank) != 0) :
			print('Total time spent in MPI_Put: ' + str(round(put_total, 3)))
			print('Total MPI_Get instances: ' + str(len(put_op_durations_per_rank)))
			put_avg = put_total/len(put_op_durations_per_rank)
			put_min = min(put_op_durations_per_rank)
			put_max = max(put_op_durations_per_rank)
			print('Average \t| Min \t\t| Max')
			print(str(round(put_avg, 3)) + ' \t| ' 
				+ str(round(put_min, 3)) + ' \t| ' 
				+ str(round(put_max, 3)) + '\n' )	
			print('Std dv: ' + str(np.std(put_op_durations_per_rank)) + ' | Median: ' +  str(np.median(put_op_durations_per_rank)) 
					+ ' |\n90%ile: ' + str(round(np.percentile(put_op_durations_per_rank, 90), 3)) 
					+ ' | 95%ile: '  + str(round(np.percentile(put_op_durations_per_rank, 95), 3)) 
					+ ' | 99%ile: '  + str(round(np.percentile(put_op_durations_per_rank, 99), 3)) + '\n')

		else:
			print('No MPI_Put instances for this rank.')

		if (len(acc_op_durations_per_rank) != 0) :
			print('Total time spent in MPI_Accumulate: ' + str(round(acc_total, 3)))
			print('Total MPI_Accumulate instances: ' + str(len(acc_op_durations_per_rank)))
			acc_avg = acc_total/len(acc_op_durations_per_rank)
			acc_min = min(acc_op_durations_per_rank)
			acc_max = max(acc_op_durations_per_rank)
			print('Average \t| Min \t\t| Max')
			print(str(round(acc_avg, 3)) + ' \t\t| ' 
				+ str(round(acc_min, 3)) + ' \t| ' 
				+ str(round(acc_max, 3)) + '\n' )
			for acc_optype in acc_op_durations_per_op: 
				print('Total time spent in MPI_Accumulate with ' + acc_optype + ' as reduce operation: ' 
						+ str(round(sum(acc_op_durations_per_op[acc_op[7]]), 3)))
		else:
			print('No MPI_Accumulate instances for this rank.')


def fence_summary():
	print('\n>>> Creating fence synch summary.\n')
	#print(rma_allranks)

	#window_union = set().union(*windows_per_node)
	#print(window_union)

	for i in window_union:
		print('Summary for window ' + str(i) + '\n')
		fences_per_window = []
		fence_durations_per_window = []
		for rma_calls in rma_allranks:
			fence_durations = []
			fences_per_rank = filter(lambda c: (c[0] == 'MPI_Win_fence' and c[2] == i), rma_calls)
			fences_per_window.append(fences_per_rank)
			for fence in fences_per_rank: 
				#print(fence)
				fence_durations.append(fence[1])
			#print(fence_durations)
			fence_durations_per_window.append(np.array(fence_durations))
		#print(fence_durations_per_window)
		afences_per_window = np.array(fence_durations_per_window)
		if afences_per_window.size == 0:
			print('No fences for this window.')
			return
		#print('Fence durations per rank (in seconds):')
		#print(afences_per_window)
		#print('afences type')
		#print(type(afences_per_window))
		#print('afences shape')
		#print(afences_per_window.shape)
		win_avg = np.mean(afences_per_window)
		win_min = np.min(afences_per_window)
		min_rank, min_fence_id, = np.where(afences_per_window == win_min) 
		win_max = np.max(afences_per_window)
		max_rank , max_fence_id, = np.where(afences_per_window == win_max) 
		print('\nAverage \t| Min (rank, fence rep) \t| Max (rank, fence rep)')
		print(str(round(win_avg, 3)) + ' \t\t| ' 
			+ str(round(win_min, 3)) + ' (' + str(int(min_rank)) + ', ' +  str(int(min_fence_id)) + ') \t\t\t| ' 
			+ str(round(win_max, 3)) + ' (' + str(int(max_rank)) + ', ' +  str(int(max_fence_id)) + ')\n')

		print('Statistics per fence instance:\n')
		columns = afences_per_window.shape[1]
		max_in_columns = np.max(afences_per_window, axis=0)
		fences_mean = np.mean(afences_per_window, axis=0)
		fences_std_dev = np.std(afences_per_window, axis=0)
		fences_median = np.median(afences_per_window, axis=0)
		fences_90p = np.percentile(afences_per_window, 90, axis=0)
		fences_95p = np.percentile(afences_per_window, 95, axis=0)
		fences_99p = np.percentile(afences_per_window, 99, axis=0)
		for i in range(columns): # i.e. for each fence iteration
			print('Instance ' + str(i) + '\n----------')
			straggler_row, straggler_col = np.where(afences_per_window == max_in_columns[i])
			print('Slowest: ' + str(round(max_in_columns[i], 3))  + ', rank '+  str(np.unique(straggler_row)))
			print('Mean:\t' + str(round(fences_mean[i], 3)) + '\nStd dv:\t' + str(round(fences_std_dev[i], 3)) + '\nmedian:\t' + str(round(fences_median[i], 3)) 
					+ '\n90%ile:\t' + str(round(fences_90p[i], 3)) + '\n95%ile:\t' + str(round(fences_95p[i], 3)) + '\n99%ile:\t' +  str(round(fences_99p[i], 3)) + '\n')



def find_epochs():
	print('Calculating MPI_Win_fence epochs...\n')

	epochs_done = 0
	current_epoch = []
	current_index = []
	current_fence_times = []

	total_ranks = len(rma_allranks)

	calls_of_rank_per_epoch = []
	calls_of_epoch = []

	for i in range(total_ranks):
		current_index.append(0)
		current_epoch.append(0)
		current_fence_times.append((0, 0))
		#call_indexes_for_epoch.append([])
	#print(current_index)

	# first off, negotiate init time differences between ranks
	base_wall_time = np.min(start_wall_times)
	#print(base_wall_time)
	wall_time_biases = [x - base_wall_time for x in start_wall_times]
	#print(wall_time_biases)

	bytes_per_epoch = []
	for i in range(len(window_union)):
		bytes_per_epoch.append(0)
	#print(bytes_per_epoch)


	while epochs_done == 0:

		if current_epoch[0] > 1:
			print('>>> Statistics for epoch ' + str(current_epoch[0]-1) + '\n')
			
			# print(f'Current fence times are: {current_fence_times}')
			min_arrival =  np.min(current_fence_times, axis=0)
			first_rank = np.argmin(current_fence_times, axis=0)[0]
			max_departure = np.max(current_fence_times, axis=0)
			last_rank = np.argmax(current_fence_times, axis=0)[1]

			print(f'First arrival at fence for epoch at: \t{round(min_arrival[0], 3)} wall clock time, is rank {first_rank}.'+
				f'\nLast exit from fence for epoch at: \t{round(max_departure[1], 3)} wall clock time, is rank {last_rank}.\n')
			print(f'Difference between first arrival - last exit for epoch: {round(max_departure[1]-min_arrival[0], 3)} us\n')

			print('Bytes moved for epoch:')
			for i in window_union:
				print(f'\tWindow {i}: {bytes_per_epoch[i-1]} bytes total.')
				bytes_per_epoch[i-1] = 0

			# calculate data transfer durations for last epoch
			# print(f'\nData transfer completion times for epoch: {calls_of_epoch}')
			dt_bounds_epoch = []
			for rank, calls_per_rank in enumerate(calls_of_epoch):
				dt_bounds_rank = []
				for call in calls_per_rank:
					dt_bound = current_fence_times[rank][1]-call[1]
					print(f'\tRank is {rank} - Call op is: {call[0]}, dt upper bound is {round(dt_bound, 3)} us.')
					dt_bounds_rank.append(dt_bound)
				#print(dt_bounds_rank)
				dt_bounds_epoch.append(dt_bounds_rank)

			#print(dt_bounds_epoch)

			if len(dt_bounds_epoch) != 0:
				#print('Total time spent in MPI_Get: ' + str(round(get_total, 3)))
				#print('(% of total exec time: ' + str(round((get_total/total_exec_times[i])*100, 3)) + '%)')
				#print('Total MPI_Get observations processed: ' + str(len(get_op_durations_per_rank)))
				#get_avg = get_total/len(get_op_durations_per_rank)
				#dt_min = min(dt_bounds_epoch)
				#dt_max = max(dt_bounds_epoch)
				dt_min = np.min(dt_bounds_epoch)
				min_rank, min_op, = np.where(dt_bounds_epoch == dt_min) 
				dt_max = np.max(dt_bounds_epoch)
				max_rank , max_op, = np.where(dt_bounds_epoch == dt_max) 

				print(f'Min \t\t\t| Max\n{round(dt_min, 3)} (rank {min_rank})\t| {round(dt_max, 3)} (rank {max_rank})')
				#print(str(round(get_avg, 3)) + ' \t| ' 
				#	+ str(round(get_min, 3)) + ' \t| ' 
				#	+ str(round(get_max, 3)) + '\n' )
				#print('Std dv: ' + str(round(np.std(get_op_durations_per_rank), 3)) + ' | Median: ' +  str(round(np.median(get_op_durations_per_rank), 3)) 
				#		+ ' |\n90%ile: ' + str(round(np.percentile(get_op_durations_per_rank, 90), 3)) 
				#		+ ' | 95%ile: '  + str(round(np.percentile(get_op_durations_per_rank, 95), 3)) 
				#		+ ' | 99%ile: '  + str(round(np.percentile(get_op_durations_per_rank, 99), 3)) + '\n')
			else:
				print('No data transfers for this epoch.')


		for rank, rma_calls in enumerate(rma_allranks): 	# i.e. for each rank
			#print('Rank is: ' + str(rank))

			calls_of_rank_per_epoch = []

			while current_index[rank] < len(rma_calls): # i.e while there are still calls to be processed for this rank
				current_call = rma_calls[current_index[rank]] # get current call data
				#print('Working on call ' + str(current_index[rank]) +  ': ' + current_call[0])
				
				if (current_call[0] == 'MPI_Win_fence'):
					#print('MPI_Win_fence found!')
					current_index[rank] += 1
					current_epoch[rank] += 1
					#current_fence_times[rank] = [(current_call[3]-start_wall_times[rank])*1000000, (current_call[4]-start_wall_times[rank])*1000000]
					current_fence_times[rank] = [(current_call[3]-wall_time_biases[rank]), (current_call[4]-wall_time_biases[rank])]
					#print('Starting epoch ' + str(current_epoch[rank]) + ' in rank ' + str(rank))
					break
				elif (current_call[0] not in {'MPI_Win_create', 'MPI_Win_free'}) :
					if current_epoch[rank] > 0: # have we started synchronizaton?
						#print(f'Call is {current_call[0]}. Bytes transferred in call: {current_call[5]}, Window is {current_call[2]}')
						bytes_per_epoch[current_call[2]-1] += current_call[5]
						#print(f'index of current call is {current_index[rank]}, rank is {rank}')
						calls_of_rank_per_epoch.append((current_call[0], current_call[3]-wall_time_biases[rank]))
				current_index[rank] += 1
			# here, all calls of an epoch of a rank have been processed
			if (rank == total_ranks-1):
				#print(current_index[rank])
				if current_index[rank] == len(rma_calls):
					epochs_done = 1

			#if call_indexes_for_rank_for_epoch != []:
			# print(f'Rank is {rank}, calls collected for epoch: {calls_of_rank_per_epoch}.')
			if len(calls_of_epoch) < rank+1:
				calls_of_epoch.append(calls_of_rank_per_epoch)
			else:
				calls_of_epoch[rank] = calls_of_rank_per_epoch
					#print(f'length of call_indexes_for_epoch is {len(call_indexes_for_epoch)}')
		# print(f'Calls for epoch {current_epoch[rank]-1} are {calls_of_epoch}')
		# here, all ranks are at the same synchronization phase

			




def parse_trace():

	global rma_allranks
	global windows_per_node
	global total_exec_times
	global start_wall_times
	global window_union

	#print('Number of arguments: {}'.format(len(argv)))
	#print('Argument(s) passed: {}'.format(str(argv)))

	rma_all_calls = ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']

	rma_tracked_calls =  ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']
	rma_set = frozenset(rma_tracked_calls)




	ordered_files = sorted(os.listdir(format(str(dirname))))
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

	calls_per_node = []
	wincount_per_node = []
	windows_per_node = []
	rma_allranks = []

	start_times = []
	end_times = []
	total_exec_times = []
	start_wall_times = []

	#for filename in os.listdir(format(str(dirname))):
	for filename in ordered_files:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			#print('Filename is: '+filename)
			filepath = format(str(dirname))+'/'+format(str(filename))
			#print('File path is: '+filepath)
			os.system('/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > d2atemp.out')

			call_count = 0
			win_count = 0
			windows = set() 
		
			rma_node_timeseries = []

			monitoring_call = 0

			i = 0 # read second line

			file = open('d2atemp.out', 'r')
			#next(file)
			line = next(file)
			line = line.strip()
			linesplit = re.split(' |, ', line)

			start_time = float(linesplit[6]) * 1000000 # convert to usec right away

			start_times.append(start_time)

			start_wall_times.append(float(linesplit[4])*1000000)

			#print(start_times)
			file.seek(0)

			# from https://www.geeksforgeeks.org/python-how-to-search-for-a-string-in-text-files/
			for line in file:
				line = line.strip()
				linesplit = re.split(' |, ', line)

				if monitoring_call == 0:
					if linesplit[0] in rma_set and linesplit[1] == 'entering':
						monitoring_call = 1
						current_call = linesplit[0]
						call_count += 1
						#print(current_call+' entering at wall time '+linesplit[4])
						start_wall_time = float(linesplit[4]) * 1000000 # convert to usec right away
						#print('CPU time is '+linesplit[6])
						start_cpu_time = float(linesplit[6]) * 1000000 # convert to usec right away

				elif monitoring_call == 1:
					if linesplit[1] == 'returning':
						monitoring_call = 0
						#print(current_call+' returning at wall time '+linesplit[4])
						end_wall_time = float(linesplit[4]) * 1000000 # convert to usec right away
						#print('CPU time is '+linesplit[6])
						end_cpu_time = float(linesplit[6]) * 1000000 # convert to usec right away
						current_duration_wall = end_wall_time - start_wall_time
						current_duration_cpu = end_cpu_time - start_cpu_time

						if current_call == 'MPI_Win_fence': 
							opdata = (current_call, current_duration_cpu, current_window, start_wall_time, end_wall_time)
						elif current_call == 'MPI_Accumulate':
							opdata = (current_call, current_duration_cpu, current_window, start_wall_time, end_wall_time, current_size, current_target, current_op)
						else: 
							opdata = (current_call, current_duration_cpu, current_window, start_wall_time, end_wall_time, current_size, current_target)

						rma_node_timeseries.append(opdata)
					elif 'win' in linesplit[1]: 
						#print((linesplit[1].split('='))[1])
						current_window = int((linesplit[1].split('='))[1])
						if current_window > win_count:
							win_count = current_window
						windows.add(current_window)
					elif 'origincount' in linesplit[1]: 
						#print((linesplit[1].split('='))[1])
						current_bytes = int((linesplit[1].split('='))[1])
					elif 'op' in linesplit[1]:
						#current_op = int((linesplit[1].split('='))[1])
						current_op = linesplit[2]
					elif 'origintype' in linesplit[1]: 
						#print(linesplit[2])
						current_type = linesplit[2]
						if current_type == '(MPI_INT)':
							current_size = 4 * current_bytes
						elif current_type == '(MPI_CHAR)' or current_type == '(MPI_BYTE)':
							current_size = 1 * current_bytes
					elif 'targetrank' in linesplit[1]:
						current_target = int((linesplit[1].split('='))[1])
			
			end_time = float(linesplit[6]) * 1000000 # convert to usec right away
			end_times.append(end_time)
			#print(end_times)

			exec_time = end_time - start_time
			total_exec_times.append(exec_time)
			#print(total_exec_times)
			
			#file.seek(0)
			#bdata = file.read()
			#print('Binary sentence', bdata)

			calls_per_node.append(call_count)
			windows_per_node.append(windows)
			#wincount_per_node.append(win_count)
			rma_allranks.append(rma_node_timeseries)
			file.close()
			os.system('rm d2atemp.out')
	#		print(rma_node_timeseries)

	window_union = set().union(*windows_per_node)

	#filter_calls_per_rank(rma_allranks, windows_per_node, total_exec_times)
	#fence_summary(rma_allranks, windows_per_node)




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
			#print('Directory name is : ' + format(str(dirname)))
			#print('Timestamp is : ' + format(str(timestamp)))
			
	except getopt.GetoptError:
		print ('Exception: wrong usage. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> [ -a <action> ] instead')
		sys.exit()


	parse_trace()

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

	


# from https://realpython.com/python-main-function/#a-basic-python-main 
# "What if you want process_data() to execute when you run the script from 
# the command line but not when the Python interpreter imports the file?"
if __name__ == "__main__":
	main()
