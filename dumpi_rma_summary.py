import getopt 
import sys 
import os
import re
import fnmatch 


def fence_summary(rma_allranks, windows_per_node):
	print('Creating fence synch summary.')
	print(rma_allranks)

	window_union = set().union(*windows_per_node)
	print(window_union)


def parse_trace():
	# Get the arguments from the command-line except the filename
	argv = sys.argv[1:]

	print('Number of arguments: {}'.format(len(argv)))
	print('Argument(s) passed: {}'.format(str(argv)))

	rma_all_calls = ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']

	rma_tracked_calls =  ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Get', 'MPI_Put', 'MPI_Accumulate', 'MPI_Win_free']
	rma_set = frozenset(rma_tracked_calls)



	# from https://www.datacamp.com/community/tutorials/argument-parsing-in-python

	try: 
		if len(argv) < 4:
			print ('usage: ' + str(sys.argv[0]) + ' -d <directory name> -t <timestamp>')
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
			print('Directory name is : ' + format(str(dirname)))
			print('Timestamp is : ' + format(str(timestamp)))
			
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
	current_target = 0
	current_duration_wall = 0
	current_duration_cpu = 0

	calls_per_node = []
	wincount_per_node = []
	windows_per_node = []
	rma_allranks = []


	#for filename in os.listdir(format(str(dirname))):
	for filename in ordered_files:
		if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
			#print('Filename is: '+filename)
			filepath = format(str(dirname))+'/'+format(str(filename))
			print('File path is: '+filepath)
			os.system('/home/lena/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > d2atemp.out')

			call_count = 0
			win_count = 0
			windows = set() 
		
			rma_node_timeseries = []

			file = open('d2atemp.out', 'r')
			# from https://www.geeksforgeeks.org/python-how-to-search-for-a-string-in-text-files/
			for line in file:
				line = line.strip()
				linesplit = re.split(' |, ', line)
				if linesplit[0] in rma_set:
					current_call = linesplit[0]
					# from https://www.delftstack.com/howto/python/how-to-split-string-with-multiple-delimiters-in-python/
					if linesplit[1] == 'entering':
						call_count += 1
						#print(current_call+' entering at wall time '+linesplit[4])
						start_wall_time = linesplit[4]
						#print('CPU time is '+linesplit[6])
						start_cpu_time = linesplit[6]
					if linesplit[1] == 'returning':
						#print(current_call+' returning at wall time '+linesplit[4])
						end_wall_time = linesplit[4]
						#print('CPU time is '+linesplit[6])
						end_cpu_time = linesplit[6]
						current_duration_wall = float(end_wall_time) - float(start_wall_time)
						current_duration_cpu = float(end_cpu_time) - float(start_cpu_time)

						if current_call == 'MPI_Win_fence': 
							opdata = (current_call, current_duration_cpu)
						else: 
							opdata = (current_call, current_duration_cpu, current_window, current_bytes, current_target)

						rma_node_timeseries.append(opdata)

				elif 'win' in linesplit[1]: 
					#print((linesplit[1].split('='))[1])
					current_window = (linesplit[1].split('='))[1]
					if current_window > win_count:
						win_count = current_window
					windows.add(current_window)
				elif 'origincount' in linesplit[1]: 
					#print((linesplit[1].split('='))[1])
					current_bytes = (linesplit[1].split('='))[1]
	#			elif 'origintype' in linesplit[1]: 
	#				#print(linesplit[2])
	#			elif 'targetcount' in linesplit[1]: 
	#				#print((linesplit[1].split('='))[1])
	#			elif 'targettype' in linesplit[1]: 
	#				#print(linesplit[2])
				elif 'rank' in linesplit[1]:
					current_target = (linesplit[1].split('='))[1]

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


	fence_summary(rma_allranks, windows_per_node)


def main():
	parse_trace()


# from https://realpython.com/python-main-function/#a-basic-python-main 
# "What if you want process_data() to execute when you run the script from 
# the command line but not when the Python interpreter imports the file?"
if __name__ == "__main__":
	main()
