### Timing in the SST Dumpi trace library


###### Measuring time in Dumpi
- Times in Dumpi are codified via the `dumpi_time` data type, which is a struct specified in file dumpi/common/types.h as:
	
	```
  /**
   * Aggregate the start- and stop-time for a given function.
   */
  typedef struct dumpi_time {
    dumpi_clock start;   /* stored as 6 bytes */
    dumpi_clock stop;    /* stored as 6 bytes */
  } dumpi_time;
	```
On the other hand, `dumpi_clock`, defined in dumpi/common/types.h as well, is the struct:

	```
  /**
   * This is effectively identical to struct timespec from time.h,
   * but some target platforms don't have high resolution timers.
   */
  typedef struct dumpi_clock {
    int32_t sec;
    int32_t nsec;
  } dumpi_clock;
	```
- Depending on the runtime configuration of SST Dumpi for a given MPI run, it can collect either wall clock time, CPU time, or both, for each profiled call (entering and exiting the call, cf. with `start` and `stop` fields in `struct dumpi_time`.)
	- Wall clock time is retrieved using `clock_gettime()` if the runtime system supports a monotonic clock (`_POSIX_MONOTONIC_CLOCK` is defined). Otherwise, `gettimeofday()` is used, provided it is available in the system. 
	- CPU time is retrieved using `clock_gettime()` if the runtime system supports it (`_POSIX_CPUTIME` is defined), otherwise `getrusage()` is used, provided it is available in the system. 

(\*) **Regarding Dumpi runtime configuration**: The trace collection library, specifically `libdumpi` looks for file `dumpi.conf` in the working directory. The existence of a file is not a pre-requisit. In case it exists, it may specify configuration information, such as which calls to profile, what filename prefix to use for tracefiles, what type of timestamps to trace, etc. For further information, cf. with Section "Runtime configuration of the DUMPI trace library" in the [Dumpi user documentation](https://github.com/sstsimulator/sst-dumpi/blob/master/docs/user.dox).

###### Regarding the trace:

- Times are calculated in SST Dumpi by using lowest level granularity representation in nanoseconds
- Time values are stored as uint16\_t for seconds and uint32\_t for nanoseconds
- Timing info is provided both in CPU and wall clock time
- Timing information is calculated by using a time bias, which is the number of seconds at the start of the execution. 