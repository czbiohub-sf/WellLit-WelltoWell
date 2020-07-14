import kivy
kivy.require('1.11.1')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
# noinspection ProblematicWhitespace
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.widget import Widget
from kivy.uix.filechooser import FileChooserListView
from datetime import datetime
from pathlib import Path
import json, logging, time, os, time, csv
from WellLit.WellLitGUI import WellLitWidget, ConfirmPopup, WellLitPopup, WellPlot
from WellLit.Transfer import TError, TConfirm
from WellToWell import WelltoWell


class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)


class WelltoWellWidget(WellLitWidget):
    """
    Loads csv files as directed by user to build well-to-well transfer protocols, and provides functionality
    for stepping through protocols using GUI buttons. Catches errors thrown by invalid user actions and displays error
    message in popups.
    """
    dest_plate = StringProperty()
    source_plate = StringProperty()

    def __init__(self, **kwargs):
        super(WelltoWellWidget, self).__init__(**kwargs)
        self.wtw = WelltoWell()
        self.msg = 'some message'
        self.initialized = False
        self.dest_plate = ''
        self.source_plate = ''

    def getStatus(self):
        return self.msg

    def load(self, path, filename):
        filename_csv  = str(filename[0])
        target = (os.path.join(str(path), filename_csv))
        logging.info('User selected file %s to load' % target)
        self.dismiss_popup()
        if os.path.isfile(target):
            try:
                self.wtw.loadCsv(target)
            except TError as err:
                self.showPopup(err, 'Load Failed')
            except TConfirm as conf:
                self.showPopup(conf, 'Load Successful')
                if not self.initialized:
                    self.reset_plates()
                    self.initialized = True
                self.updateLights()
                self.wtw.tp.id_type = ''
                self.dest_plate = self.wtw.dest_plate
                self.updateLabels()

    def updateLabels(self):
        self.source_plate = self.wtw.tp.current_plate_name

    def show_load(self):
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title='Load File', content=content)
        self._popup.size_hint = (0.4, .8)
        self._popup.pos_hint = {'x': 10.0 / Window.width, 'y': 100 / Window.height}
        self._popup.open()

    def updateLights(self):
        '''
        At each step:
        dest_wells: completed -> filled, uncompleted -> empty
        source_wells: completed -> empty, uncompletled -> full
        color current target wells, and black out wells not involved in transfer
        '''
        if self.initialized:
            self.ids.source_plate.pl.blackoutWells()
            self.ids.dest_plate.pl.blackoutWells()

            current_transfers = self.wtw.tp.transfers_by_plate[self.wtw.tp.current_plate_name]

            # For transfer that is complete, color source well empty and dest well as full
            for tf_id in self.wtw.tp.lists['completed']:
                self.ids.dest_plate.pl.markFilled(self.wtw.tp.transfers[tf_id]['dest_well'])
                if tf_id in current_transfers:
                    self.ids.source_plate.pl.markEmpty(self.wtw.tp.transfers[tf_id]['source_well'])

            # For transfer that is uncomplete, mark source well as full, dest well as empty
            for tf_id in list(set(current_transfers) & set(self.wtw.tp.lists['uncompleted'])):
                self.ids.source_plate.pl.markFilled(self.wtw.tp.transfers[tf_id]['source_well'])
                self.ids.dest_plate.pl.markEmpty(self.wtw.tp.transfers[tf_id]['dest_well'])

            # skipped wells in source are full, and empty in dest
            for tf_id in list(set(current_transfers) & set(self.wtw.tp.lists['skipped'])):
                self.ids.source_plate.pl.markFilled(self.wtw.tp.transfers[tf_id]['source_well'])
                self.ids.dest_plate.pl.markEmpty(self.wtw.tp.transfers[tf_id]['dest_well'])

            # Mark current targets
            self.ids.source_plate.pl.markTarget(self.wtw.tp.transfers[self.wtw.tp.current_uid]['source_well'])
            self.ids.dest_plate.pl.markTarget(self.wtw.tp.transfers[self.wtw.tp.current_uid]['dest_well'])

            self.ids.source_plate.pl.show()
            self.ids.dest_plate.pl.show()

    def next(self):
        try:
            self.wtw.next()
            self.wtw.writeTransferRecordFiles(None)
            self.status = self.wtw.tp.msg
            self.updateLights()
        except TError as err:
            self.showPopup(err, 'Unable to complete transfer')
            self.status = err.__str__()
        except TConfirm as conf:
            self.showPopup(conf, 'Plate complete', func=self.nextPlate)
            self.status = conf.__str__()

    def skip(self):
        try:
            self.wtw.skip()
            self.wtw.writeTransferRecordFiles(None)
            self.status = self.wtw.tp.msg
            self.updateLights()
        except TError as err:
            self.showPopup(err, 'Unable to skip transfer')
            self.status = err.__str__()
        except TConfirm as conf:
            self.showPopup(conf, '')
            self.status = conf.__str__()

    def failed(self):
        try:
            self.wtw.failed()
            self.wtw.writeTransferRecordFiles(None)
            self.status = self.wtw.tp.msg
            self.updateLights()
        except TError as err:
            self.showPopup(err, 'Unable to abort transfer')
            self.status = err.__str__()
        except TConfirm as conf:
            self.showPopup(conf, '')
            self.status = conf.__str__()

    def undo(self):
        try:
            self.wtw.undo()
            self.wtw.writeTransferRecordFiles(None)
            self.status = self.wtw.tp.msg
            self.updateLights()
        except TError as err:
            self.showPopup(err, 'Unable to undo transfer')
            self.status = err.__str__()
        except TConfirm as conf:
            self.showPopup(conf, '')
            self.status = conf.__str__()

    def nextPlate(self, _):
        try:
            self.wtw.nextPlate()
        except TError as err:
            self.showPopup(err, 'Unable to complete plate', func=self.nextPlateOverride)
            self.status = err.__str__()
        except TConfirm as conf:
            self.nextPlateConfirm(None)
            self.updateLights()

    def nextPlateConfirm(self, _):
        try:
            self.wtw.nextPlateConfirm()
            self.status = self.wtw.tp.msg
            self.updateLights()
        except TError as err:
            self.showPopup(err, 'Cannot load next plate')
            self.status = err.__str__()
        except TConfirm as conf:
            self.showPopup(conf, 'Load next plate')
            self.updateLabels()
            self.updateLights()

    def nextPlateOverride(self, _):
        try:
            self.wtw.nextPlateOverride()
            self.status = self.wtw.tp.msg
            self.updateLights()
        except TError as err:
            self.showPopup(err, 'Cannot override plate skip')
            self.status = err.__str__()
            self.updateLights()
        except TConfirm as conf:
            self.showPopup(conf, 'Plate skipped')
            self.status = conf.__str__()
            self.updateLights()

    def finishTransfer(self):
        if self.initialized:
            if not self.wtw.tp.protocolComplete():
                self.showPopup(TConfirm(
                    'Are you sure you wish to finish this transfer protocol? All remaining transfers will be skipped'),
                               'Confirm transfer abort',
                               func=self.finishTransferConfirm)
            else:
                self.finishTransferConfirm(None)

    def finishTransferConfirm(self, _):
        try:
            self.ids.source_plate.pl.emptyWells()
            self.ids.dest_plate.pl.emptyWells()
            self.ids.source_plate.pl.show()
            self.ids.dest_plate.pl.show()
            self.wtw.writeTransferRecordFiles(None)
            self.showPopup(TConfirm('Record file generated'), 'Transfers recorded')
        except TError as err:
            self.showPopup(err, 'Error aborting transfer')
            self.status = err.__str__()

    def setSquareMarker(self):
        """
        Change shape of source well plate
        """
        if self.initialized:
            self.ids.source_plate.pl.setMarker('square')

    def setCircleMarker(self):
        """
        Change shape of source well plate
        """
        if self.initialized:
            self.ids.source_plate.pl.setMarker('circle')


class WellToWellApp(App):
    def build(self):
        return WelltoWellWidget()


if __name__ == '__main__':
    cwd = os.getcwd()
    logdir = os.getcwd() + '/logs/'
    logfile = 'WelltoWell_Logfile_' + datetime.utcnow().strftime('%Y_%m_%d') + '.txt'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] - %(message)s',
        filename=Path(logdir + logfile))  # pass explicit filename here
    logger = logging.getLogger()  # get the root loggers
    logging.info('Session started')

    Window.size = (1600, 1200)
    Window.fullscreen = True
    WellToWellApp().run()