import sqlite3

class DB:
    def __init__(self, db_dir):
        self.connection = sqlite3.connect(db_dir)
        self.cursor = self.connection.cursor()

    def execute(self, sql_command, args=None):
        if args:
            self.cursor.execute(sql_command, args)
        else:
            self.cursor.execute(sql_command)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()
