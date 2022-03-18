#!/usr/bin/python3

import getopt 
import sys 
import os
import re
import fnmatch
import numpy as np
import collections

def filter_calls_per_rank(rma_allranks, windows_per_node, total_exec_times):

	
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
			acc_op_durations_per_op[acc_op[5]].append(acc_op[1])
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
						+ str(round(sum(acc_op_durations_per_op[acc_op[5]]), 3)))
		else:
			print('No MPI_Accumulate instances for this rank.')


def fence_summary(rma_allranks, windows_per_node):
	print('\n>>> Creating fence synch summary.\n')
	#print(rma_allranks)

	window_union = set().union(*windows_per_node)
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
					+ '\n90%ile:\t' + str(round(fences_90p[i], 3)) + '\n95%ile:\t' + str(round(fences_95p[i], 3)) + '\n99%ile:\t' +  str(round(fences_99p[i], 3))+ '\n')



def find_epochs(rma_allranks, windows_per_node):
	print('Calculating MPI_Win_fence epochs...')

	epochs_done = 0
	current_epoch = []
	current_index = []
	total_ranks = len(rma_allranks)
	for i in range(total_ranks):
		current_index.append(0)
	for i in range(total_ranks):
		current_epoch.append(0)
	print(current_index)

	while epochs_done == 0:
		for rank, rma_calls in enumerate(rma_allranks): 	# i.e. for each rank
			print('Rank is: ' + str(rank))
			while current_index[rank] < len(rma_calls):
				current_call = rma_calls[current_index[rank]]
				if current_epoch[rank] > 0:
					print('collecting statistics')
				print('Working on call ' + str(current_index[rank]))
				if (current_call[0] == 'MPI_Win_fence'):
					#print('MPI_Win_fence found!')
					current_index[rank] += 1
					current_epoch[rank] += 1
					print('Starting epoch ' + str(current_epoch[rank]) + ' in rank ' + str(rank))
					if rank == total_ranks-1:
						print('printing statistics')
					break
				current_index[rank] += 1
			if (rank == 0):
				#print(current_index[rank])
				if current_index[rank] == len(rma_calls):
					epochs_done = 1
			




def parse_trace():
	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]

	#print('Number of arguments: {}'.format(len(argv)))
	#print('Argument(s) passed: {}'.format(str(argv)))

	rma_all_calls = ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']

	rma_tracked_calls =  ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']
	rma_set = frozenset(rma_tracked_calls)



	# from https://www.datacamp.com/community/tutorials/argument-parsing-in-python

	try: 
		if len(argv) < 4:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp>')
			sys.exit(2)
		else:
			opts, args = getopt.getopt(argv, 'd:t:')
			for o, a in opts:
				if o == "-d": 
					dirname = a
				elif o == "-t":
					timestamp = a
				else: 
					assert False, "No such command-line option!"
					sys.exit(2)
			#print('Directory name is : ' + format(str(dirname)))
			#print('Timestamp is : ' + format(str(timestamp)))
			
	except getopt.GetoptError:
		print ('Exception: wrong usage. Use  ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp> instead')
		sys.exit(2)

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

			start_time = linesplit[4]

			start_times.append(linesplit[4])
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
						start_wall_time = linesplit[4]
						#print('CPU time is '+linesplit[6])
						start_cpu_time = linesplit[6]

				elif monitoring_call == 1:
					if linesplit[1] == 'returning':
						monitoring_call = 0
						#print(current_call+' returning at wall time '+linesplit[4])
						end_wall_time = linesplit[4]
						#print('CPU time is '+linesplit[6])
						end_cpu_time = linesplit[6]
						current_duration_wall = ( float(end_wall_time) - float(start_wall_time)) * 1000000
						current_duration_cpu = ( float(end_cpu_time) - float(start_cpu_time) ) * 1000000

						if current_call == 'MPI_Win_fence': 
							opdata = (current_call, current_duration_cpu, current_window, start_wall_time, end_wall_time)
						elif current_call == 'MPI_Accumulate':
							opdata = (current_call, current_duration_cpu, current_window, current_size, current_target, current_op, start_wall_time, end_wall_time)
						else: 
							opdata = (current_call, current_duration_cpu, current_window, current_size, current_target, start_wall_time, end_wall_time)

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
			
			end_time = linesplit[4]
			end_times.append(linesplit[4])
			#print(end_times)

			exec_time = float(end_time) - float(start_time)
			total_exec_times.append(exec_time)
			#print(total_exec_times)
			
			#file.seek(0)
			#bdata = file.read()
			#print('Binary sentence', bdata)

			calls_per_node.append(call_count)
			windows_per_node.append(windows)
			wincount_per_node.append(win_count)
			rma_allranks.append(rma_node_timeseries)
			file.close()
			os.system('rm d2atemp.out')
	#		print(rma_node_timeseries)


	#filter_calls_per_rank(rma_allranks, windows_per_node, total_exec_times)
	#fence_summary(rma_allranks, windows_per_node)
	find_epochs(rma_allranks, windows_per_node)



def main():
	parse_trace()
	


# from https://realpython.com/python-main-function/#a-basic-python-main 
# "What if you want process_data() to execute when you run the script from 
# the command line but not when the Python interpreter imports the file?"
if __name__ == "__main__":
	main()
