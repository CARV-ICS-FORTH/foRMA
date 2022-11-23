# Introduction

foRMA is a methodology and a tool for profiling MPI RMA operation timing. It is designed to process traces produced by [SST Dumpi](https://github.com/justacid/pydumpi), and in its current implementation, it consists of Python 3 scripting that parses and extract timing information regarding MPI RMA operations in that trace. To do so, it takes advantage of the [pydumpi](https://github.com/justacid/pydumpi) module, which provides Python bindings for the SST Dumpi library. 

foRMA is agnostic of the source code or the executable that was used to produce traces. Instead, it processes the trace files of a given execution in order to come up with data on timing analysis. The tool offers timing analysis options such as statistics on data transfer volume and upper bound of data transfer duration, organized by RMA  synchronization epoch, statistics on fence execution duration, across ranks, statistics on total time spent in various MPI RMA calls.

⚠️ _Notice that currently, epochs are assumed to be based on fence synchronization (```MPI_Win_fence()```)_.


# How to use

In order to run a timing analysis on the execution of an MPI program using the tool, the following steps need to be performed:

1. Compile the MPI program with SST Dumpi.
2. Run program to produce traces.
3. Use RMA Profiler on produced traces in order to obtain a timing analysis.

These steps are detailed below.
##### Step 1: Compile the MPI program with SST Dumpi. 
Dumpi is part
of the popular SST simulator (http://sst-simulator.org/). Specifically, Dumpi is a library for instrumenting MPI calls so that they produce (referred to as the `dumpi` tool) or replay (referred to as the `undumpi` tool) a trace of the execution of an MPI program. The library is distributed under an open source license and can be downloaded from [GitHub](https://github.com/sstsimulator/sst-dumpi). 

For more information and detailed installation guidelines and instructions of use, please refer to a Dumpi tutorial, such as https://calccrypto.github.io/sst-macro/page_DumpiTutorial.html

##### Step 2: Run program to produce traces. 
Once Dumpi is installed, e.g. at a directory specified by `<DUMPI_PATH>`, you can compile your MPI program, e.g. mpi-ex with the Dumpi library using a command such as:
```$ mpicc mpi-ex.c -L <DUMPI_PATH>/lib -ldumpi -o mpi-ex
```
In order to run the program with N ranks with Dumpi, you can use a command such as:
```$ mpirun -np N -x LD_LIBRARY_PATH = $LD_LIBRARY_PATH:<DUMPI_PATH>/lib mpi-ex
```
The above command creates N files with the extension .bin as well as a file with the extension .meta. Each of the .bin files are named in the format `dumpi-<timestamp>-X.bin` , where `<timestamp>` is the timestamp of when the program was executed and X is the number of the rank, i.e. it takes values from 0 to N − 1. Each of the .bin files contains the trace of the execution for
the corresponding rank. We refer to those as trace files.
If nothing else is specified, those files are dumped inside the directory of execution of the MPI program. In order to control the location of the trace files, it is recommended to create a specific folder for collecting them. One way of specifying where to store trace files, is to include a dumpi.conf file with the relevant information, in the execution directory. For more information on the dumpi.conf file and for an example template, refer to the [Dumpi user manual](https://github.com/sstsimulator/sst-dumpi/blob/master/docs/user.dox), specifically, section ”Runtime configuration of the DUMPI trace library”.

##### Step 3: Use foRMA on produced traces in order to obtain a timing analysis

Invoke the RMA Profiler from command line as follows:
```$ forma.py -d <trace dir> -t <timestamp> [-a <option>]```
where `<trace dir>` is the directory where the SST Dumpi output traces are stored and `<timestamp>` is the timestamp in the filename of the trace. 

The tool has a command line mode and an interactive mode. In order to execute the command line mode, use the optional `-a <option>` command line argument. This acts as a shortcut that will cause the tool to directly
calculate the requested statistics and exit. In contrast, when the tool is executed in interactive mode (i.e. without the `-a <option>` command line argument),
it offers the possibility of requesting various of the statistic options, one after the other.

The offered options are:

- `-e`: Produces statistics per epoch.
- `-f`: Creates statistics on fence execution.
- `-c`: Creates statistics on time spent inside various MPI calls.
- `-a`: Prepare a full analysis, i.e. calculate all of the above. 

###### Output
Independently of the provided command line argument, foRMA prepares a summary of total execution times and operation durations, as well as data transfer bounds and bytes transferred per memory window. This summary is printed out in the standard output. 

Further foRMA command line options result in detailed statistics per rank or memory window and epoch. These results are stored in files, for better readability and searchability. 

Both in the summaries as well as the detailed statistics, and both when presenting durations or data volumes, foRMA also calculates min, max, averages and medians, as well as standard deviations. The indexes labeled "aggregate" may refer to a sum of values across ranks (i.e. total execution time or total time spent in MPI_Get) or across windows (i.e. total bytes transferred in execution).


# Acknowledgements

We thankfully acknowledge the support of the European Commission and the Greek General Secretariat for Research and Innovation under the EuroHPC Programme through project DEEP-SEA (GA-955606). National contributions from the involved state members (including the Greek General Secretariat for Research and Innovation) match the EuroHPC funding.
