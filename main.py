#! /usr/bin/env python3
# coding=utf-8

"""
 description:
 author:		kevin.wang
 create date:	2024-11-06
 version:		1.0.0
"""


import sys
import csv
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog, QHBoxLayout, QListView, QMessageBox, QInputDialog, QTextEdit, QLabel
from PyQt5.QtCore import QStringListModel

from csvwrapper import CSVHandler
from tcmcontroller import TCMController


def assemble_instrument(instrument_dict):
    device = instrument_dict['Device']
    module = instrument_dict['Module']
    register = instrument_dict['Register']
    type = instrument_dict['Type']

    if type == 'V':
        return [f"{module}:{register}?@{device}", 'V'] 
    else:
        return None

class CommandApp(QWidget):
    def __init__(self, simulation = False):
        super().__init__()
        self.init_ui()
        self.simulation = simulation
        if self.simulation is not True:
            self.controller = TCMController("/dev/ttyUSB0", 57600)

    def __del__(self):
        pass

    def init_ui(self):
        # Create widgets
        self.log_edit = QTextEdit(self)
        self.load_button = QPushButton('Load CSV File', self)
        self.save_button = QPushButton('Save CSV File', self)
        self.list_view = QListView(self)
        self.edit_button = QPushButton('Edit Selected Row', self)
        self.clear_log_button = QPushButton('Clear Log', self)  
        self.log_label = QLabel('Log:', self)  # Label for log_edit
        self.list_label = QLabel('List View:', self)  # Label for list_view

        # Set up button actions
        self.load_button.clicked.connect(self.load_csv)
        self.save_button.clicked.connect(self.save_csv)
        self.edit_button.clicked.connect(self.edit_row)
        self.clear_log_button.clicked.connect(self.clear_log)

        # Set up layout for buttons
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.clear_log_button)

        # Set up the main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.log_label)
        main_layout.addWidget(self.log_edit)
        main_layout.addWidget(self.list_label)
        main_layout.addWidget(self.list_view)
        main_layout.addLayout(button_layout)

        # Set the main layout
        self.setLayout(main_layout)

        # Set window properties
        self.setWindowTitle('CSV File Loader, Editor, and Saver')
        self.setGeometry(300, 300, 600, 450)
        self.show()

        # Initialize model and view
        self.model = QStringListModel()
        self.list_view.setModel(self.model)
        self.data = []  # Store the loaded data in a list of rows

    def load_csv(self):
        sample_command = "Load data from instruments.csv"
        self.log_edit.append(sample_command)

        """Load data from a CSV file and populate the QListView"""
        file_name, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv);;All Files (*)")
        
        if file_name:
            try:
                with open(file_name, 'r', newline='') as f:
                    csv_reader = csv.reader(f)
                    self.data = [row for row in csv_reader]

                # Convert each row to a string to display in the QListView
                display_data = [",".join(row) for row in self.data]
                self.model.setStringList(display_data)

                print("CSV file loaded successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load CSV file: {str(e)}")

            handler = CSVHandler(file_name)
            data = handler.read_csv()
            instruments = []
            for item in data:
                ins = assemble_instrument(item)
                instruments.append(ins)

                if ins is not None:
                    self.log_edit.append(str(ins))

            if instruments is not None:
                for ins in instruments:
                    self.controller.set_instruments_sets([ins])
                    print(self.controller.get_instruments_return_value())

    def save_csv(self):
        """Save the current data in the QListView back to a CSV file"""
        file_name, _ = QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv);;All Files (*)")
        
        if file_name:
            try:
                with open(file_name, 'w', newline='') as f:
                    csv_writer = csv.writer(f)
                    csv_writer.writerows(self.data)
                print("CSV file saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save CSV file: {str(e)}")
            sample_command = "Save data into instruments.csv"
            self.log_edit.append(sample_command)

    def edit_row(self):
        """Edit the selected row in the QListView"""
        # Get the index of the selected item
        index = self.list_view.selectedIndexes()
        if not index:
            QMessageBox.warning(self, "No Selection", "Please select a row to edit.")
            return

        # Get the selected row from the model and display it in an input dialog
        row_index = index[0].row()
        row_data = self.data[row_index]

        # Convert the row to a comma-separated string for editing
        current_text = ",".join(row_data)
        new_text, ok = QInputDialog.getText(self, "Edit Row", "Modify the row:", text=current_text)
        
        if ok and new_text:
            # Split the edited row by commas and update the data
            new_row = new_text.split(",")
            self.data[row_index] = new_row

            # Update the QListView display with the modified data
            display_data = [",".join(row) for row in self.data]
            self.model.setStringList(display_data)

            print(f"Row updated: {new_row}")
        else:
            print("Edit canceled or empty input.")

    def clear_log(self):
        """Clear the contents of log_edit"""
        self.log_edit.clear()

    def closeEvent(self, event):
        if self.simulation is not True:
            self.controller.stop()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    debug_flag = False
    if len(sys.argv) == 2 and sys.argv[1] == '--simulation':
        debug_flag = True
    ex = CommandApp(debug_flag)
    sys.exit(app.exec_())
