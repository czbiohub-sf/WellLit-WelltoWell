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
from kivy.properties import ObjectProperty
from kivy.uix.widget import Widget
from kivy.uix.filechooser import FileChooserListView
import json, logging, time, os, time, csv
from WellLit.WellLitGUI import WellLitWidget, ConfirmPopup, WellLitPopup, WellPlot
from WelltoWell import WellToWell

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] - %(message)s',
    filename='filename.txt')  # pass explicit filename here
logger = logging.getLogger()  # get the root logger

class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)


class WelltoWellWidget(WellLitWidget):
    def __init__(self, **kwargs):
        super(WelltoWellWidget, self).__init__(**kwargs)
        self.wtw = WellToWell()

    def load(self, path, filename):
        target = (os.path.join(str(path), str(filename[0])))
        logging.info('User selected file %s to load' % target)
        self.dismiss_popup()
        if os.path.isfile(target):
            self.wtw.loadCsv(target)
            if self.wtw.tp is not None:
                self.reset_plates()
                self.updateLights()
                self.wtw.tp.id_type = ''

    def show_load(self):
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title='Load File', content=content, size_hint=(0.5, 0.5))
        self._popup.open()

    def updateLights(self):
        '''
        dest_wells:
            - colors well empty to filled, current target
        source_wells:
            - colors well filled to empty, current target
        :return:
        '''
        self.ids.source_plate.pl.emptyWells()
        self.ids.dest_plate.pl.emptyWells()
        current_transfers = self.wtw.tp.transfers_by_plate[self.wtw.tp.current_plate_name]

        # For transfer that is complete, color source well empty and dest well as full
        for tf_id in self.wtw.tp.lists['completed']:
            self.ids.dest_plate.pl.markFilled(self.wtw.tp.transfers[tf_id]['dest_well'])
            if tf_id in current_transfers:
                self.ids.source_plate.pl.markEmpty(self.wtw.tp.transfers[tf_id]['source_well'])

        # For transfer that is uncomplete, mark source well as full
        for tf_id in list(set(current_transfers) & set(self.wtw.tp.lists['uncompleted'])):
            self.ids.source_plate.pl.markFilled(self.wtw.tp.transfers[tf_id]['source_well'])

        # Mark current targets
        self.ids.source_plate.pl.markTarget(self.wtw.tp.transfers[self.wtw.tp.current_uid]['source_well'])
        self.ids.dest_plate.pl.markTarget(self.wtw.tp.transfers[self.wtw.tp.current_uid]['dest_well'])

        self.ids.source_plate.pl.show()
        self.ids.dest_plate.pl.show()

    def next(self):
        self.wtw.next()
        self.updateLights()

    def skip(self):
        self.wtw.skip()
        self.updateLights()

    def failed(self):
        self.wtw.failed()
        self.updateLights()

    def undo(self):
        self.wtw.undo()
        self.updateLights

    def nextPlate(self):
        self.wtw.nextPlate()
        self.updateLights()


class WelltoWellApp(App):
    def build(self):
        return WelltoWellWidget()


if __name__ == '__main__':
    cwd = os.getcwd()
    logging.basicConfig(filename=cwd + '\WelltoWell_log.log',
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        level=logging.INFO,
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.info('Session started')
    Window.size = (1600, 1200)
    # Window.fullscreen = True
    WelltoWellApp().run()