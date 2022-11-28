# foRMA internal representation of op data

foRMA relies on pydumpi in order to parce the traces provided as input, in order to extract any necessary timing information so as to provide a timing analysis. 

Such statistics could be calculated a posteriori, i.e. once all relevant timing info has been extracted from the trace, or incrementally, i.e. by updating a calculation each time new timing info is gathered. 

The present version carries out a posteriori calculations, and thus, must keep teh extracted timing information, either in a file or in memory. 

For the in memory case, the internal structure in which the trace is then represented, takes the form of a multi-dimension vector, referred to in the Python script as `opdata_per_rank`. The lowest-level  granularity of elements in this vector is the timing info of some RMA operation in the execution, summarized in an array, referred to in the Python script as `opdata`, that contains the following information: 
- `opdata[0]`: RMA opcode
- `opdata[1]`: Op start time (wall)
- `opdata[2]`: Op duration (CPU)
- `opdata[3]`: Data volume transferred (Bytes)
- `opdata[4]`: Data transfer bound
  

In order to access a particular operation in  `opdata_per_rank`, the following indexing is used: 
```
opdata_per_rank[rank_id][win_id][win_epoch][op_in_epoch]
```