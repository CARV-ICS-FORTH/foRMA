

###################################################################################
# RMA timing profiling using data from SST-Dumpi traces
# 
# In order to extract timing information from the traces, the following are assumed 
# about the corresponding executions:
#
# - Synchronization is based on MPI_Win_fence. PSCW and locks are not supported. 
# - Windows created by ranks belong to the same communicator. 
# - RMA epochs on different windows may overlap.
#
#	My convention:
#	-> using # to comment out code
#	-> using ## to add comments and explanation
#
###################################################################################

__author__ = "Lena Kanellou"
__version__ = "0.1.0"


"""This module defines project-level constants."""



""" The following constants are used in numpy arrays or lists 
throughout foRMA in order to index to the part of the list or 
array that is designated for holding statistics or values of 
that particular RMA opcode """

GET			= 0		# MPI_Get
PUT			= 1		# MPI_Put
ACC			= 2		# MPI_Accumulate
FENCE		= 3		# MPI_Win_fence
WIN_CR		= 4		# MPI_Win_create
WIN_FREE	= 5		# MPI_Win_free
INIT		= 6		# MPI_Init
FIN			= 7		# MPI_Finalize


""" The following constants are used in numpy arrays or lists 
throughout foRMA in order to index to the part of the list or 
array that is designated for holding the value of the corresponging 
metric """ 

AGR			= 0		# aggregate or total, i.e. sum of all samples
MIN			= 1 	# minimum
MAX			= 2		# maximum
AVG			= 3		# average or mean
MED			= 4		# median
STD			= 5		# standard deviation
VAR			= 6		# variance
