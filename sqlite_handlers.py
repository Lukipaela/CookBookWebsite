import sqlite3

# Class variable
prod_mode = True


# -------------------- DB METHODS -------------------- #
def execute_query(query_string: str, query_args=(), convert_to_dict=True):
    console_log('QUERY:   ' + query_string)
    console_log(f"args: {query_args}")
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            result = db_cursor.execute(query_string, query_args).fetchall()
            if convert_to_dict:
                # convert the resulting List to a Dict and return it to the caller
                columns = [desc[0] for desc in db_cursor.description]
                results = []
                for row in result:
                    summary = dict(zip(columns, row))
                    results.append(summary)
                console_log(results)
                return results
            else:
                # if not requested in Dict form, return as a List, which is combobox-compatible if defined correctly
                console_log(result)
                return result
    except sqlite3.Error as e:
        print('QUERY ERROR:   ' + e.args[0])
        return e.args[0]


def execute_update_script(script_string: str, query_args=()):
    console_log('UPDATE SCRIPT:   ' + script_string)
    console_log(f"args: {query_args}")
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            db_cursor.execute(script_string, query_args)
    except sqlite3.Error as e:
        print('UPDATE SCRIPT ERROR:   ' + e.args[0])
        return e.args[0]


def execute_insert_script(script_string: str, query_args=(), table_name: str = None, id_column: str = None):
    console_log('INSERT SCRIPT:   ' + script_string)
    console_log(f"args: {query_args}")
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            db_cursor.execute(script_string, query_args)

            # if a table name was specified then, the calling code is requesting a newly generated ID to be returned
            if table_name is not None:
                get_id = f"SELECT MAX({id_column}) FROM {table_name}"
                result = db_cursor.execute(get_id).fetchall()[0][0]
                console_log(f"new id: {result}")
                return result
            else:
                return None
    except sqlite3.Error as e:
        print('INSERT SCRIPT ERROR:   ' + e.args[0])
        return e.args[0]


def execute_delete_script(script_string: str, query_args=()):
    console_log('DELETE SCRIPT:   ' + script_string)
    console_log(f"args: {query_args}")
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            db_cursor.execute(script_string, query_args)
    except sqlite3.Error as e:
        print('DELETE SCRIPT ERROR:   ' + e.args[0])
        return e.args[0]


def execute_general_sql(sql_string):
    console_log('GENERAL SQL:   ' + sql_string)
    try:
        with sqlite3.connect("CookBookDatabase.db") as con:
            db_cursor = con.cursor()
            response = db_cursor.execute(sql_string).fetchall()
            console_log(response)
            return response
    except sqlite3.Error as e:
        print('GENERAL SQL ERROR:   ' + e.args[0])
        return e.args[0]


def set_prod_mode(value: bool):
    global prod_mode
    prod_mode = value
    print(f"SQL HANDLER - New prod mode: {prod_mode}")


def console_log(value):
    global prod_mode
    if not prod_mode:
        print(value)
