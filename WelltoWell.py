#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020

import logging, csv, time, os, re, json, uuid, datetime, argparse
import pandas as pd
import csv, re, uuid, datetime
import pandas as pd
import numpy as np
from WellLit.plateLighting import Well, PlateLighting
from WellLit.Transfer import Transfer, TransferProtocol, TError, TStatus

#TODO: regexp check on well names
#TODO: Write log files

DEST = 'destination-plate'


class WTWTransferProtocol(TransferProtocol):
	"""
	Extends base TP to handle multiple source plates
	"""
	def __init__(self, df=None, **kwargs):
		super(WTWTransferProtocol, self).__init__(**kwargs)
		self.transfers_by_plate = {}
		self.df = df
		if self.df is not None:
			self.buildTransferProtocol(df)

	def buildTransferProtocol(self, df):
		if df is not None:
			self.plate_names = df['PlateName'].unique()

			# organize transfers into a dict by unique_id, collect id's into lists by plateName
			for plate_name in self.plate_names:
				plate_df = df[df['PlateName'] == plate_name]
				plate_transfers = []
				for idx, plate_df_entry in plate_df.iterrows():
					src_plt = plate_df_entry[0]
					dest_plt = DEST
					src_well = plate_df_entry[1]
					dest_well = plate_df_entry[2]
					unique_id = str(uuid.uuid1())

					tf = Transfer(src_plt, dest_plt, src_well, dest_well, unique_id)
					plate_transfers.append(unique_id)
					self.transfers[unique_id] = tf

				self.transfers_by_plate[plate_name] = plate_transfers

			# produce numpy array of ids to be performed in a sequence, grouped by plate.
			current_idx = 0
			self.num_transfers = len(self.tp.transfers)
			self.tf_seq = np.empty(self.tp.num_transfers, dtype=object)

			for plate in self.plate_names:
				plate = self.transfers_by_plate[plate]
				for tf_id in plate:
					self.tf_seq[current_idx] = tf_id
					current_idx += 1

			self._current_idx = 0  # index in tf_seq
			self._current_plate = 0  # index in plate_names

			self.current_uid = self.tf_seq[self._current_idx]
			self.current_plate_name = self.plate_names[self._current_plate]
			self.num_plates = len(self.plate_names)
			self.plate_sizes = {}
			for plate in self.plate_names:
				self.plate_sizes[plate] = len(self.transfers_by_plate[plate])
			self.sortTransfers()

	def canUpdate(self):
		current_transfer = self.transfers[self.current_uid]

		if current_transfer['timestamp'] is None:
			return True
		else:
			self.log('Cannot update transfer: %s, status is already marked as %s' %
					 (current_transfer.id[0:8], current_transfer['status']))
			msg = self.msg
			if self.plateComplete():
				self.log('Plate %s is complete, press next plate to continue' % self.current_plate_name)
			raise (TError(msg + self.msg))
			return False

	def step(self):
		"""
		Moves index to the next transfer in a plate. If plate full or transfer complete, raises flag
		"""
		self.sortTransfers()
		self.canUndo = True

		if self.plateComplete():
			if self.protocolComplete():
				self.log('TransferProtocol is complete')
			else:
				self.log('Plate %s completed' % self.current_plate_name)
		else:
			self.current_idx_increment()

	def nextPlate(self):
		self.canUndo = False
		if self.plateComplete():
			if not self.protocolComplete():
				self.current_plate_increment()
				self.current_idx_increment()
				self.log('Plate %s loaded' % self.current_plate_name)
			else:
				self.log('TransferProtocol is complete')

		else:
			self.log('Warning: Plate %s not yet complete' % self.current_plate_name)
			skipped_transfers_in_plate = list(
				set(self.lists['uncompleted']) &
				set(self.transfers_by_plate[self.current_plate_name]))

			self.msg = 'Skipping this plate will skip %s remaining transfers. Are you sure?' % len(
				skipped_transfers_in_plate)

			if self.override:
				self.override = False
				# collect leftover transfers
				skipped_transfers_in_plate = list(
					set(self.lists['uncompleted']) &
					set(self.transfers_by_plate[self.current_plate_name]))

				# Mark uncomplete transfers as skipped for this plate
				for tf in skipped_transfers_in_plate:
					self.transfers[tf].updateStatus(TStatus.skipped)

				self.log('Remaining %s transfers in plate %s skipped' %
						 (len(skipped_transfers_in_plate), self.current_plate_name))

				if self.protocolComplete():
					pass
				else:
					self.current_plate_increment()
					self.current_idx_increment(steps=len(skipped_transfers_in_plate))
					self.log('Plate %s loaded' % self.current_plate_name)

	def plateComplete(self):
		for tf in self.transfers_by_plate[self.current_plate_name]:
			if self.transfers[tf].status == TStatus.uncompleted:
				return False
		return True

	def current_plate_increment(self):
		self._current_plate += 1
		self.synchronize()

	def current_plate_decrement(self):
		self._current_plate -= 1
		self.synchronize()

	def synchronize(self):
		self.current_uid = self.tf_seq[self._current_idx]
		self.current_plate_name = self.plate_names[self._current_plate]


