### Timing in the SST Dumpi trace library

- Times are calculated in SST Dumpi by using lowest level granularity representation in nanoseconds
- Time values are stored as uint16_t for seconds and uint32_t for nanoseconds
- Timing info is provided both in CPU and wall clock time
- Timing information is calculated by using a time bias, which is the number of seconds at the start of the execution. 
