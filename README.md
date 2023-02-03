# What is foRMA

foRMA is a methodology and a tool for profiling MPI RMA operation timing, designed to process traces produced by [SST Dumpi](https://github.com/justacid/pydumpi). 

The tool offers timing analysis options such as statistics on data transfer volume and upper bound of data transfer duration, organized by RMA  synchronization epoch, statistics on fence execution duration, across ranks, statistics on total time spent in various MPI RMA calls.

⚠️ _Notice that currently, epochs are assumed to be based on fence synchronization (```MPI_Win_fence()```)_.

foRMA is agnostic of the source code or the executable that was used to produce traces. Instead, it processes the trace files of a given execution in order to come up with data on timing analysis. 

In its current implementation, foRMA consists of Python 3 scripting for parsing SST Dumpi trace files and extract timing information regarding MPI RMA operations from them. To do so, it takes advantage of the [pydumpi](https://github.com/justacid/pydumpi) module, which provides Python bindings for the SST Dumpi library. 

# Pre-requisites

Apart from an up-to-date Python 3, foRMA relies on the following (fast-forward to  [Getting Started](#getting-started) section for installation details.)

* **SST Dumpi**: Part of the popular SST simulator (http://sst-simulator.org/). Specifically, Dumpi is a library for instrumenting MPI calls so that they produce (referred to as the `dumpi` tool) or replay (referred to as the `undumpi` tool) a trace of the execution of an MPI program. The library is distributed under an open source license and can be downloaded from [GitHub](https://github.com/sstsimulator/sst-dumpi). 
* **Pydumpi**: A Python module which provides bindings for the SST dumpi trace library. Is is available at PyPi and can be installed through `pip3`. Its source code is also available at http://github.com/justacid/pydumpi.


# Getting Started

In order to run a timing analysis on the execution of an MPI program using the tool, the following steps need to be performed:

##### Step 0: Installation pre-requisites.
If you have SST Dumpi and Pydumpi installed in your system, you may skip to [Step 1](#step-1).


###### To install SST Dumpi
* Download SST Dumpi from [GitHub](https://github.com/sstsimulator/sst-dumpi).
* Once downloaded, change into the Dumpi directory and initialize the build system.

```
$ ./bootstrap.sh
```
* To build Dumpi, specify the preferred MPI compiler.

```
$ dumpi/build $ ../configure CC=mpicc CXX=mpicxx --enable-libdumpi --prefix=$DUMPI_PATH
```
The `--enable-libdumpi` flag is needed to configure the trace collection library. 

* Compile and install.

```
$ make
$ make install
``` 
After compiling and installing, a `libdumpi.$prefix` will be added to `$DUMPI_PATH/lib`.

For more information and detailed installation guidelines and instructions of use, please refer to a Dumpi tutorial, such as https://calccrypto.github.io/sst-macro/page_DumpiTutorial.html

###### To install Pydumpi
* Either from [PyPi](https://pypi.org/project/pydumpi/) \[_Linux systems only!_\]: 

```
$ pip3 install pydumpi
```

* or install from [GitHub](http://github.com/justacid/pydumpi):

```
$ git clone http://github.com/justacid/pydumpi
$ cd myproject
$ source venv/bin/activate
$ pip install ../pydumpi
```

For more information on Pydumpi, you can refer to the [local documentation](doc/pydumpi.md) about it.

⚠️ _Important notice:_ If you wish to have compatibility between the SST Dumpi version that is used by pydumpi and the SST Dumpi version that was used to create your tracefiles, please refer to section [Notes regarding pydumpi installation](doc/pydumpi.md) of the [local documentation](doc/pydumpi.md#notes-regarding-pydumpi-installation)  

##### Step 1: Compile the MPI program with SST Dumpi. 

Once Dumpi is installed, e.g. at a directory specified by `$DUMPI_PATH/`, you can compile your MPI program, e.g. `mpi-app` with the Dumpi library using a command such as:

```
$ mpicc mpi-app.c -L DUMPI_PATH/lib -ldumpi -o mpi-app
```


##### Step 2: Run program to produce traces. 

In order to run the program with N ranks with Dumpi, you can use a command such as:

```
$ mpirun -np N -x LD_LIBRARY_PATH = $LD_LIBRARY_PATH:DUMPI_PATH/lib mpi-app
```
The above command creates N files with the extension .bin as well as a file with the extension .meta. Each of the .bin files are named in the format `dumpi-<timestamp>-X.bin` , where `<timestamp>` is the timestamp of when the program was executed and X is the number of the rank, i.e. it takes values from 0 to N − 1. Each of the .bin files contains the trace of the execution for
the corresponding rank. We refer to those as trace files.

##### Step 3: Use foRMA on produced traces in order to obtain a timing analysis

Invoke the RMA Profiler on the tracefiles produced in the previous step. 

```
$ forma.py -d <trace dir> -t <timestamp> [-a <option>]
```
where `<trace dir>` is the directory where the SST Dumpi output traces are stored and `<timestamp>` is the timestamp in the filename of the trace. 


## foRMA Usage

The tool has a command line mode and an interactive mode. In order to execute the command line mode, use the optional `-a <option>` command line argument. This acts as a shortcut that will cause the tool to directly calculate the requested statistics and exit. In contrast, when the tool is executed in interactive mode (i.e. without the `-a <option>` command line argument), it offers the possibility of requesting various of the statistic options, one after the other.

The offered options are:

- `-e`: Produces statistics per epoch.
Outputs data transfer bounds and data volume information into file epochs.txt. Data is calculated by memory window found in the execution. For each memory window, the relevant information is organized by synchronization epochs on that window. 
- `-f`: Creates statistics on fence execution. 
Outputs first and last arrival to MPI_Win_fence instances in execution, into file fences.txt. Information is provided both as timestamp and rank ID.  
- `-c`: Creates statistics on time spent inside various MPI calls.
Outputs MPI RMA call durations and statistics on them, into file calls.txt. Data is calculated by rank found to participate in the execution. For each rank, information is organized by RMA opcode. 
- `-a`: Prepare a full analysis, i.e. calculate all of the above. Produces all three of the aforementioned output files. 

## Output
Independently of the provided command line argument, foRMA prepares a summary of total execution times and operation durations, as well as data transfer bounds and bytes transferred per memory window. This summary is printed out in the standard output. 

Further foRMA command line options result in detailed statistics per rank or memory window and epoch. These results are stored in files, for better readability and searchability. 

Both in the summaries as well as the detailed statistics, and both when presenting durations or data volumes, foRMA also calculates min, max, averages and medians, as well as standard deviations. The indexes labeled "aggregate" may refer to a sum of values across ranks (i.e. total execution time or total time spent in MPI_Get) or across windows (i.e. total bytes transferred in execution).



# Acknowledgements

We thankfully acknowledge the support of the European Commission and the Greek General Secretariat for Research and Innovation under the EuroHPC Programme through project DEEP-SEA (GA-955606). National contributions from the involved state members (including the Greek General Secretariat for Research and Innovation) match the EuroHPC funding.