class WellToWell:
	"""
	* Loads a csv file into a pandas DataFrame, checking for duplicates or invalid Well labels
	* Parses a validated DataFrame into a TransferProtocol
	* Updates Transfers on functions connected to user actions, i.e. next, skipped, failed
	* Writes Transfers to transferlog.csv
	"""


	def __init__(self, csv=None):
		self.csv = csv
		self.error_msg = ''
		self.df = None
		self.tp = None

		if self.csv is not None:
			self.loadCsv(csv)

	def tp_present(self):
		if self.tp is not None:
			return True
		else:
			self.log('No transferProtocol loaded into memory.')
			return False

	def next(self):
		if self.tp_present():
			self.tp.complete()

	def skip(self):
		if self.tp_present():
			self.tp.skip()

	def failed(self):
		if self.tp_present():
			self.tp.failed()

	def undo(self):
		if self.tp_present():
			self.tp.undo()

	def nextPlate(self):
		if self.tp_present():
			self.tp.nextPlate()

	def log(self, error):
		self.error_msg = error
		print(error)
		logging.info(error)

	def loadCsv(self, csv):
		try:
			self.df = pd.read_csv(csv)
			self.log('CSV file %s loaded' % csv)
		except:
			self.log('Failed to load file csv %s' % csv)
			return None

		hasSourDupes, msg_s = self.checkDuplicateSource()
		hasDestDupes, msg_d = self.checkDuplicateDestination()

		if hasSourDupes or hasDestDupes:
			self.log(str(msg_s) + msg_d)
			self.df = None
		else:
			self.tp = WTWTransferProtocol(df=self.df)
			self.log('TransferProtocol with %s transfers in %s plates created' %
					 (self.tp.num_transfers, self.tp.num_plates))

	def checkDuplicateDestination(self):
		hasDupes = False
		dupes_mask = self.df.duplicated(subset='TargetWell')
		dupes = self.df.where(dupes_mask).dropna()
		duplicates = set(dupes['TargetWell'].values)
		error_msg = ''

		if len(duplicates) == 0:
			return hasDupes, error_msg
		else:
			hasDupes = True

		for element in duplicates:
			subset = self.df.where(df['TargetWell'] == element).dropna()

			indices = []
			for index, row in subset.iterrows():
				indices.append(index)
				target = row['TargetWell']
			error_msg = error_msg + 'TargetWell %s is duplicated in rows %s' % (target, indices)
		return hasDupes, error_msg

	def checkDuplicateSource(self):
		plates = self.df['PlateName'].drop_duplicates().values

		hasDupes = False
		error_msg = []
		msg = ''

		for plate in plates:
			batch = self.df.where(self.df['PlateName'] == plate).dropna()

			dupes_mask = batch.duplicated(subset='SourceWell')
			dupes = batch.where(dupes_mask).dropna()
			duplicates = set(dupes['SourceWell'].values)

			if len(duplicates) == 0:
				continue
			else:
				hasDupes = True

			message = 'Plate %s has duplicates: \n ' % plate
			for element in duplicates:
				subset = batch.where(batch['SourceWell'] == element).dropna()

				indices = []
				for index, row in subset.iterrows():
					indices.append(index)
				msg = msg + 'SourceWell %s is duplicated in rows %s' % (element, indices) + '\n'

			error_msg.append(msg)
			msg = ''

		return hasDupes, error_msg