#!/usr/bin/python3

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


class FormaTrace(DumpiTrace):

	def __init__(self, file_name, ext_var):
		super().__init__(file_name)
		#self.message_count = 0
		self.fence_count = 0
		self.win_count = 0
		self.wincreate_count = 0
		self.mylist = ext_var

		## DataVolumes per epoch per detected window for current trace. 
		## indexed by window ID (cf. window lookaside translation buffer wintb)
		#self.dv_perEpoch_perWindow = dict()
		self.wintb = dict()


	def on_win_fence(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		# count mpi_win_fence occurrences
		self.fence_count += 1

		## identify window key to use on windows dictionary by looking into wintb
		win_id = self.wintb[data.win]



	def on_win_create(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		self.win_count += 1
		self.wincreate_count += 1

		## on create, I update the window ID to index translation buffer
		## on free, I will free the corresponding entry
		## DEBUG attempt: I am using a check with -1 in order to detect eventual collisions
		if self.wintb: ## check first if dict is empty, otherwise nasty seg faults
			if data.win in (self.wintb).keys(): ## if NOT empty and key already exists... 
				if (self.wintb[data.win] != -1): ## ... check value, in case on_win_free has not yet been called on it
					print(f'COLLISION ON WINDOW ID {data.win}')
			#print('window tb not empty, key does not exist') 
			## otherwise, not empty, but key does not exist yet
			self.wintb[data.win] = self.win_count-1
		else:
			self.wintb[data.win] = self.win_count-1
			#print('window tb empty')


		win_id = self.wintb[data.win]


	def on_win_free(self, data, thread, cpu_time, wall_time, perf_info):
		self.wintb[data.win] = -1

	def on_get(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		win_id = self.wintb[data.win]


	def on_put(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		win_id = self.wintb[data.win]


	def on_accumulate(self, data, thread, cpu_time, wall_time, perf_info):
		time_diff = wall_time.stop - wall_time.start
		win_id = self.wintb[data.win]
