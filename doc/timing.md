### Timing in the SST Dumpi trace library

Timing information provided by foRMA depends on the timestamps that are present in the tracefiles produced by Dumpi. This means that their accuracy is reliant on the precision and time meassurement methods employed by Dumpi. 


- Times are calculated in SST Dumpi by using _nanoseconds_ as lowest level granularity representation.
- Timing info is provided both in CPU and wall clock time.
- In the tracefiles, time values are stored as `uint16_t` for seconds and `uint32_t` for nanoseconds.
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
	- Wall clock time is retrieved using `clock_gettime()` and requesting the `_POSIX_MONOTONIC_CLOCK`  if the runtime system supports a monotonic clock (`_POSIX_MONOTONIC_CLOCK` is defined). Otherwise, `gettimeofday()` is used, provided it is available in the system. 
	- CPU time is retrieved using `clock_gettime()` and requesting the `CLOCK_PROCESS_CPUTIME_ID` sustem clock if the runtime system supports it (`_POSIX_CPUTIME` is defined), otherwise `getrusage()` is used, provided it is available in the system.   
	  
	If neither of the above options is available, whether for wall clock or cpu time, then the `sec` and `nsec` fields of the start and stop times of the functions default to '0'.

- Timing information is output to the trace after applying a time bias, which is the number of seconds at the start of the execution. This time bias is captured by function `libdumpi_init()` (defined in dumpi/libdumpi/init.c) and represented by `cpuoffset` and `walloffset`:

	```
	/* Finally, initialize the profile but leave the file unopened */
    {
      dumpi_clock cpu, wall;
      dumpi_get_time(&cpu, &wall);
      int cpuoffset = cpu.sec;
      int walloffset = wall.sec;
      dumpi_global->profile =
        dumpi_alloc_output_profile(cpuoffset, walloffset, 0);
    }
```
	This bias is then subtracted -- before printing into the tracefile -- from the start and stop time of the profiled call, as measured by Dumpi during execution. Function ` put_times()`, defined in dumpi/common/iodefs.h, serves this purpose:
	
	```
	/** Utility routine write timestamps to the stream */
  static inline void put_times(dumpi_profile *profile,
			       const dumpi_time *cpu, const dumpi_time *wall,
			       uint8_t config_mask)
  {
	    if(DO_TIME_CPU(config_mask)) {
	      put16(profile, (uint16_t)(cpu->start.sec - profile->cpu_time_offset));
	      put32(profile, cpu->start.nsec);
	      put16(profile, (uint16_t)(cpu->stop.sec - profile->cpu_time_offset));
	      put32(profile, cpu->stop.nsec);
	    }
	    if(DO_TIME_WALL(config_mask)) {
	      put16(profile, (uint16_t)(wall->start.sec - profile->wall_time_offset));
	      put32(profile, wall->start.nsec);
	      put16(profile, (uint16_t)(wall->stop.sec - profile->wall_time_offset));
	      put32(profile, wall->stop.nsec);
	    }
  }
```


(\*) **Regarding Dumpi runtime configuration**: The trace collection library, specifically `libdumpi` looks for file `dumpi.conf` in the working directory. The existence of a file is not a pre-requisit. In case it exists, it may specify configuration information, such as which calls to profile, what filename prefix to use for tracefiles, what type of timestamps to trace, etc. For further information, cf. with Section "Runtime configuration of the DUMPI trace library" in the [Dumpi user documentation](https://github.com/sstsimulator/sst-dumpi/blob/master/docs/user.dox).




 