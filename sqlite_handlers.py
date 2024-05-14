import sqlite3


# -------------------- DB METHODS -------------------- #
def execute_query(query_string: str, convert_to_dict=True):
    print('QUERY:   ' + query_string)
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            result = db_cursor.execute(query_string).fetchall()
            if convert_to_dict:
                # convert the resulting List to a Dict and return it to the caller
                columns = [desc[0] for desc in db_cursor.description]
                results = []
                for row in result:
                    summary = dict(zip(columns, row))
                    results.append(summary)
                print(results)
                return results
            else:
                # if not requested in Dict form, return as a List, which is combobox-compatible if defined correctly
                print(result)
                return result
    except sqlite3.Error as e:
        return e.args[0]


def execute_update_script(script_string: str):
    print('UPDATE SCRIPT:   ' + script_string)
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            db_cursor.execute(script_string)
    except sqlite3.Error as e:
        return e.args[0]


def execute_insert_script(script_string: str, table_name: str = None, id_column: str = None):
    print('INSERT SCRIPT:   ' + script_string)
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            db_cursor.execute(script_string)

            # if a table name was specified then, the calling code is requesting a newly generated ID to be returned
            if table_name is not None:
                get_id = f"SELECT MAX({id_column}) FROM {table_name}"
                result = db_cursor.execute(get_id).fetchall()[0][0]
                print(f"new id: {result}")
                return result
            else:
                return None
    except sqlite3.Error as e:
        return e.args[0]


def execute_delete_script(script_string: str):
    print('DELETE SCRIPT:   ' + script_string)
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            db_cursor.execute(script_string)
    except sqlite3.Error as e:
        return e.args[0]


def execute_general_sql(sql_string):
    print('GENERAL SQL:   ' + sql_string)
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            response = db_cursor.execute(sql_string).fetchall()
            print(response)
            return response
    except sqlite3.Error as e:
        return e.args[0]
