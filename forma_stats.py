#!/usr/bin/python3


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



import getopt 
import sys 
import glob, os
import re
import fnmatch
import numpy as np
import collections
import subprocess
import math
import pandas as pd

import gc

from bisect import insort

import matplotlib.pyplot as plt

import pandas as pd

import logging

from pydumpi import DumpiTrace

from ctypes.util import find_library

import forma_trace as ft
