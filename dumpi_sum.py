import getopt 
import sys 
import os
import re
import fnmatch 

# Get the arguments from the command-line except the filename
argv = sys.argv[1:]

print('Number of arguments: {}'.format(len(argv)))
print('Argument(s) passed: {}'.format(str(argv)))

rma_tracked_calls = ['MPI_Win_create', 'MPI_Win_fence', 'MPI_Win_post', 'MPI_Win_start', 'MPI_Win_complete', 'MPI_Win_wait', 'MPI_Get', 'MPI_Put', 'MPI_Win_free']

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
current_duration_wall = 0
current_duration_cpu = 0

calls_per_node = []
max_dur_per_node = []
min_dur_per_node = []
avg_dur_per_node = []
max_bytes_per_node = []
min_bytes_per_node = []
avg_bytes_per_node = []

#for filename in os.listdir(format(str(dirname))):
for filename in ordered_files:
	if fnmatch.fnmatch(filename, 'dumpi-'+format(str(timestamp))+'*.bin'):
		#print('Filename is: '+filename)
		filepath = format(str(dirname))+'/'+format(str(filename))
		print('File path is: '+filepath)
		os.system('/home/lena/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -S '+filepath+' > d2atemp.out')

		call_count = 0
		min_dur = 0
		max_dur = 0
		avg_dur = 0

		file = open('d2atemp.out', 'r')
		# from https://www.geeksforgeeks.org/python-how-to-search-for-a-string-in-text-files/
		for line in file:
			linesplit = re.split(' |, ', line)
			#if 'MPI_Win_free' in line:
			#if linesplit[0] == 'MPI_Win_create':
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
					end_wall_time = linesplit[6]
					#print('CPU time is '+linesplit[6])
					end_cpu_time = linesplit[6]
					current_duration_wall = float(end_wall_time) - float(start_wall_time)
					current_duration_cpu = float(end_cpu_time) - float(start_cpu_time)
					if (min_dur == 0) or (current_duration_cpu < min_dur):
						min_dur = current_duration_cpu
					if current_duration_cpu > max_dur:
						max_dur = current_duration_cpu
					avg_dur = ((avg_dur * (call_count-1)) + current_duration_cpu) / call_count
			elif 'win' in linesplit[1]: 
				#print((linesplit[1].split('='))[1])
				current_window = (linesplit[1].split('='))[1]
#			elif 'origincount' in linesplit[1]: 
#				#print((linesplit[1].split('='))[1])
#			elif 'origintype' in linesplit[1]: 
#				#print(linesplit[2])
#			elif 'targetcount' in linesplit[1]: 
#				#print((linesplit[1].split('='))[1])
#			elif 'targettype' in linesplit[1]: 
#				#print(linesplit[2])

		#file.seek(0)
		#bdata = file.read()
		#print('Binary sentence', bdata)

		calls_per_node.append(call_count)
		min_dur_per_node.append(min_dur)
		max_dur_per_node.append(max_dur)
		avg_dur_per_node.append(avg_dur)

		file.close()
		os.system('rm d2atemp.out')

print('\n')
	
for i in range(len(calls_per_node)):
	print("Node {} has {} RMA calls in total.".format(i, calls_per_node[i]))
	print("Max call duration is {}.\nMin call duration is {}.\nAverage call duration is {}.\n".format(max_dur_per_node[i], min_dur_per_node[i], avg_dur_per_node[i]))


#sentence = 'Hello Python'
#file_encode = sentence.encode('ASCII')
#file.write(file_encode)
#file.seek(0)
#bdata = file.read()
#print('Binary sentence', bdata)
#new_sentence = bdata.decode('ASCII')
#print('ASCII sentence', new_sentence)
