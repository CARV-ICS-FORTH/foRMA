#!/usr/bin/bash

# read traced calls from file, store in array tracedCalls
filename="$1"
#echo "Tracked RMA calls: " 
tracedCalls=()
tracedCallsNums=()
while read -r line; do
    [[ "$line" =~ ^#.*$ ]] && continue
    name="$line"
 #   echo "footer_reader: $name"
    tracedCalls+=($name)
    tracedCallsNums+=0
done < "$filename"

# find directory and timestamp for which to find the footer of the dumpi traces
dir="$2"
ts="$3" 

#for each trace, read footer and count references to each call, store in array tracedCallsNums
#echo "footer_reader: Reading traces with timestamp $ts from directory $dir." 
for tracefile in `ls $dir/dumpi-$ts-*.bin`; do
	# echo "footer_reader: Examining $tracefile :" 
	for i in ${!tracedCalls[@]}; do
		callLine=`/home/kanellou/opt/sst-dumpi-11.1.0/bin/dumpi2ascii -F $tracefile | grep -w ${tracedCalls[$i]}` 
		callLineArray=($callLine)
		# echo "footer_reader: ${tracedCalls[$i]} occurs in $tracefile ${callLineArray[2]} times."
		# tracedCallsNums[$i]=$((${callLineArray[2]} + ${tracedCallsNums[$i]}))
		tracedCallsNums[$i]=$(( callLineArray[2] + tracedCallsNums[$i] ))
	done
done


# report call occurrences to results file 
results="$4"
# echo "footer_reader: Reporting results in file $4."
for i in ${!tracedCalls[@]}; do
	echo "footer_reader: ${tracedCalls[$i]} : ${tracedCallsNums[$i]}" >> $results
done
