# WellLit-WelltoWell
WelltoWell implementation of the WellLit library

## Installation Instructions

1. Install Anaconda (tested on version 4.8.3) or miniconda for python 3.7, make sure to add to PATH
2. Make anaconda environment: Open up anaconda prompt and type: conda create -n WellLit python=3.7.6
3. Activate the environment with conda activate WellLit
4. Install dependencies:
  - conda install matplotlib==3.1.3
  - conda install -c conda-forge kivy
  - pip install kivy-garden
  - pip install pandas
  - garden install graph
  - garden install matplotlib
5. Clone this repo https://github.com/czbiohub/WellLit-WelltoWell.git or download as a zip file and then unzip
6. Create a shortcut to the 'startup.bat' file located in folder and place it on the desktop. If you like, you can change the icon to be the WellLit icon by right clicking the shortcut, clicking properties, and then "change Icon" in the 'shortcut' tab



## Use instructions

1. Create a csv file representing your desired transfer protocol and save it to the desktop folder named 'CSVTransfers'
The format of the csv file must be:

destination plate name
source plate, source well, destination well
source plate, source well, destination well
source plate, source well, destination well
.
.
.

e.g. a valid file would be:

destination-plate-001
sample-plate-002, A2, A1
sample-plate-003, A2, A2

2. Run WellLit program by double clicking the icon on the desktop
3. Select 'Load Protocol' and navigate to the csv file you created, click load. 
4. A Transfer Protocol is generated that will step you through each transfer. A transfer can be marked as 'complete', 'skipped', 'failed', or 'uncompete'. A record csv is generated and updated after each transfer and saved to the desktop in the 'TransferRecords' folder.
	Keyboard shortcuts: n: next / complete transfer, p: next plate, q: quit program
5. At the end of a transfer protocol, you can choose to load a new csv file, or quit. Records are always produced automatically when a protocol is complete.

## Changing default save / records directory:

To change the default directory where records are saved, edit line 13 of the file WellLit-WelltoWell/WelltoWell.py in a text editor
To change teh default load directory where csv files are imported from, edit line 16 of the file WellLit-WelltoWell/WelltoWellGUI.py


## Software update instructions (if necessary)

1. Right click on the WellLit-WelltoWell folder on the desktop and select 'Git Bash'
2. In the terminal window that opens, type 'git pull' and hit enter. If any updates are available it will download them in the terminal window. 
4. In the same terminal, type 'cd WellLit', hit enter, then type 'git pull' and hit enter.
5. You're done!

## Troubleshooting

If the program fails or does not behave as expected, send an email to andrew.cote@czbiohub.org
