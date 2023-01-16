# Introduction

pydumpi is a Python module which provides bindings for the SST dumpi trace library. Is is available at PyPi and can be installed through pip and its source code is also available at http://github.com/justacid/pydumpi.

## Quick Start

For a quick-start guide, the user may refer to the [pydumpi project page at PyPi](https://pypi.org/project/pydumpi/0.1.2/) or the readme in the [pydumpi Github repository](https://github.com/justacid/pydumpi/blob/master/README.md)

## Usage in foRMA

The aim of foRMA is to parse trace files produced by an MPI execution in order to extract timing information that is relevant to RMA calls. 

The use of the SST Dumpi trace library creates binary traces that have a particular, sst-dumpi-specific, binary format, where, apart from a header and a footer, each traced MPI call is logged via a call record (cf. with SST dumpi documentation regarding the trace format [here](https://github.com/sstsimulator/sst-dumpi/blob/master/docs/traceformat.dox)). 

Unfortunately, these records are not of a fixed size neither of fixed semantics; rather, size and semantics depend on the call being profiled in the record and on specific dumpi configurations for the particular run that produced the trace. 

The above render it impossible for foRMA to simply parse the trace file skipping from record to record based on record size. Instead, foRMA would have to interpret each record based on the SST Dumpi format, in order to determine the position of the following record, and so, detect those records that refer to RMAs. Furthermore, foRMA would then also have to re-implement the SST Dumpi binary format in order to decode the timing information encoded in the call records. 

The use of pydumpi solves this problem: it provides bindings to the SST Dumpi library and avoids the need for re-implementation in Python. Specifically, pydumpi provides bindings to the [libundumpi tool](https://github.com/sstsimulator/sst-dumpi/blob/master/docs/tools.dox) of the SST Dumpi library, which is an interface that parses Dumpi trace files and invokes a callback for each profiled MPI function. Among other things, pydumpi provides bindings to these callbacks, allowing foRMA to use those callbacks in order to efficiently parse a trace file. 

# pydumpi Module Descriptions

The pydumpi repository contains the following modules:

* **callbacks.py**: Defines the `DumpiCallbacks` class, which simply exposes the C callback `struct` of the SST Dumpi library to Python. 
* **constants.py**: Defines the `DataType` class. This class is an enumeration of SST Dumpi data types and indicates an integer number to correspond to each data type. As the SST Dumpi binary trace files encode data types using an integer, this enumeration class serves to do the translation between trace file format and data type in the profiled call record. 
* **dtypes.py**: Contains a class definition for each one of the C data structures defined by SST Dumpi and thus, exposes them to Python. 
* **undumpi.py**: At the core of the pydumpi functionality lies the `DumpiTrace` class, defined in this module. This class represents the binary SST Dumpi trace and is meant to be used to read both metadata as well as profiled call data of a trace. A functionality that foRMA takes advantage of, is the possibility of creating custom callback functions by defining child classes of `DumpiTrace`. These custom callbacks allow foRMA to extract the desired timing information from the trace, in order to forward it to the foRMA calculation modules that provide the statistics.
* **util.py**: Contains some utility tools, such as functions for reading the meta files or detecting trace files in a directory. 


# The DumpiTrace class