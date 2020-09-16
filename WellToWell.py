#!/usr/bin/env python3
# Joana Cabrera
# 3/15/2020

import logging, csv, uuid, datetime, os, re, json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from WellLit.Transfer import Transfer, TransferProtocol, TError, TStatus, TConfirm


class WelltoWell:
	"""
	Class for importing and validating a csv file to build a database of well-to-well transfers
	* Loads a csv file into a pandas DataFrame, checking for duplicates or invalid Well labels
	* Parses a validated DataFrame into a TransferProtocol
	* Passes user commands (next, skip etc) to TransferProtocol
	* Writes Transfers to transferlog.csv

	Raises TError if user incorrectly specifies csv source file, or uses gui before transfer is loaded
	"""

	def __init__(self):
		self.csv = ''
		self.msg = ''
		self.df = None
		self.tp = None
		self.timestamp = ''
		self.dest_plate = ''

		cwd = os.getcwd()
		config_path = os.path.join(cwd, "wellLitConfig.json")
		with open(config_path) as json_file:
			configs = json.load(json_file)

		self.save_path = configs['records_dir']
		self.load_path = configs['protocol_dir']
		self.num_wells = configs['num_wells']

		if not os.path.isdir(self.save_path):
			self.save_path = cwd + '/records/'

		if not os.path.isdir(self.load_path):
			self.save_path = cwd + '/protocols/'

	def reset(self):
		self.csv = ''
		self.msg = ''
		self.df = None
		self.tp = None
		self.timestamp = ''
		self.dest_plate = ''

	def tp_present_bool(self):
		if self.tp is not None:
			return True
		else:
			return False

	def tp_present(self):
		if self.tp is not None:
			return True
		else:
			self.log('No Transfer Protocol loaded. \n Load a CSV file to begin')
			raise TError(self.msg)

	def next(self):
		if self.tp_present():
			self.tp.complete()
			self.writeTransferRecordFiles(None)

	def skip(self):
		if self.tp_present():
			self.tp.skip()
			self.writeTransferRecordFiles(None)

	def failed(self):
		if self.tp_present():
			self.tp.failed()
			self.writeTransferRecordFiles(None)

	def undo(self):
		if self.tp_present():
			self.tp.undo()
			self.writeTransferRecordFiles(None)

	def nextPlate(self):
		if self.tp_present():
			self.tp.nextPlate()

	def nextPlateOverride(self):
		if self.tp_present():
			self.tp.nextPlateOverride()

	def nextPlateConfirm(self):
		if self.tp_present():
			self.tp.nextPlateConfirm()

	def log(self, msg):
		self.msg = msg
		logging.info(msg)

	def finishTransferProtocol(self):
		self.timestamp = ''

	def loadCsv(self, csv):
		"""
		Validates a csv file as being free of duplicates before loading constructing a TransferProtocol from it

		:param csv: absolute path to csv to be used

		Raises TError if there are problems importing the file
		Raises TConfirm if the file loads successfully
		"""
		try:
			# read the first line of the csv as the destination plate name
			self.dest_plate = list(pd.read_csv(csv, nrows=0))[0]
			self.df = pd.read_csv(csv, skiprows=1, names=['PlateName', 'SourceWell', 'DestWell'])
			self.log('CSV file %s loaded' % csv)
			self.csv = csv
		except:
			self.log('Failed to load file csv \n %s' % csv)
			raise TError(self.msg)

		hasSourDupes, msg_s = self.checkDuplicateSource()
		self.checkWellNames()
		if hasSourDupes:
			self.log('CSV file has duplicate well sources')
			raise TError(self.msg)
		else:
			self.tp = WTWTransferProtocol(wtw=self, df=self.df)
			self.log('TransferProtocol with %s transfers in %s plates created' %
					 (self.tp.num_transfers, self.tp.num_plates))
			self.timestamp = datetime.utcnow().strftime('%Y_%m_%d_%H_%M_%S')
			load_plate_msg = '\n Please load plate ' + self.tp.current_plate_name + ' to begin'
			raise TConfirm(self.msg + load_plate_msg)

	def checkWellNames(self):
		if self.num_wells == "384":
			for row_idx, well_name in enumerate(list(self.df['SourceWell'])):
				if well_name == np.nan:
					raise TError('Missing well name in row %s or improperly formatted csv' % str(row_idx + 2))
				if not re.match(r'([a-p]|[A-P])([1-9](?!.)|1[0-9]|2[0-4])', well_name):
					raise TError('Invalid source well name %s in row %s of csv file' % (well_name, str(row_idx + 2)))

			for row_idx, well_name in enumerate(list(self.df['DestWell'])):
				if well_name == np.nan:
					raise TError('Missing well name in row %s or improperly formatted csv' % str(row_idx + 2))
				if not re.match(r'([a-h]|[A-H])([1-9](?!.)|1[0-9]|2[0-4])', well_name):
					raise TError(
						'Invalid destination well name %s in row %s of csv file' % (well_name, str(row_idx + 2)))

		else:
			for row_idx, well_name in enumerate(list(self.df['SourceWell'])):
				if well_name == np.nan:
					raise TError('Missing well name in row %s or improperly formatted csv' %str(row_idx + 2))
				if not re.match(r'([a-h]|[A-H])([1-9](?!.)|1[0-2])', well_name):
					raise TError('Invalid source well name %s in row %s of csv file' %(well_name, str(row_idx + 2)))

			for row_idx, well_name in enumerate(list(self.df['DestWell'])):
				if well_name == np.nan:
					raise TError('Missing well name in row %s or improperly formatted csv' % str(row_idx + 2))
				if not re.match(r'([a-h]|[A-H])([1-9](?!.)|1[0-2])', well_name):
					raise TError('Invalid destination well name %s in row %s of csv file' %(well_name, str(row_idx + 2)))

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
			subset = self.df.where(self.df['TargetWell'] == element).dropna()

			indices = []
			for index, row in subset.iterrows():
				indices.append(index)
				target = row['TargetWell']
			error_msg = error_msg + 'TargetWell %s is duplicated in rows %s ' % (target, indices)
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

			for element in duplicates:
				subset = batch.where(batch['SourceWell'] == element).dropna()

				indices = []
				for index, row in subset.iterrows():
					indices.append(index)
				msg = msg + 'SourceWell %s is duplicated in rows %s' % (element, indices)

			error_msg.append(msg)
			msg = ''

		return hasDupes, error_msg

	def abortTransfer(self):
		if self.tp_present():
			self.tp = None
			self.df = None

	def writeTransferRecordFiles(self, _):
		csv_filename = Path(self.csv).stem
		filename = Path(csv_filename + '_' + 'transfer_record_' + self.timestamp + '.csv')
		record_path_filename = Path(self.save_path + str(filename))
		try:
			with open(record_path_filename, mode='w') as logfile:
				log_writer = csv.writer(logfile, delimiter=',')
				log_writer.writerow(['Timestamp', 'Source plate', 'Source well', 'Destination plate', 'Destination well', 'Status'])
				keys = ['timestamp', 'source_plate', 'source_well', 'dest_plate', 'dest_well', 'status']
				for transfer_id in self.tp.tf_seq:
					transfer = self.tp.transfers[transfer_id]
					if transfer['status'] is not 'uncompleted':
						log_writer.writerow([transfer[key] for key in keys])
			self.log('Wrote transfer record to ' + str(record_path_filename))
		except:
			raise TError('Cannot write log file to ' + str(record_path_filename))


