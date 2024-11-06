import csv
from typing import List, Dict, Optional

class CSVHandler:
    def __init__(self, filepath: str, delimiter: str = ',', encoding: str = 'utf-8'):
        """
        Initializes the CSVHandler instance.

        :param filepath: Path to the CSV file.
        :param delimiter: Character separating values in the CSV file (default is ',').
        :param encoding: File encoding (default is 'utf-8').
        """
        self.filepath = filepath
        self.delimiter = delimiter
        self.encoding = encoding

    def read_csv(self, as_dict: bool = True) -> List[Dict[str, str]]:
        """
        Reads the CSV file and returns its content.

        :param as_dict: If True, returns each row as a dictionary with headers as keys. 
                        If False, returns rows as lists.
        :return: List of rows as dictionaries or lists based on `as_dict` parameter.
        """
        try:
            with open(self.filepath, mode='r', newline='', encoding=self.encoding) as file:
                try:
                    if as_dict:
                        reader = csv.DictReader(file, delimiter=self.delimiter)
                        return [row for row in reader]
                    else:
                        reader = csv.reader(file, delimiter=self.delimiter)
                        return [row for row in reader]
                except csv.Error as e:
                    print(f"CSV error: {e}")
                    return []
        except FileNotFoundError:
            print(f"Error: The file {self.filepath} was not found.")
            return []
        except UnicodeDecodeError:
            print(f"Error: The file {self.filepath} cannot be decoded with the specified encoding.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while reading the CSV: {e}")
            return []

    def write_csv(self, data: List[Dict[str, str]], fieldnames: List[str], mode: str = 'w'):
        """
        Writes data to the CSV file. If the file doesn't exist, it will be created.

        :param data: List of dictionaries containing the data to write.
        :param fieldnames: List of fieldnames (headers) for the CSV file.
        :param mode: Mode to open the file ('w' for write, 'a' for append).
        """
        try:
            with open(self.filepath, mode=mode, newline='', encoding=self.encoding) as file:
                try:
                    writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=self.delimiter)
                    if mode == 'w':  # Write header only if file is being created or overwritten
                        writer.writeheader()
                    writer.writerows(data)
                except csv.Error as e:
                    print(f"CSV error: {e}")
        except IOError as e:
            print(f"I/O error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while writing to the CSV: {e}")

    def append_csv(self, data: List[Dict[str, str]], fieldnames: List[str]):
        """
        Appends data to the existing CSV file.

        :param data: List of dictionaries containing the data to append.
        :param fieldnames: List of fieldnames (headers) for the CSV file.
        """
        self.write_csv(data, fieldnames, mode='a')

    def filter_data(self, condition: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Filters the CSV data based on a condition.

        :param condition: Dictionary where the key is the column name, and the value is the value to match.
        :return: List of filtered rows as dictionaries.
        """
        data = self.read_csv()
        try:
            filtered_data = [
                row for row in data if all(row[key] == value for key, value in condition.items())
            ]
            return filtered_data
        except TypeError:
            print("Error: The condition dictionary must have the same keys as the CSV headers.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while filtering data: {e}")
            return []

    def update_row(self, condition: Dict[str, str], updated_data: Dict[str, str]) -> bool:
        """
        Updates a specific row based on a condition.

        :param condition: Dictionary to match rows (key: column, value: value to match).
        :param updated_data: Dictionary containing the columns and new values to update.
        :return: True if the update is successful, False otherwise.
        """
        data = self.read_csv()
        try:
            updated = False
            for row in data:
                if all(row[key] == value for key, value in condition.items()):
                    row.update(updated_data)
                    updated = True
            if updated:
                self.write_csv(data, fieldnames=list(data[0].keys()))  # Write updated data back to file
            return updated
        except KeyError as e:
            print(f"Key error: {e} - Make sure the keys in the condition and updated_data match the CSV headers.")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while updating the CSV: {e}")
            return False

    def get_column(self, column_name: str) -> List[str]:
        """
        Retrieves all values of a specific column.

        :param column_name: The name of the column to retrieve.
        :return: List of values from the specified column.
        """
        data = self.read_csv()
        try:
            return [row[column_name] for row in data if column_name in row]
        except KeyError:
            print(f"Error: The column '{column_name}' does not exist in the CSV.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while retrieving the column: {e}")
            return []
