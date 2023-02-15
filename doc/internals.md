# foRMA Structure and Iinternal Representations of Operation Data

## Overview

foRMA relies on pydumpi in order to parce the traces provided as input, in order to extract any necessary timing information so as to provide a timing analysis in the form of statistics such as operation duration min, max, and averages as well as estimation of upper bounds for data transfers. 

Such statistics could be calculated a posteriori, i.e. once all relevant timing info has been extracted from the trace, or incrementally, i.e. by updating a calculation each time new timing info is gathered. 

The present version carries out a posteriori calculations, and thus, must keep the extracted timing information until after a trace file is parsed. 

⚠️ _Notice that the SST Dumpi library produces one trace file per rank involved in an MPI execution. Thus, the trace of an execution is distributed among several trace files, an aspect which has to be taken into consideration when producing trace statistics_.

## foRMA Structure and Modules

foRMA relies on the use of the following four modules: 
* `forma_trace`. Contains the definition of FormaIMTrace, the foRMA-specific trace, a child class of DumpiTrace (cf. with documentation in [pydumpi.md](pydumpi.md)). Includes the definition of callbacks to be registered with the C back-end. 
* `forma_parse`. Provides the necessary functions to parse the trace files pertaining to an execution trace and to extract the required timing data into a vector-based format that is suitable for further processing. 
* `forma_stats`. Provides functions that can process the vector-based RMA timing representation and provide timing statistics by rank, by memory window, by memory window epoch, etc. 
* `forma_print`. Provides functions to print out the calculated statistics. 

## foRMA RMA op Data Representation

The foRMA-specific structure in which the data extracted from the trace is then represented, takes the form of several multi-dimension vector, the most important of which is referred to in the Python foRMA script as `opdata_per_rank`. 

The current version of foRMA assumes `MPI_Win_fence`-based synchronization. Therefore, it is designed around the concept of a memory window and its synchronization epochs. 

The RMA timing data of each trace is then organized by 
- rank (rank_id)
- memory window (win_id)
- window epoch (win_epoch)
- RMA operation in window epoch (op_in_epoch)

The lowest-level  granularity is the `opdata` vector, a vector that contains timing and data volume data for a single RMA (or RMA-related) operation. It is a vector of five elements that contain the following information:
- `opdata[0]`: RMA opcode. We use the following convention: 0 - `MPI_Get`, 1 - `MPI_Put`, 2 - `MPI_Accumulate`, and 3 - `MPI_Win_fence`.
- `opdata[1]`: Operation start time (wall clock). This is used as an estimate of data transfer start. 
- `opdata[2]`: Operation duration (wall clock).
- `opdata[3]`: Data volume transferred (Bytes). In the special case of MPI_Win_fence (`opdata[0]` == 3), this field is interpreted as the operation wall clock finishing time and is used to calculate the data transfer bounds of the epoch. 
- `opdata[4]`: Data transfer bound. While the previous elements are filled out while parsing a trace file, this field is calculated after parsing, given that it represents the duration of a data transfer, calculated  as the difference of `opdata[1]` and the end time of the next `MPI_Win_fence` op referring to that window.  In the special case of `MPI_Win_fence` (`opdata[0]` == 3), this field is not present.

Based on the above, it follows that in order to access the `opdata` vector of a particular operation in  `opdata_per_rank`, the following indexing is used: 
```
opdata_per_rank[rank_id][win_id][win_epoch][op_in_epoch]
```