class WTWTransferProtocol(TransferProtocol):
	"""
	TransferProtocol that handles multiple source plates when transferring well-to-well.
	Implements buildTransferProtocol, step from parent class.
	Overrides default synchronize and canUpdate methods.

	Raises TError if user tries to skip incomplete source plate
	"""
	def __init__(self, wtw=None, df=None, **kwargs):
		super(WTWTransferProtocol, self).__init__(**kwargs)
		self.transfers_by_plate = {}
		self.df = df
		self.msg = ''
		if self.df is not None:
			self.buildTransferProtocol(wtw, df)

	def buildTransferProtocol(self, wtw, df):
		"""
		Builds a transfer protocol for well to well transfers
		:param wtw: parent well to well object
		:param df: pandas dataframe containing transfer information
		:return:
		"""
		if df is not None:
			self.plate_names = df['PlateName'].unique()

			# organize transfers into a dict by unique_id, collect id's into lists by plateName
			for plate_name in self.plate_names:
				plate_df = df[df['PlateName'] == plate_name]
				plate_transfers = []
				for idx, plate_df_entry in plate_df.iterrows():
					src_plt = plate_df_entry[0]
					dest_plt = wtw.dest_plate
					src_well = plate_df_entry[1]
					dest_well = plate_df_entry[2]
					unique_id = str(uuid.uuid1())

					tf = Transfer(unique_id,
								  source_plate=src_plt, dest_plate=dest_plt, source_well=src_well.upper(), dest_well=dest_well.upper())
					plate_transfers.append(unique_id)
					self.transfers[unique_id] = tf

				self.transfers_by_plate[plate_name] = plate_transfers

			# produce numpy array of ids to be performed in a sequence, grouped by plate.
			current_idx = 0
			self.num_transfers = len(self.transfers)
			self.tf_seq = np.empty(self.num_transfers, dtype=object)

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
		"""
		Checks to see that current transfer has not already been timestamped with a status.

		Raises TError if transfer has already been updated and/or plate is complete
		"""
		self.synchronize()
		self.sortTransfers()
		current_transfer = self.transfers[self.current_uid]
		if current_transfer['timestamp'] is None:
			return True
		else:
			msg = ''
			self.log('Cannot update transfer: %s Status is already marked as %s ' %
					 (self.tf_id(), self.transfers[self.current_uid]['status']))
			msg = self.msg
			if self.plateComplete():
				if self.protocolComplete():
					self.log('Transfer Protocol complete ')
					raise TError(msg + self.msg)
				else:
					self.log('Plate %s is complete, press next plate to continue ' % self.current_plate_name)
					raise TError(msg + self.msg)


	def complete(self):
		"""
		Complete current transfer. If plate is complete, raise TConfirm
		"""
		if self.plateComplete():
			self.log('Plate %s is complete, load plate %s to continue')
		if self.canUpdate():
			self.transfers[self.current_uid].updateStatus(TStatus.completed)
			self.log('transfer complete: %s' % self.tf_id())
			self.step()


	def step(self):
		"""
		Moves index to the next transfer in a plate. If plate full or transfer complete, raises flag
		"""
		self.sortTransfers()
		self.canUndo = True

		if self.plateComplete():
			if self.protocolComplete():
				self.log('TransferProtocol is complete')
				raise TConfirm(self.msg)
			else:
				self.log('Plate %s completed' % self.current_plate_name)
				raise TConfirm(self.msg)
		else:
			self.current_idx_increment()

	def nextPlate(self):
		"""
		Checks if a source plate
		Raise TConfirm if plate is complete
		Raises TError if plate is incomplete
		"""
		if self.plateComplete():
			raise TConfirm('Are you sure you wish to finish the plate?')
		else:
			self.log('Warning: Plate %s not yet complete ' % self.current_plate_name)
			skipped_transfers_in_plate = list(
				set(self.lists['uncompleted']) &
				set(self.transfers_by_plate[self.current_plate_name]))
			msg = self.msg
			self.log('Confirm to skip %s remaining transfers.  Are you sure?' %
					 len(skipped_transfers_in_plate))
			raise TError(msg + self.msg)

	def nextPlateConfirm(self):
		self.canUndo = False
		if not self.protocolComplete():
			self.current_plate_increment()
			self.current_idx_increment()
			self.log('Please load plate %s' % self.current_plate_name)
			raise TConfirm(self.msg)
		else:
			self.log('TransferProtocol is complete')

	def nextPlateOverride(self):
		"""
		Marks any incomplete transfers in the current plate as skipped and moves to the next plate

		raises TConfirm to notify how many transfers skipped
		"""
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
			raise TConfirm(self.msg + ' Protocol Complete')
		else:
			self.current_plate_increment()
			self.current_idx_increment(steps=len(skipped_transfers_in_plate))
			msg = '. Please load plate %s' % self.current_plate_name
			raise TConfirm(self.msg + msg)

	def plateComplete(self):
		self.synchronize()
		self.sortTransfers()
		for tf in self.transfers_by_plate[self.current_plate_name]:
			if self.transfers[tf].status == TStatus.uncompleted:
				return False

		self.lists['target']
		return True


	def undo(self):
		"""
		Overrides superclass undo to disalllow undo-ing immediately after switching plates
		:return:
		"""
		self.synchronize()
		self.sortTransfers()
		if self.canUndo:
			if not self.plateComplete():
				self.current_idx_decrement()
			self.transfers[self.current_uid].resetTransfer()
			self.sortTransfers()
			self.canUndo = False
			self.log('transfer marked incomplete: %s' % self.tf_id())
		else:
			self.log('Cannot undo previous operation')

	def current_plate_increment(self):
		self._current_plate += 1
		self.synchronize()

	def current_plate_decrement(self):
		self._current_plate -= 1
		self.synchronize()

	def synchronize(self):
		"""
		Overrides superclass synchronize to support multiple plates
		:return:
		"""
		self.current_uid = self.tf_seq[self._current_idx]
		self.current_plate_name = self.plate_names[self._current_plate]

